#!/usr/bin/env python3
"""Phep thu bac dap ung van toc cua FC (SITL, GUIDED): lenh van toc ngang nhay bac, ghi van toc that (SIM_STATE).
Chay qua fc_step_test.sh (khoi 1 SITL). Ket qua: <out>/steps.csv va in tom tat: tre thuan, hang so thoi gian 63%,
gia toc phanh that (trung binh 10-90% va dinh). CHI mo phong."""
import argparse
import csv
import math
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from simtools.sim_helper import Conn, GUIDED  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--alt", type=float, default=30.0)
    ap.add_argument("--hold", type=float, default=9.0)
    a = ap.parse_args()
    host, port = "127.0.0.1", 5770
    t0 = time.monotonic()
    while True:
        try:
            s = socket.create_connection((host, port), timeout=5); time.sleep(1.0); s.close(); break
        except OSError:
            if time.monotonic() - t0 > 240: raise
            time.sleep(1)
    ch = Conn("tcp:127.0.0.1:5772", "chaser")
    last = 0.0
    while not (ch.armed and ch.mode == GUIDED):
        ch.pump()
        if time.monotonic() - last > 3.0:
            last = time.monotonic(); ch.cmd(176, 1, GUIDED); ch.cmd(400, 1)
        time.sleep(0.02)
    last = 0.0
    while ch.sim is None or ch.sim[3] < 584.0 + 0.95 * a.alt:
        ch.pump()
        if time.monotonic() - last > 3.0 and (ch.sim is None or ch.sim[3] - 584.0 < 1.0):
            last = time.monotonic(); ch.cmd(22, 0, 0, 0, 0, 0, 0, a.alt)
        time.sleep(0.02)
    time.sleep(5.0)
    seq = [0.0, 5.0, 10.0, 5.0, 0.0, 10.0, 0.0]
    rows = []
    def send(v):
        ch.mav.mav.set_position_target_local_ned_send(0, ch.mav.target_system, ch.mav.target_component, 1, 3527,
                                                      0, 0, 0, v, 0, 0, 0, 0, 0, 0, 0)
    steps = []
    for k, v in enumerate(seq):
        t_step = time.monotonic()
        steps.append((t_step, v, seq[k - 1] if k else 0.0))
        t_end = t_step + a.hold
        while time.monotonic() < t_end:
            send(v); ch.pump()
            if ch.sim: rows.append((ch.sim[0], v, ch.sim[4], ch.sim[5]))
            time.sleep(0.02)
    send(0.0)
    with open(os.path.join(a.out, "steps.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["t", "cmd_vn", "vn", "ve"]); w.writerows(rows)
    print("RESULT step: v0->v1 | tre_thuan(s) | tau63(s) | gia_toc_TB_10-90%(m/s2) | gia_toc_dinh(m/s2)")
    for (ts, v1, v0) in steps[1:]:
        seg = [(t, vn) for (t, c, vn, ve) in rows if ts <= t <= ts + a.hold - 0.5]
        if not seg or v1 == v0: continue
        dv = v1 - v0
        frac = [(t - ts, (vn - v0) / dv) for t, vn in seg]
        dead = next((t for t, f in frac if f >= 0.05), float("nan"))
        t63 = next((t for t, f in frac if f >= 0.632), float("nan"))
        t10 = next((t for t, f in frac if f >= 0.1), float("nan")); t90 = next((t for t, f in frac if f >= 0.9), float("nan"))
        acc_mean = abs(0.8 * dv) / (t90 - t10) if t90 == t90 and t10 == t10 and t90 > t10 else float("nan")
        peak = 0.0
        for i in range(5, len(seg)):
            peak = max(peak, abs((seg[i][1] - seg[i - 5][1]) / max(seg[i][0] - seg[i - 5][0], 1e-6)))
        print("RESULT %4.0f->%4.0f | %.2f | %.2f | %.2f | %.2f" % (v0, v1, dead, t63, acc_mean, peak))


if __name__ == "__main__":
    main()