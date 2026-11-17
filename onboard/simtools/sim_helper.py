#!/usr/bin/env python3
"""Tro giup vong kin (CHI mo phong): cat canh chaser, dat chaser sau muc tieu, ghi VI TRI THAT cua hai may
(SIM_STATE) de cham diem, chay kich ban (mat hinh / disengage), dieu phoi go-file / stop-file.

Khong nam trong app. Cong SITL: chaser SERIAL0=5770 (danh cho app), SERIAL1=5772 (script nay),
SERIAL2=5773 (SimTruthSource); target SERIAL0=5760 (target.py), SERIAL1=5762 (SimTruthSource), SERIAL2=5763 (script nay).

Dong ho: time.monotonic() (cung dong ho voi app tren Linux), ghi trong truth.csv cot t.
Truc toa do chung: NED quanh TARGET_HOME, tinh bang trac dia WGS84 (dtrack.mavlink_io.latlon_to_ned).
"""
import argparse
import csv
import json
import math
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dtrack.mavlink_io import latlon_to_ned  # noqa: E402

from pymavlink import mavutil  # noqa: E402

TARGET_HOME = (-35.363261, 149.165230, 584.0)   # phai khop sim/run_chase.sh / chaselib.py
CHASER_HOME = (-35.3633957, 149.165230, 584.0)
GUIDED, LOITER = 4, 5
MSG_SIM_STATE = 108
COLS = ["t", "tgt_n", "tgt_e", "tgt_alt", "tgt_vn", "tgt_ve", "tgt_vd",
        "ch_n", "ch_e", "ch_alt", "ch_vn", "ch_ve", "ch_vd", "ch_roll", "ch_pitch", "ch_yaw",
        "d3", "dh", "ch_armed", "ch_mode"]


def log(msg):
    print("[helper] %s" % msg, flush=True)


class Conn:
    """Mot ket noi MAVLink toi mot SITL, giu SIM_STATE moi nhat (thoi diem nhan, lat, lon, alt, v, euler)."""

    def __init__(self, url, tag, rate_hz=50.0, timeout=240.0):
        self.tag = tag
        t0 = time.monotonic()
        while True:
            try:
                self.mav = mavutil.mavlink_connection(url, source_system=254, source_component=190)
                if self.mav.wait_heartbeat(timeout=10):
                    break
            except OSError as exc:
                log("%s chua noi duoc %s: %s" % (tag, url, exc))
            if time.monotonic() - t0 > timeout:
                raise RuntimeError("khong noi duoc %s" % url)
            time.sleep(2)
        self.sim = None
        self.n_sim = 0
        self.armed = False
        self.mode = None
        self.mav.mav.command_long_send(self.mav.target_system, self.mav.target_component, 511, 0,
                                       MSG_SIM_STATE, int(1e6 / rate_hz), 0, 0, 0, 0, 0)
        log("%s da noi %s" % (tag, url))

    def pump(self):
        """Doc het ban tin. Tra True neu co SIM_STATE moi."""
        got = False
        while True:
            m = self.mav.recv_match(blocking=False)
            if m is None:
                return got
            typ = m.get_type()
            if typ == "SIM_STATE":
                self.sim = (time.monotonic(), m.lat_int / 1e7, m.lon_int / 1e7, m.alt, m.vn, m.ve, m.vd,
                            m.roll, m.pitch, m.yaw)
                self.n_sim += 1
                got = True
            elif typ == "HEARTBEAT" and m.type != mavutil.mavlink.MAV_TYPE_GCS \
                    and m.get_srcSystem() == self.mav.target_system:
                self.armed = bool(m.base_mode & 128)
                self.mode = m.custom_mode

    def cmd(self, command, *params):
        p = list(params) + [0] * (7 - len(params))
        self.mav.mav.command_long_send(self.mav.target_system, self.mav.target_component, command, 0, *p)

    def pos_ned(self, ref):
        s = self.sim
        n, e = latlon_to_ned(ref[0], ref[1], s[1], s[2])
        return n, e, s[3] - ref[2]


