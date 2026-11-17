#!/usr/bin/env python3
"""Cham diem vong kin theo VI TRI THAT (truth.csv tu SIM_STATE), KHONG dung uoc luong cua tracker.

Cua so do: bat dau khi muc tieu >= 90% toc do dat va chaser lan dau vao range +- tol (do sim_helper xac dinh,
events.json: t_ws), dai --window s.
Tieu chi (kich ban none / blackout):
  - sai so TB |d - range| < tol (3 m) trong cua so; cua so du 120 s; muc tieu doi huong >= 2 lan trong cua so
  - khoang cach that min >= 8 m tren TOAN BO du lieu (tu luc cat canh toi khi ca hai dung)
  - ty le thoi gian supervisor o TRACK >= 90% trong cua so (tu app_log.csv)
  - khoang trong du lieu truth toi da <= 0.2 s CHI trong cua so do (toan chuyen chi in tham khao), tan so ghi >= 10 Hz
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

def b4_metrics(a, truth, app, ev, scenario):
    """Do dac B4 (khong anh huong PASS/FAIL): hinh hoc camera tu truth + app_cfg.json (fx, tilt, khop gat).
    In cac dong 'B4 ...' va mot dong 'B4JSON {...}'."""
    import statistics
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import numpy as np
    from dtrack.geometry import quat_from_euler, quat_to_matrix
    from dtrack.config import make_camera
    from simtools.gimbal_model import GimbalModel
    cfgp = os.path.join(a.out, "app_cfg.json")
    cam = {}
    if os.path.exists(cfgp):
        try:
            cam = json.load(open(cfgp)).get("camera", {})
        except ValueError:
            cam = {}
    fx = float(cam.get("fx", 1739.0)); tilt = float(cam.get("tilt_up_deg", 15.0))
    W, H = int(cam.get("width", 1456)), int(cam.get("height", 1088))
    gm = GimbalModel(cam.get("gimbal_travel_deg", 50.0), cam.get("gimbal_rate_dps", 300.0),
                     cam.get("gimbal_lag_s", 0.05)) if cam.get("gimbal_enabled") else None
    Rbc = np.array(make_camera(tilt, fx, fx, W, H).R_body_cam)
    T = np.array([fl(r, "t") for r in truth])
    col = lambda k: np.array([fl(r, k) for r in truth])
    u = np.stack([col("tgt_n") - col("ch_n"), col("tgt_e") - col("ch_e"), -(col("tgt_alt") - col("ch_alt"))], 1)
    D = col("d3")
    spd = np.hypot(col("tgt_vn"), col("tgt_ve"))
    rr, pp, yy = col("ch_roll"), col("ch_pitch"), col("ch_yaw")
    n = len(T)
    out_of = np.zeros(n, bool); ang = np.zeros(n); delta = np.zeros(n)
    for i in range(n):
        qb = quat_from_euler(rr[i], pp[i], yy[i])
        Rb = quat_to_matrix(qb)
        qc = qb
        if gm is not None:
            qc, delta[i] = gm.step(T[i], tuple(qb))
        ray = (quat_to_matrix(qc) @ Rbc).T @ u[i]
        if ray[2] <= 1e-6:
            out_of[i] = True
        else:
            px, py = fx * ray[0] / ray[2] + W / 2.0, fx * ray[1] / ray[2] + H / 2.0
            out_of[i] = not (0.0 <= px <= W and 0.0 <= py <= H)
        un = u[i] / max(np.linalg.norm(u[i]), 1e-9)
        ang[i] = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(Rb @ np.array([0.0, 0.0, -1.0]), un))))))
    t_go = ev.get("t_go")
    t_stop = ev.get("t_stop_target")
    t_end = ev.get("t_both_stopped") or T[-1]
    if t_go is None or t_stop is None:
        return ["B4 thieu t_go/t_stop_target: bo qua"]
    i90 = np.where((T >= t_go) & (spd >= 0.9 * a.speed))[0]
    t90 = T[i90[0]] if len(i90) else t_stop
    phases = {"tang_toc": (t_go, t90), "bam_on_dinh": (t90, t_stop), "phanh_cuoi": (t_stop, t_end)}
    res = {"fx": fx, "tilt": tilt, "gimbal": bool(gm), "range": a.rng, "speed": a.speed, "scenario": scenario}
    lines = ["B4 camera: fx=%.0f px (FOV ngang %.0f, doc %.0f do), tilt=%.0f, khop gat=%s" % (
        fx, 2 * math.degrees(math.atan(W / 2 / fx)), 2 * math.degrees(math.atan(H / 2 / fx)), tilt, "co" if gm else "khong")]
    for name, (ta, tb) in phases.items():
        m = (T >= ta) & (T <= tb)
        if not m.any():
            continue
        j = np.where(m)[0][np.argmin(D[m])]
        oo = out_of[m]
        trans = int(np.sum(oo[1:] & ~oo[:-1])) + int(oo[0])
        dts = np.diff(T[m], append=T[m][-1])
        out_t = float(np.sum(dts[oo]))
        res[name] = {"dur": float(tb - ta), "min_d3": float(D[j]), "min_t_rel": float(T[j] - T[0]), "out_n": trans,
                     "out_s": out_t, "ang_min": float(ang[m].min()), "ang_med": float(np.median(ang[m])),
                     "ang_max": float(ang[m].max())}
        r = res[name]
        lines.append("B4 pha %-11s %5.1fs: min d3 %.2f m (t_rel %.1f) ; ra khoi khung %d lan / %.2f s ; "
                     "goc(truc day than, huong nhin) min/trung vi/max = %.0f/%.0f/%.0f do" % (
                         name, r["dur"], r["min_d3"], r["min_t_rel"], r["out_n"], r["out_s"], r["ang_min"], r["ang_med"], r["ang_max"]))
    m = (T >= t_go) & (T <= t_end)
    oo = out_of[m]
    dts = np.diff(T[m], append=T[m][-1])
    res["out_total_n"] = int(np.sum(oo[1:] & ~oo[:-1])) + int(oo[0]); res["out_total_s"] = float(np.sum(dts[oo]))
    lines.append("B4 ra khoi khung toan chuyen (t_go..dung): %d lan, %.2f s" % (res["out_total_n"], res["out_total_s"]))
    if gm is not None:
        rate = np.abs(np.diff(delta)) / np.maximum(np.diff(T), 1e-6)
        res["gimbal"] = {"delta_min": math.degrees(delta.min()), "delta_max": math.degrees(delta.max()),
                         "rate_max": math.degrees(float(rate.max()))}
        lines.append("B4 khop gat: hanh trinh dung %.1f..%.1f do (so voi danh dinh), toc do quay max %.0f do/s" % (
            res["gimbal"]["delta_min"], res["gimbal"]["delta_max"], res["gimbal"]["rate_max"]))
    t_ws = ev.get("t_ws")
    if t_ws is not None:
        w = (T >= t_ws) & (T <= t_ws + a.window)
        size = fx * 0.30 / D[w]
        res["size_px_med"] = float(np.median(size))
        lines.append("B4 kich thuoc muc tieu trong cua so (truth): trung vi %.1f px (RANGE %.0f)" % (res["size_px_med"], a.rng))
        errs = []
        for r in app:
            try:
                ta_ = float(r["t"])
                if t_ws <= ta_ <= t_ws + a.window and r["range_valid"] == "1" and r["range"] not in ("", None):
                    errs.append(float(r["range"]) - float(np.interp(ta_, T, D)))
            except (KeyError, ValueError):
                pass
        if errs:
            res["range_err"] = {"n": len(errs), "mean": float(np.mean(errs)), "abs_mean": float(np.mean(np.abs(errs))),
                                "rms": float(math.sqrt(np.mean(np.square(errs))))}
            lines.append("B4 sai so uoc luong khoang cach khi range_valid (%d mau): TB %.2f, |TB| %.2f, RMS %.2f m" % (
                len(errs), res["range_err"]["mean"], res["range_err"]["abs_mean"], res["range_err"]["rms"]))
    lines.append("B4JSON " + json.dumps(res))
    return lines

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
    lines.append("khoang trong truth TOAN chuyen (tham khao, khong chan): max %.3f s" % max(gaps))
    t_ws0 = ev.get("t_ws")
    if scenario == "disengage" or t_ws0 is None:
        crit("khoang trong truth toi da <= 0.2 s", max(gaps) <= 0.2, "max gap = %.3f s (toan chuyen)" % max(gaps))
    else:
        # nguoi dung quyet: nguong 0.2 s CHI ap trong cua so do (pha ket noi app ngoai cua so khong tinh)
        wg = [T[i + 1] - T[i] for i in range(len(T) - 1) if t_ws0 <= T[i] and T[i + 1] <= t_ws0 + a.window]
        crit("khoang trong truth toi da <= 0.2 s (trong cua so do)", (max(wg) if wg else float("inf")) <= 0.2,
             "max gap trong cua so = %.3f s" % (max(wg) if wg else float("nan")))
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
    if ev.get("straight"):
        lines.append("muc tieu bay thang: bo tieu chi doi huong (%d lan quan sat)" % turns)
    else:
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
    try:
        lines.extend(b4_metrics(a, truth, app, ev, scenario))
    except Exception as exc:     # do dac B4 khong duoc lam hong ket qua chinh
        lines.append("B4 loi: %r" % (exc,))
    print("\n".join(lines))
    print("KET QUA: %s" % ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
