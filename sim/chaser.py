#!/usr/bin/env python3
"""Chaser: bay GUIDED giu khoang cach --range toi target, doc vi tri target qua MAVLink cua target.

Luat dieu khien (ngang): v_cmd = v_target + clamp(kp*(d3 - range), +-vcl) * L
  L = vector don vi tu chaser den target (duong ngam). Do cao: P theo do cao target.
Ngat an toan: d3 < --safety-range thi v_cmd = v_target - safety_back*L cho toi khi d3 > safety-range + 2.
Cua so do (dung chung dinh nghia voi analyze.py): t_ws = lan dau (sau khi target dat >= 90% toc do dat)
ma |d3 - range| <= tol; chaser dung sau t_ws + window + tail.
"""
import argparse
import csv
import math
import os
import sys

import chaselib as L

COLS = ["t_sim", "t_tgt", "tgt_n", "tgt_e", "tgt_alt", "tgt_vn", "tgt_ve", "tgt_vd",
        "ch_n", "ch_e", "ch_alt", "ch_vn", "ch_ve", "ch_vd", "dist3d", "disth",
        "cmd_vn", "cmd_ve", "cmd_vd", "safety", "set_speed"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--connect", default="tcp:127.0.0.1:5770", help="SERIAL0 cua chaser")
    ap.add_argument("--target-connect", default="tcp:127.0.0.1:5762",
                    help="SERIAL1 cua target (SERIAL0 da do target.py giu)")
    ap.add_argument("--speed", type=float, required=True, help="toc do dat cua target (m/s)")
    ap.add_argument("--alt", type=float, default=30.0)
    ap.add_argument("--range", type=float, default=15.0, dest="rng")
    ap.add_argument("--tol", type=float, default=3.0)
    ap.add_argument("--window", type=float, default=120.0)
    ap.add_argument("--tail", type=float, default=5.0, help="bay them sau cua so (s)")
    ap.add_argument("--kp", type=float, default=0.6)
    ap.add_argument("--vcl", type=float, default=12.0, help="gioi han thanh phan P (m/s)")
    ap.add_argument("--vmax", type=float, default=30.0, help="gioi han toc do lenh (m/s)")
    ap.add_argument("--safety-range", type=float, default=10.0,
                    help="nguong ngat an toan (m); tieu chi nghiem thu van la 8 m")
    ap.add_argument("--safety-back", type=float, default=10.0)
    ap.add_argument("--max-wait", type=float, default=200.0,
                    help="neu sau chung nay s sim ke tu go ma chua co cua so thi bo cuoc")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--go-file", required=True)
    ap.add_argument("--stop-file", required=True)
    a = ap.parse_args()

    ch = L.Vehicle(a.connect, "chaser", L.TARGET_HOME)   # goc toa do chung = home cua target
    tg = L.Vehicle(a.target_connect, "tgt-link", L.TARGET_HOME)
    ch.request_gpi(20)
    tg.request_gpi(20)
    ch.arm_and_takeoff(a.alt)
    while tg.pos is None or tg.pos.alt < 0.9 * a.alt:
        tg.pump(0.5)
        ch.drain()
    L.log("chaser", "ca hai da cat canh, tao go-file")
    open(a.go_file, "w").close()

    f = open(a.csv, "w", newline="")
    w = csv.writer(f)
    w.writerow(COLS)
    t_go = None
    t_s90 = None
    t_ws = None
    safety = False
    last_print = -1e9
    idle = 0
    rc = 0
    while True:
        typ = ch.pump(2.0)
        if typ is None:
            idle += 1
            if idle > 15:
                L.log("chaser", "mat du lieu chaser > 30 s")
                rc = 3
                break
            continue
        idle = 0
        if typ != "GLOBAL_POSITION_INT":
            continue
        tg.drain()
        c, t = ch.pos, tg.pos
        if t_go is None:
            t_go = c.t
        dn, de, dz = t.n - c.n, t.e - c.e, t.alt - c.alt
        dh = math.hypot(dn, de)
        d3 = math.sqrt(dh * dh + dz * dz)
        if dh > 0.5:
            ln, le = dn / dh, de / dh
        elif t.hspeed > 0.5:
            ln, le = t.vn / t.hspeed, t.ve / t.hspeed
        else:
            ln, le = 1.0, 0.0
        # ngat an toan voi tre (hysteresis 2 m)
        if d3 < a.safety_range:
            safety = True
        elif d3 > a.safety_range + 2.0:
            safety = False
        if safety:
            u = -a.safety_back
        else:
            u = L.clamp(a.kp * (d3 - a.rng), -a.vcl, a.vcl)
        vn, ve = t.vn + u * ln, t.ve + u * le
        sp = math.hypot(vn, ve)
        if sp > a.vmax:
            vn, ve = vn * a.vmax / sp, ve * a.vmax / sp
        vd = -L.clamp(1.0 * (t.alt - c.alt), -4.0, 4.0)
        ch.send_vel(vn, ve, vd)
        w.writerow(["%.3f" % c.t, "%.3f" % t.t,
                    "%.2f" % t.n, "%.2f" % t.e, "%.2f" % t.alt,
                    "%.2f" % t.vn, "%.2f" % t.ve, "%.2f" % t.vd,
                    "%.2f" % c.n, "%.2f" % c.e, "%.2f" % c.alt,
                    "%.2f" % c.vn, "%.2f" % c.ve, "%.2f" % c.vd,
                    "%.2f" % d3, "%.2f" % dh, "%.2f" % vn, "%.2f" % ve, "%.2f" % vd,
                    int(safety), "%.2f" % a.speed])
        f.flush()
        if t_s90 is None and t.hspeed >= 0.9 * a.speed:
            t_s90 = c.t
            L.log("chaser", "target dat 90%% toc do tai t=%.1f" % c.t)
        if t_s90 is not None and t_ws is None and abs(d3 - a.rng) <= a.tol:
            t_ws = c.t
            L.log("chaser", "cua so do bat dau t=%.1f" % c.t)
        if c.t - last_print >= 10.0:
            last_print = c.t
            L.log("chaser", "t=%.0f d3=%.1f target_v=%.1f safety=%d" % (c.t, d3, t.hspeed, safety))
        if t_ws is not None and c.t >= t_ws + a.window + a.tail:
            L.log("chaser", "xong cua so do")
            break
        if t_ws is None and c.t - t_go > a.max_wait:
            L.log("chaser", "bo cuoc: khong vao cua so do sau %.0f s" % a.max_wait)
            rc = 2
            break
    f.close()
    open(a.stop_file, "w").close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