class Recorder:
    def __init__(self, path, ch: Conn, tg: Conn, win):
        self.f = open(path, "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(COLS)
        self.ch, self.tg = ch, tg
        self.rows = 0
        self.last = None       # dict hang moi nhat
        self.win = win

    def step(self):
        """Doc hai ket noi; moi SIM_STATE moi cua chaser -> mot dong. Tra True neu co dong moi."""
        self.tg.pump()
        got = self.ch.pump()
        if not got or self.tg.sim is None:
            return False
        c, t = self.ch.sim, self.tg.sim
        cn, ce, ca = self.ch.pos_ned(TARGET_HOME)
        tn, te, ta = self.tg.pos_ned(TARGET_HOME)
        dn, de, dz = tn - cn, te - ce, ta - ca
        dh = math.hypot(dn, de)
        d3 = math.sqrt(dh * dh + dz * dz)
        # noi suy vi tri muc tieu toi thoi diem cua chaser (hai luong khong dong bo toi ~20 ms)
        self.w.writerow(["%.4f" % c[0], "%.3f" % tn, "%.3f" % te, "%.3f" % ta, "%.3f" % t[4], "%.3f" % t[5], "%.3f" % t[6],
                         "%.3f" % cn, "%.3f" % ce, "%.3f" % ca, "%.3f" % c[4], "%.3f" % c[5], "%.3f" % c[6],
                         "%.4f" % c[7], "%.4f" % c[8], "%.4f" % c[9], "%.3f" % d3, "%.3f" % dh,
                         int(self.ch.armed), self.ch.mode])
        self.rows += 1
        if self.rows % 50 == 0:
            self.f.flush()
        self.last = dict(t=c[0], d3=d3, dh=dh, tspeed=math.hypot(t[4], t[5]), cspeed=math.hypot(c[4], c[5]),
                         tn=tn, te=te, ta=ta, cn=cn, ce=ce, ca=ca)
        return True

    def close(self):
        self.f.close()


def send_pos(ch: Conn, n, e, d, yaw):
    """SET_POSITION_TARGET_LOCAL_NED: vi tri + yaw (bo qua van toc, gia toc, yaw rate): mask 8|16|32|64|128|256|2048."""
    ch.mav.mav.set_position_target_local_ned_send(
        0, ch.mav.target_system, ch.mav.target_component, 1, 2552, n, e, d, 0, 0, 0, 0, 0, 0, yaw, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="thu muc ket qua")
    ap.add_argument("--speed", type=float, required=True)
    ap.add_argument("--scenario", choices=["none", "blackout", "disengage"], default="none")
    ap.add_argument("--alt", type=float, default=30.0)
    ap.add_argument("--range", type=float, default=15.0, dest="rng")
    ap.add_argument("--tol", type=float, default=3.0)
    ap.add_argument("--window", type=float, default=120.0)
    ap.add_argument("--start-back", type=float, default=25.0, help="chaser dat sau muc tieu (m), cung huong")
    ap.add_argument("--max-wait", type=float, default=150.0)
    ap.add_argument("--event-at", type=float, default=40.0, help="s sau t_ws cho kich ban mat hinh / disengage")
    ap.add_argument("--blackout-s", type=float, default=3.0)
    ap.add_argument("--straight", action="store_true", help="muc tieu bay thang (chi ghi vao events.json de bo cham biet)")
    ap.add_argument("--chaser-ctl", default="tcp:127.0.0.1:5772")
    ap.add_argument("--chaser-unblock", default="127.0.0.1:5770")
    ap.add_argument("--target-truth", default="tcp:127.0.0.1:5763")
    a = ap.parse_args()
    out = a.out
    f_go, f_stop = os.path.join(out, "go"), os.path.join(out, "stop")
    f_ready, f_appup = os.path.join(out, "ready"), os.path.join(out, "app_up")
    f_appstop, f_black = os.path.join(out, "app_stop"), os.path.join(out, "blackout")
    ev = {"scenario": a.scenario, "speed": a.speed, "straight": bool(a.straight)}

    # SITL chaser doi mot ket noi tren SERIAL0 moi chay: mo roi dong (app se dung cong nay sau)
    host, port = a.chaser_unblock.split(":")
    t0 = time.monotonic()
    while True:
        try:
            s = socket.create_connection((host, int(port)), timeout=5)
            time.sleep(1.0)
            s.close()
            break
        except OSError:
            if time.monotonic() - t0 > 240:
                raise
            time.sleep(1)
    ch = Conn(a.chaser_ctl, "chaser")
    tg = Conn(a.target_truth, "target")
    rec = Recorder(os.path.join(out, "truth.csv"), ch, tg, None)

    def spin(sec, every=0.01):
        t_end = time.monotonic() + sec
        while time.monotonic() < t_end:
            rec.step()
            time.sleep(every)

    # ---- cat canh chaser (GUIDED, arm, takeoff), van ghi vi tri that ----
    last = 0.0
    t0 = time.monotonic()
    while not (ch.armed and ch.mode == GUIDED):
        rec.step()
        if time.monotonic() - last > 3.0:
            last = time.monotonic()
            ch.cmd(176, 1, GUIDED)
            ch.cmd(400, 1)
        if time.monotonic() - t0 > 400:
            raise RuntimeError("chaser khong arm duoc")
        time.sleep(0.01)
    log("chaser da arm, GUIDED")
    last = 0.0
    while True:
        rec.step()
        if ch.sim is not None and ch.sim[3] - CHASER_HOME[2] >= 0.95 * a.alt:
            break
        if time.monotonic() - last > 3.0 and (ch.sim is None or ch.sim[3] - CHASER_HOME[2] < 1.0):
            last = time.monotonic()
            ch.cmd(22, 0, 0, 0, 0, 0, 0, a.alt)
        if time.monotonic() - t0 > 600:
            raise RuntimeError("chaser khong cat canh duoc")
        time.sleep(0.01)
    log("chaser da dat do cao")
    while tg.sim is None or tg.sim[3] - TARGET_HOME[2] < 0.9 * a.alt:
        rec.step()
        time.sleep(0.01)
    log("target da dat do cao")

    # ---- dat chaser sau muc tieu start_back m, mui huong Bac (cung huong target luc dau) ----
    ok_since = None
    t0 = time.monotonic()
    last_cmd = 0.0
    while True:
        rec.step()
        if time.monotonic() - last_cmd > 0.2:
            last_cmd = time.monotonic()
            tn, te = latlon_to_ned(CHASER_HOME[0], CHASER_HOME[1], tg.sim[1], tg.sim[2])
            send_pos(ch, tn - a.start_back, te, -a.alt, 0.0)
        L = rec.last
        if L and abs(L["dh"] - a.start_back) < 1.5 and L["cspeed"] < 0.4 and abs(L["ca"] - L["ta"]) < 1.0 \
                and L["tspeed"] < 0.4 and abs(ch.sim[9]) < 0.1:
            ok_since = ok_since or time.monotonic()
            if time.monotonic() - ok_since > 2.0:
                break
        else:
            ok_since = None
        if time.monotonic() - t0 > 180:
            raise RuntimeError("khong dat duoc vi tri xuat phat")
        time.sleep(0.01)
    log("chaser vao vi tri xuat phat d=%.1f m" % rec.last["d3"])
    open(f_ready, "w").close()          # shell khoi dong app sau dong nay (ngung gui lenh vi tri o day)
    t0 = time.monotonic()
    while not os.path.exists(f_appup):
        rec.step()
        time.sleep(0.01)
        if time.monotonic() - t0 > 120:
            raise RuntimeError("app khong len")
    spin(4.0)                           # app ket noi, tracker hoi tu truoc khi muc tieu bay
    # cho chaser (do app dieu khien) tien toi dai range +- 2 m va dung yen 3 s roi moi cho muc tieu bay
    ok_since = None
    t0 = time.monotonic()
    while time.monotonic() - t0 < 90.0:
        if not rec.step():
            time.sleep(0.005)
            continue
        L = rec.last
        if abs(L["d3"] - a.rng) <= 2.0 and L["cspeed"] < 0.7:
            ok_since = ok_since or L["t"]
            if L["t"] - ok_since >= 3.0:
                break
        else:
            ok_since = None
    log("truoc go: d3=%.1f m cspeed=%.2f settled=%s" % (rec.last["d3"], rec.last["cspeed"], ok_since is not None))
    ev["settled_before_go"] = ok_since is not None
    open(f_go, "w").close()
    t_go = time.monotonic()
    ev["t_go"] = t_go
    log("go")

    # ---- do va chay kich ban ----
    t_s90 = t_ws = None
    t_event = None
    blackout_on = None
    ended = False
    while True:
        if not rec.step():
            time.sleep(0.005)
            continue
        L = rec.last
        now = L["t"]
        if t_s90 is None and L["tspeed"] >= 0.9 * a.speed:
            t_s90 = now
            log("target dat 90%% toc do")
        if t_s90 is not None and t_ws is None and abs(L["d3"] - a.rng) <= a.tol:
            t_ws = now
            ev["t_ws"] = t_ws
            log("cua so do bat dau, d3=%.1f" % L["d3"])
        if t_ws is not None:
            if a.scenario == "blackout" and t_event is None and now - t_ws >= a.event_at:
                t_event = now
                open(f_black, "w").close()
                blackout_on = now
                ev["blackout_start"] = now
                log("mat hinh bat dau")
            if blackout_on is not None and now - blackout_on >= a.blackout_s and os.path.exists(f_black):
                os.remove(f_black)
                ev["blackout_end"] = now
                log("mat hinh ket thuc")
            if a.scenario == "disengage" and t_event is None and now - t_ws >= a.event_at:
                t_event = now
                ch.cmd(176, 1, LOITER)
                ev["t_disengage_cmd"] = time.monotonic()
                log("da gui doi mode LOITER (disengage)")
            if a.scenario == "disengage" and t_event is not None and now - t_event >= 10.0:
                break
            if a.scenario != "disengage" and now - t_ws >= a.window + 5.0:
                break
        if t_ws is None and now - t_go > a.max_wait:
            log("bo cuoc: khong vao cua so do")
            ev["aborted"] = "no_window"
            break
    # ---- ket thuc: target phanh (target.py thay stop-file), chaser/app giu dieu khien toi khi ca hai dung ----
    open(f_stop, "w").close()
    ev["t_stop_target"] = time.monotonic()
    t0 = time.monotonic()
    still = None
    while time.monotonic() - t0 < 90.0:
        if rec.step():
            L = rec.last
            if L["tspeed"] < 0.3 and L["cspeed"] < 0.3:
                still = still or L["t"]
                if L["t"] - still > 2.0:
                    break
            else:
                still = None
        else:
            time.sleep(0.005)
    ev["both_stopped"] = still is not None
    ev["t_both_stopped"] = rec.last["t"] if rec.last else None
    log("hai may da dung: %s" % ev["both_stopped"])
    open(f_appstop, "w").close()
    ev["t_app_stop"] = time.monotonic()
    spin(4.0)                           # ghi them trong luc app phanh / thoat
    rec.close()
    ev["rows"] = rec.rows
    with open(os.path.join(out, "events.json"), "w") as f:
        json.dump(ev, f, indent=1)
    log("xong: %d dong truth" % rec.rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
