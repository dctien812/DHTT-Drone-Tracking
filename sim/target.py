#!/usr/bin/env python3
"""Target: cat canh, cho tin hieu go, roi bay toc do --speed voi doi huong lien tuc.

Quy dao (heading tinh tu bac, doi voi toc do khong doi): giu 20 s, sau do cu 30 s
doi huong 1 lan theo chu ky +60, -90, +90, -60 do (toc do xoay 15 do/s).
"""
import argparse
import math
import os
import sys

import chaselib as L

TURNS = [60.0, -90.0, 90.0, -60.0]


def heading_deg(t, first, period, rate):
    h = 0.0
    k = 0
    while first + k * period < t:
        d = TURNS[k % len(TURNS)]
        h += d * min(1.0, (t - (first + k * period)) / (abs(d) / rate))
        k += 1
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--connect", default="tcp:127.0.0.1:5760")
    ap.add_argument("--speed", type=float, required=True, help="toc do ngang dat (m/s)")
    ap.add_argument("--alt", type=float, default=30.0, help="do cao so voi home (m)")
    ap.add_argument("--go-file", required=True, help="cho file nay xuat hien thi moi bay")
    ap.add_argument("--stop-file", required=True, help="file nay xuat hien thi dung")
    ap.add_argument("--first-turn", type=float, default=20.0, help="s sau go den lan doi huong dau")
    ap.add_argument("--turn-period", type=float, default=30.0)
    ap.add_argument("--turn-rate", type=float, default=15.0, help="do/s")
    ap.add_argument("--max-motion", type=float, default=400.0, help="gioi han thoi gian bay (s sim)")
    a = ap.parse_args()

    v = L.Vehicle(a.connect, "target", L.TARGET_HOME)
    v.request_gpi(20)
    v.arm_and_takeoff(a.alt)
    L.log("target", "cho go-file %s" % a.go_file)
    while not os.path.exists(a.go_file):
        v.pump(0.2)

    t0 = None
    last_print = -1e9
    while not os.path.exists(a.stop_file):
        if v.pump(2.0) != "GLOBAL_POSITION_INT":
            continue
        p = v.pos
        if t0 is None:
            t0 = p.t
        t = p.t - t0
        if t > a.max_motion:
            L.log("target", "het max-motion, dung")
            break
        hd = math.radians(heading_deg(t, a.first_turn, a.turn_period, a.turn_rate))
        vd = -L.clamp(1.0 * (a.alt - p.alt), -3.0, 3.0)
        v.send_vel(a.speed * math.cos(hd), a.speed * math.sin(hd), vd)
        if t - last_print >= 10.0:
            last_print = t
            L.log("target", "t=%.0f heading=%.0f hspeed=%.1f alt=%.1f" % (
                t, math.degrees(hd), p.hspeed, p.alt))
    v.send_vel(0.0, 0.0, 0.0)
    L.log("target", "xong")


if __name__ == "__main__":
    sys.exit(main())
