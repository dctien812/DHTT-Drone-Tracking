#!/usr/bin/env python3
"""Muc tieu cho ca CAM XUONG + GIAM TOC HA CANH (CHI mo phong). Khong sua sim/; dung lai sim/chaselib.py.

Dien bien (huong Bac, bay thang): sau go-file bay --speed tai do cao --alt; khi thay dive-file thi DOT NGOT doi vector
van toc sang huong cam xuong goc --dive-deg (giu NGUYEN toc do 3D = --speed: ngang = speed*cos, xuong = speed*sin),
cho toi khi con cach do cao dich --alt - --dive-drop chung quang phanh (vd^2 / (2*2 m/s^2)) thi vuot len bay bang
(luat P nhu target.py, toc do ngang tro lai --speed). Khi thay stop-file: giam toc do ngang theo --decel (m/s^2, mac dinh
1.5, kieu chuan bi ha canh, KHONG phanh gap) toi 0, giu do cao, roi dung.

Gioi han thuc te cua SITL muc tieu (da do doi chieu): sim/run_sitl.sh nap Tools/autotest/models/freestyle.param co
WP_SPD_DN=5.0 m/s, WP_ACC_Z=3.0 m/s^2, WP_SPD_UP=5.0 m/s (guided velocity bi cat theo cac tham so nay), nen toc do xuong
toi da 5 m/s: voi speed 10 m/s thi goc toi da asin(5/10)=30 do. Script tu choi vd > 5 m/s (--max-vd) thay vi de FC am tham cat.
Chaser (guidance.descend_max_mps = 4 m/s) cung bi gioi han rieng: goc 25 do voi 10 m/s -> vd 4.23 m/s > 4 la ca co chu y.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "sim"))
import chaselib as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--connect", default="tcp:127.0.0.1:5760")
    ap.add_argument("--speed", type=float, required=True, help="toc do 3D (m/s)")
    ap.add_argument("--alt", type=float, default=70.0, help="do cao hanh trinh (m so voi home)")
    ap.add_argument("--go-file", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--dive-file", required=True, help="xuat hien thi bat dau cam xuong")
    ap.add_argument("--dive-deg", type=float, default=float(os.environ.get("DIVE_DEG", "15")))
    ap.add_argument("--dive-drop", type=float, default=float(os.environ.get("DIVE_DROP", "40")), help="do cao ha xuong (m)")
    ap.add_argument("--first-turn", type=float, default=20.0, help="bo qua (luon bay thang); giu de chung dong lenh voi target.py")
    ap.add_argument("--decel", type=float, default=float(os.environ.get("TARGET_DECEL", "1.5")))
    ap.add_argument("--max-vd", type=float, default=5.0, help="tran toc do xuong cua SITL muc tieu (WP_SPD_DN)")
    ap.add_argument("--max-motion", type=float, default=400.0)
    a = ap.parse_args()

    vd_dive = a.speed * math.sin(math.radians(a.dive_deg))
    vh_dive = a.speed * math.cos(math.radians(a.dive_deg))
    if not 0.0 < a.dive_deg < 90.0 or vd_dive > a.max_vd:
        L.log("target", "goc cam %.1f do cho vd %.2f m/s > %.1f m/s (WP_SPD_DN): tu choi" % (a.dive_deg, vd_dive, a.max_vd))
        return 2
    alt_end = a.alt - a.dive_drop
    pullout = vd_dive * vd_dive / (2.0 * 2.0)

    v = L.Vehicle(a.connect, "target", L.TARGET_HOME)
    v.request_gpi(20)
    v.arm_and_takeoff(a.alt)
    L.log("target", "cho go-file %s (cam %.0f do, vd %.2f, ha %.0f m toi %.0f m; giam toc %.1f m/s^2)" % (
        a.go_file, a.dive_deg, vd_dive, a.dive_drop, alt_end, a.decel))
    while not os.path.exists(a.go_file):
        v.pump(0.2)
    t0 = None
    t_stop = None
    last_t = None
    cmd = a.speed
    diving = False
    leveled = False
    last_print = -1e9
    while True:
        if v.pump(2.0) != "GLOBAL_POSITION_INT":
            continue
        p = v.pos
        if t0 is None:
            t0 = p.t
        t = p.t - t0
        if t > a.max_motion:
            L.log("target", "het max-motion, dung")
            break
        if not diving and os.path.exists(a.dive_file):
            diving = True
            L.log("target", "t=%.1f BAT DAU CAM: vn %.2f vd %.2f alt %.1f" % (t, vh_dive, vd_dive, p.alt))
        if diving and not leveled and p.alt - alt_end <= pullout:
            leveled = True
            L.log("target", "t=%.1f vuot len bay bang: alt %.1f vd %.2f" % (t, p.alt, p.vd))
        if t_stop is None and os.path.exists(a.stop_file):
            t_stop = t
            L.log("target", "stop: giam toc do lenh %.1f m/s^2" % a.decel)
        if t_stop is not None:
            cmd = max(0.0, cmd - a.decel * (t - (t if last_t is None else last_t)))
        last_t = t
        if diving and not leveled:
            vn, vd = vh_dive, vd_dive
            if t_stop is not None:
                vn = min(vn, cmd)
        else:
            vn = cmd
            vd = -L.clamp(1.0 * ((alt_end if diving else a.alt) - p.alt), -3.0, 3.0)
        v.send_vel(vn, 0.0, vd)
        if t - last_print >= 10.0:
            last_print = t
            L.log("target", "t=%.0f hspeed=%.1f vz=%.1f alt=%.1f" % (t, p.hspeed, p.vd, p.alt))
        if t_stop is not None and cmd <= 0.0:
            break
    v.send_vel(0.0, 0.0, 0.0)
    L.log("target", "xong")
    return 0


if __name__ == "__main__":
    sys.exit(main())
