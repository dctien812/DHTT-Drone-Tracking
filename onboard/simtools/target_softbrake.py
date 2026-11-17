#!/usr/bin/env python3
"""Muc tieu cho ca PHANH MEM (CHI mo phong): giong sim/target.py o che do bay thang (huong Bac),
nhung khi thay stop-file thi giam toc do LENH theo doc --decel (m/s^2) toi 0 thay vi dung phat mot.
Dung: TARGET_PY=<file nay> TARGET_DECEL=4 STRAIGHT=1 bash run_closed_loop.sh 10   (cung tham so dong lenh voi target.py)
Khong sua sim/; dung lai sim/chaselib.py.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "sim"))
import chaselib as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--connect", default="tcp:127.0.0.1:5760")
    ap.add_argument("--speed", type=float, required=True)
    ap.add_argument("--alt", type=float, default=30.0)
    ap.add_argument("--go-file", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--first-turn", type=float, default=20.0, help="bo qua (luon bay thang); giu de chung dong lenh voi target.py")
    ap.add_argument("--decel", type=float, default=float(os.environ.get("TARGET_DECEL", "4.0")))
    ap.add_argument("--max-motion", type=float, default=400.0)
    a = ap.parse_args()

    v = L.Vehicle(a.connect, "target", L.TARGET_HOME)
    v.request_gpi(20)
    v.arm_and_takeoff(a.alt)
    L.log("target", "cho go-file %s (phanh mem %.1f m/s^2)" % (a.go_file, a.decel))
    while not os.path.exists(a.go_file):
        v.pump(0.2)
    t0 = None
    t_stop = None
    last_t = None
    cmd = a.speed
    while True:
        if v.pump(2.0) != "GLOBAL_POSITION_INT":
            continue
        p = v.pos
        if t0 is None:
            t0 = p.t
        t = p.t - t0
        if t > a.max_motion:
            break
        if t_stop is None and os.path.exists(a.stop_file):
            t_stop = t
            L.log("target", "stop: giam toc do lenh %.1f m/s^2" % a.decel)
        if t_stop is not None:
            cmd = max(0.0, cmd - a.decel * (t - (t if last_t is None else last_t)))
        last_t = t
        vd = -L.clamp(1.0 * (a.alt - p.alt), -3.0, 3.0)
        v.send_vel(cmd, 0.0, vd)
        if t_stop is not None and cmd <= 0.0:
            break
    v.send_vel(0.0, 0.0, 0.0)
    L.log("target", "xong")


if __name__ == "__main__":
    sys.exit(main())
