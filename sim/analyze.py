#!/usr/bin/env python3
"""Doc CSV cua chaser.py, tinh so do va in PASS/FAIL. Exit 0 = dat het, 1 = co tieu chi FAIL/khong du du lieu.

Dinh nghia (thoi gian la thoi gian SIM tu MAVLink, cot t_sim):
  - khoang cach = 3D giua target va chaser (cot dist3d).
  - t_s90 = lan dau toc do ngang target >= 90% toc do dat.
  - t_ws  = lan dau sau t_s90 ma |dist3d - range| <= tol (chaser vao 15 +- 3 m). Cua so do = [t_ws, t_ws + window].
  - t_fly = lan dau ca hai cung co do cao >= 2 m. "Khong bao gio < 8 m" kiem tren [t_fly, het du lieu].
  - doi huong = huong di (course) cua target lech >= 30 do so voi 8 s truoc; dem so lan trong cua so.
"""
import argparse
import csv
import math
import sys


def wrap(deg):
    return (deg + 180.0) % 360.0 - 180.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--speed", type=float, help="toc do dat (mac dinh lay tu cot set_speed)")
    ap.add_argument("--range", type=float, default=15.0, dest="rng")
    ap.add_argument("--tol", type=float, default=3.0)
    ap.add_argument("--window", type=float, default=120.0)
    ap.add_argument("--mean-max", type=float, default=3.0, help="nguong sai so trung binh (m)")
    ap.add_argument("--min-range", type=float, default=8.0, help="khoang cach toi thieu cho phep (m)")
    ap.add_argument("--min-turns", type=int, default=2)
    a = ap.parse_args()

    try:
        with open(a.csv, newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        print("FAIL: khong doc duoc CSV: %s" % exc)
        return 1
    if len(rows) < 10:
        print("FAIL: CSV qua it dong (%d)" % len(rows))
        return 1

    col = lambda name: [float(r[name]) for r in rows]
    t = col("t_sim")
    d3 = col("dist3d")
    tvn, tve = col("tgt_vn"), col("tgt_ve")
    talt, calt = col("tgt_alt"), col("ch_alt")
    speed = a.speed if a.speed is not None else float(rows[0]["set_speed"])
    hs = [math.hypot(x, y) for x, y in zip(tvn, tve)]

    t_s90 = next((i for i in range(len(t)) if hs[i] >= 0.9 * speed), None)
    i_ws = None
    if t_s90 is not None:
        i_ws = next((i for i in range(t_s90, len(t)) if abs(d3[i] - a.rng) <= a.tol), None)
    i_fly = next((i for i in range(len(t)) if talt[i] >= 2.0 and calt[i] >= 2.0), None)

    ok = True
    print("=== Ket qua chase: toc do target dat %.1f m/s, file %s ===" % (speed, a.csv))
    print("Dinh nghia cua so: bat dau khi target dat >= 90%% toc do dat (%.1f m/s) VA chaser lan dau "
          "vao %.0f +- %.0f m; dai %.0f s thoi gian sim." % (0.9 * speed, a.rng, a.tol, a.window))
    print("Khong bao gio < %.0f m: kiem tren toan chuyen bay tu khi ca hai cat canh (do cao >= 2 m)."
          % a.min_range)

    if i_fly is None:
        print("FAIL: ca hai khong bao gio cung cat canh trong du lieu")
        return 1
    d_all = d3[i_fly:]
    min_all = min(d_all)
    print("Toan chuyen bay: %.1f s sim, %d mau, khoang cach min %.2f m, max %.2f m" % (
        t[-1] - t[i_fly], len(d_all), min_all, max(d_all)))
    c_min = min_all >= a.min_range
    print("[%s] khoang cach min toan chuyen bay %.2f m >= %.1f m" % (
        "PASS" if c_min else "FAIL", min_all, a.min_range))
    ok &= c_min

    if i_ws is None:
        reason = "target khong dat 90% toc do" if t_s90 is None else "chaser khong vao %.0f+-%.0f m" % (a.rng, a.tol)
        print("[FAIL] khong co cua so do: %s" % reason)
        return 1
    t_ws = t[i_ws]
    idx = [i for i in range(i_ws, len(t)) if t[i] <= t_ws + a.window]
    covered = t[idx[-1]] - t_ws
    c_len = covered >= a.window - 0.5
    print("Cua so: t_sim %.1f .. %.1f (%d mau, %.1f s)" % (t_ws, t[idx[-1]], len(idx), covered))
    print("[%s] du lieu phu du %.0f s cua so (co %.1f s)" % ("PASS" if c_len else "FAIL", a.window, covered))
    ok &= c_len

    err = [abs(d3[i] - a.rng) for i in idx]
    mean_err = sum(err) / len(err)
    rms = math.sqrt(sum(e * e for e in err) / len(err))
    dw = [d3[i] for i in idx]
    print("Trong cua so: sai so TB %.2f m, RMS %.2f m, max %.2f m; khoang cach min %.2f m, max %.2f m" % (
        mean_err, rms, max(err), min(dw), max(dw)))
    print("Toc do ngang target TB trong cua so: %.2f m/s (dat %.1f; min %.2f)" % (
        sum(hs[i] for i in idx) / len(idx), speed, min(hs[i] for i in idx)))
    c_mean = mean_err < a.mean_max
    print("[%s] sai so trung binh %.2f m < %.1f m" % ("PASS" if c_mean else "FAIL", mean_err, a.mean_max))
    ok &= c_mean

    # dem so lan doi huong cua target trong cua so
    course = [math.degrees(math.atan2(tve[i], tvn[i])) if hs[i] > 2.0 else None for i in range(len(t))]
    turns, armed, j = 0, True, 0
    for i in idx:
        if course[i] is None:
            continue
        while t[j] < t[i] - 8.0:
            j += 1
        if course[j] is None:
            continue
        diff = abs(wrap(course[i] - course[j]))
        if armed and diff >= 30.0:
            turns += 1
            armed = False
        elif diff < 10.0:
            armed = True
    c_turn = turns >= a.min_turns
    print("[%s] so lan doi huong cua target trong cua so: %d (can >= %d)" % (
        "PASS" if c_turn else "FAIL", turns, a.min_turns))
    ok &= c_turn

    saf = sum(1 for r in rows[i_ws:] if r["safety"] == "1")
    print("Thong tin: so mau ngat an toan dang bat: %d" % saf)
    print("KET QUA: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
