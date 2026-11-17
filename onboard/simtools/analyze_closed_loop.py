#!/usr/bin/env python3
"""Cham diem vong kin theo VI TRI THAT (truth.csv tu SIM_STATE), KHONG dung uoc luong cua tracker.

Cua so do: bat dau khi muc tieu >= 90% toc do dat va chaser lan dau vao range +- tol (do sim_helper xac dinh,
events.json: t_ws), dai --window s.
Tieu chi (kich ban none / blackout):
  - sai so TB |d - range| < tol (3 m) trong cua so; cua so du 120 s; muc tieu doi huong >= 2 lan trong cua so
  - khoang cach that min >= 8 m tren TOAN BO du lieu (tu luc cat canh toi khi ca hai dung)
  - ty le thoi gian supervisor o TRACK >= 90% trong cua so (tu app_log.csv)
  - khoang trong du lieu truth toi da <= 0.2 s va tan so ghi >= 10 Hz
  - app thoat 0 (app.rc)
Kich ban disengage: do do tre tu lenh doi mode toi luc app ngung gui lenh (<= 0.5 s); khong cham sai so.
"""
import argparse
import csv
import json
import math
import os
import sys


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fl(r, k):
    try:
        return float(r[k])
    except (KeyError, ValueError):
        return float("nan")


def heading(vn, ve):
    return math.degrees(math.atan2(ve, vn))


def angdiff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out")
    ap.add_argument("--speed", type=float, required=True)
    ap.add_argument("--range", type=float, default=15.0, dest="rng")
    ap.add_argument("--tol", type=float, default=3.0)
    ap.add_argument("--window", type=float, default=120.0)
    a = ap.parse_args()

    truth = read_csv(os.path.join(a.out, "truth.csv"))
    ev = json.load(open(os.path.join(a.out, "events.json"))) if os.path.exists(os.path.join(a.out, "events.json")) else {}
    app = read_csv(os.path.join(a.out, "app_log.csv")) if os.path.exists(os.path.join(a.out, "app_log.csv")) else []
    app_rc = int(open(os.path.join(a.out, "app.rc")).read().strip()) if os.path.exists(os.path.join(a.out, "app.rc")) else None
    scenario = ev.get("scenario", "none")
    ok_all = True
    lines = []

    def crit(name, ok, detail):
        nonlocal ok_all
        ok_all &= bool(ok)
        lines.append("[%s] %s: %s" % ("PASS" if ok else "FAIL", name, detail))

    if len(truth) < 10:
        print("KET QUA: FAIL (truth.csv gan nhu rong)")
        return 1
    T = [fl(r, "t") for r in truth]
    D = [fl(r, "d3") for r in truth]
    dur = T[-1] - T[0]
    gaps = [T[i + 1] - T[i] for i in range(len(T) - 1)]
    lines.append("scenario=%s speed=%.0f  truth rows=%d  duration=%.1f s" % (scenario, a.speed, len(T), dur))
    crit("khoang trong truth toi da <= 0.2 s", max(gaps) <= 0.2, "max gap = %.3f s" % max(gaps))
    crit("tan so ghi truth >= 10 Hz", len(T) / max(dur, 1e-6) >= 10.0, "%.1f Hz" % (len(T) / dur))
    # khoang cach that min tren toan chuyen bay
    imin = min(range(len(D)), key=lambda i: D[i])
    lines.append("min d3 toan chuyen bay = %.2f m tai t=%.1f s (t_rel=%.1f)" % (D[imin], T[imin], T[imin] - T[0]))
    both_air = [i for i, r in enumerate(truth) if fl(r, "tgt_alt") >= 2.0 and fl(r, "ch_alt") >= 2.0]
    if both_air:
        lines.append("min d3 khi ca hai >= 2 m do cao = %.2f m" % min(D[i] for i in both_air))
    crit("khong bao gio < 8 m (toan chuyen bay)", D[imin] >= 8.0, "min = %.2f m" % D[imin])
    crit("app thoat code 0", app_rc == 0, "app.rc = %s" % app_rc)
    abort_n = sum(1 for r in app if r.get("state") == "abort")
    lines.append("so chu ky app o ABORT = %d" % abort_n)

    t_ws = ev.get("t_ws")
    if scenario == "disengage":
        td = ev.get("t_disengage_cmd")
        if td is None or not app:
            crit("do tre disengage", False, "thieu t_disengage_cmd hoac app_log")
        else:
            rows = [(float(r["t"]), int(r["sent"]), r["mode"], r["state"]) for r in app]
            before = [x for x in rows if x[0] < td]
            after = [x for x in rows if x[0] >= td]
            first_stop = next((x for x in after if x[1] == 0), None)
            last_sent = max((x[0] for x in after if x[1] == 1), default=None)
            sent_before = bool(before and before[-1][1] == 1)
            if first_stop is None or not sent_before:
                crit("do tre disengage", False, "sent_before=%s first_stop=%s" % (sent_before, first_stop))
            else:
                lat = first_stop[0] - td
                lines.append("mode quan sat o dong dau tien sent=0: %s ; lan gui cuoi sau lenh: %s" %
                             (first_stop[2], "%.3f s" % (last_sent - td) if last_sent else "khong"))
                crit("app ngung gui lenh <= 0.5 s sau lenh doi mode", lat <= 0.5 and (last_sent is None or last_sent - td <= 0.5),
                     "do tre (tick dau sent=0) = %.3f s ; lenh gui cuoi cach lenh doi mode %s" %
                     (lat, "%.3f s" % (last_sent - td) if last_sent else "n/a"))
                post = [x for x in after if x[0] > first_stop[0]]
                crit("sau disengage khong gui lai lenh nao", all(x[1] == 0 for x in post), "%d tick sau do" % len(post))
        print("\n".join(lines))
        print("KET QUA: %s" % ("PASS" if ok_all else "FAIL"))
        return 0 if ok_all else 1

    if t_ws is None:
        crit("co cua so do", False, "chaser khong vao dai %.0f +- %.0f m sau khi muc tieu dat 90%% toc do" % (a.rng, a.tol))
        print("\n".join(lines))
        print("KET QUA: FAIL")
        return 1
    w = [i for i in range(len(T)) if t_ws <= T[i] <= t_ws + a.window]
    wd = T[w[-1]] - T[w[0]] if w else 0.0
    err = [abs(D[i] - a.rng) for i in w]
    mean = sum(err) / len(err)
    rms = math.sqrt(sum(e * e for e in err) / len(err))
    mx = max(err)
    sp = [math.hypot(fl(truth[i], "tgt_vn"), fl(truth[i], "tgt_ve")) for i in w]
    lines.append("cua so: t_ws=%.1f, %d mau, dai %.1f s ; muc tieu toc do TB %.1f m/s" %
                 (t_ws, len(w), wd, sum(sp) / len(sp)))
    lines.append("sai so |d-%.0f|: TB %.2f  RMS %.2f  max %.2f m ; d3 trong cua so: min %.2f max %.2f" %
                 (a.rng, mean, rms, mx, min(D[i] for i in w), max(D[i] for i in w)))
    crit("cua so du %.0f s" % a.window, wd >= a.window - 1.0, "%.1f s" % wd)
    crit("sai so TB < %.0f m" % a.tol, mean < a.tol, "%.2f m" % mean)
    # so lan doi huong >= 30 do so voi 8 s truoc
    turns = 0
    j0 = w[0]
    last_turn_t = -1e9
    hs = [heading(fl(truth[i], "tgt_vn"), fl(truth[i], "tgt_ve")) for i in w]
    tw = [T[i] for i in w]
    k = 0
    for n in range(len(w)):
        while tw[k] < tw[n] - 8.0:
            k += 1
        if abs(angdiff(hs[n], hs[k])) >= 30.0 and tw[n] - last_turn_t > 8.0:
            turns += 1
            last_turn_t = tw[n]
    crit("muc tieu doi huong >= 2 lan trong cua so", turns >= 2, "%d lan" % turns)

    # TRACK% theo supervisor + range_valid trong cua so (app log)
    if app:
        aw = [r for r in app if t_ws <= float(r["t"]) <= t_ws + a.window]
        if aw:
            ntrack = sum(1 for r in aw if r["state"] == "track")
            ttrack = sum(1 for r in aw if r["trk_status"] == "track")
            rv0 = sum(1 for r in aw if r["range_valid"] == "0")
            coast = sum(1 for r in aw if r["state"] == "coast")
            lost = sum(1 for r in aw if r["state"] in ("lost", "search"))
            lines.append("app trong cua so: %d chu ky ; supervisor TRACK %.1f%%, COAST %.1f%%, LOST/SEARCH %.1f%% ; "
                         "tracker TRACK %.1f%% ; range_valid=False %d chu ky ; ABORT %d" %
                         (len(aw), 100.0 * ntrack / len(aw), 100.0 * coast / len(aw), 100.0 * lost / len(aw),
                          100.0 * ttrack / len(aw), rv0, sum(1 for r in aw if r["state"] == "abort")))
            crit("ty le thoi gian o TRACK >= 90%", ntrack / len(aw) >= 0.9, "%.1f%%" % (100.0 * ntrack / len(aw)))
            ld = [float(r["loop_dt"]) for r in aw]
            lines.append("chu ky app: TB %.1f ms, max %.1f ms" % (1000 * sum(ld) / len(ld), 1000 * max(ld)))
            mn = [float(r["range"]) for r in aw if r["range"] not in ("", None)]
            # sai so uoc luong khoang cach cua tracker so voi that (chi de tham khao)
            tt = [(float(r["t"]), r) for r in truth if False]
        else:
            crit("ty le thoi gian o TRACK >= 90%", False, "khong co dong app trong cua so")
    else:
        crit("ty le thoi gian o TRACK >= 90%", False, "khong co app_log.csv")
    if scenario == "blackout" and "blackout_start" in ev:
        bs, be = ev["blackout_start"], ev.get("blackout_end", ev["blackout_start"] + 3.0)
        seg = [i for i in range(len(T)) if bs <= T[i] <= be + 5.0]
        lines.append("mat hinh %.1f-%.1f: d3 min %.2f m, max %.2f m trong [mat hinh, +5 s sau]" %
                     (bs, be, min(D[i] for i in seg), max(D[i] for i in seg)))
        aseg = [r for r in app if bs <= float(r["t"]) <= be + 5.0]
        from collections import Counter
        lines.append("trang thai supervisor trong doan do: %s" % dict(Counter(r["state"] for r in aseg)))
        rtl = sum(int(r["rtl"]) for r in app)
        lines.append("so lan yeu cau RTL = %d" % rtl)
    print("\n".join(lines))
    print("KET QUA: %s" % ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
