#!/usr/bin/env python3
"""Cham diem vong kin theo VI TRI THAT (truth.csv tu SIM_STATE), KHONG dung uoc luong cua tracker.

Cua so do: bat dau khi muc tieu >= 90% toc do dat va chaser lan dau vao range +- tol (do sim_helper xac dinh,
events.json: t_ws), dai --window s.
Tieu chi (kich ban none / blackout):
  - sai so TB |d - range| < tol (3 m) trong cua so; cua so du 120 s; muc tieu doi huong >= 2 lan trong cua so
  - khoang cach that min >= acceptance.hard_floor_m (app_cfg.json; thieu thi 8 m) tren TOAN BO du lieu (tu luc cat canh toi khi ca hai dung)
  - ty le thoi gian supervisor o TRACK >= 90% trong cua so (tu app_log.csv)
  - khoang trong du lieu truth toi da <= 0.2 s CHI trong cua so do (toan chuyen chi in tham khao), tan so ghi >= 10 Hz
  - app thoat 0 (app.rc)
Kich ban disengage: do do tre tu lenh doi mode toi luc app ngung gui lenh (<= 0.5 s); khong cham sai so.
Ca CAM XUONG (events.json co t_dive_cmd; xem docs/scenario_dive.md) cham THEM:
  - events.json phai du t_go, t_dive_cmd, t_stop_target, dive_deg, dive_drop_m va both_stopped=true (thieu/false -> FAIL)
  - muc tieu thuc su ha >= 0.8 * dive_drop_m (SITL muc tieu khong am tham cat toc do xuong) VA toc do ha dinh >= 0.8 * speed*sin(dive_deg)
  - pha cam (t_dive .. het cam + --dive-after s): d3 min >= range_min (--range-min, else acceptance.dive_range_min_m, else guidance.range_min_m cua app_cfg.json, else 12.5 m), d3 max <= --dmax (40 m) tinh tu
    luc cam toi luc target stop; muc tieu ra khoi khung tong <= --out-max s (2 s); pha bay bang (het pha cam .. stop) cung <= --out-max
    (bao ca khoang lien tuc dai nhat va tong tu lenh cam toi het chuyen)
  - do cao chaser >= san an toan (config min_alt_m - 1 m) VA >= (do cao dich cua muc tieu sau cam - --alt-margin 10 m),
    tu luc cam toi het chuyen. In them (khong cham) d3 max doan bay deu truoc lenh cam
  - pha giam toc cuoi (t_stop_target .. dung): d3 min >= range_min, d3 max <= --dmax, ra khoi khung <= --out-max s
Ca khong cam (target.py / target_softbrake.py): pha phanh cuoi chi IN cac so tren (khong cham) tru khi co --score-final.
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


NUM_COLS = ["t", "tgt_n", "tgt_e", "tgt_alt", "tgt_vn", "tgt_ve", "tgt_vd", "ch_n", "ch_e", "ch_alt",
            "ch_roll", "ch_pitch", "ch_yaw", "d3"]


def drop_bad_rows(truth):
    """Bo dong truth.csv thieu/khong doc duoc gia tri so (fl -> NaN lam sai min/max/trung vi). Tra (dong tot, so dong bo)."""
    if not truth:
        return truth, 0
    cols = [c for c in NUM_COLS if c in truth[0]]
    good = [r for r in truth if all(math.isfinite(fl(r, c)) for c in cols)]
    return good, len(truth) - len(good)


def dive_times(truth, ev):
    """(t_dive, t_dive_end) cua ca cam xuong; t_dive_end = lan dau sau dinh toc do xuong ma tgt_vd < 0.5 m/s (None neu khong thay)."""
    td = ev.get("t_dive_cmd")
    if td is None:
        return None, None
    ts = ev.get("t_stop_target")
    rows = [(fl(r, "t"), fl(r, "tgt_vd")) for r in truth if fl(r, "t") >= td and (ts is None or fl(r, "t") <= ts)]
    if not rows:
        return td, None
    k = max(range(len(rows)), key=lambda i: rows[i][1])
    for t, vd in rows[k:]:
        if vd < 0.5:
            return td, t
    return td, None


def longest_run(oo, dts):
    """Thoi gian lien tuc dai nhat (s) ma co oo[i] la True, moi mau chiem dts[i] s."""
    best = cur = 0.0
    for o, d in zip(oo, dts):
        cur = cur + float(d) if o else 0.0
        best = max(best, cur)
    return best


def b4_metrics(a, truth, app, ev, scenario, res_out=None):
    """Do dac B4 (khong anh huong PASS/FAIL): hinh hoc camera tu truth + app_cfg.json (fx, tilt, khop gat).
    In cac dong 'B4 ...' va mot dong 'B4JSON {...}'."""
    import statistics
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import numpy as np
    from dtrack.geometry import quat_from_euler, quat_to_matrix
    from dtrack.config import make_camera
    from dtrack.gimbal import camera_attitude
    from simtools.gimbal_model import GimbalModel
    cfgp = os.path.join(a.out, "app_cfg.json")
    cam, shape = {}, {}
    if os.path.exists(cfgp):
        try:
            jc = json.load(open(cfgp))
            cam, shape = jc.get("camera", {}), jc.get("target_shape", {})
        except ValueError:
            cam = {}
    span = float(shape.get("span_m", 0.30))      # = TargetShapeConfig.span_m (kich thuoc ma bo uoc luong dung)
    fx = float(cam.get("fx", 1739.0)); tilt = float(cam.get("tilt_up_deg", 15.0))
    W, H = int(cam.get("width", 1456)), int(cam.get("height", 1088))
    gm = GimbalModel(cam.get("gimbal_travel_deg", 50.0), cam.get("gimbal_rate_dps", 300.0),
                     cam.get("gimbal_lag_s", 0.05)) if cam.get("gimbal_enabled") else None
    gact = cfg_gimbal_enabled(a.out)      # khop gat chu dong: doc goc THAT tu gimbal.csv, bo qua camera.tilt_up_deg
    if gact:
        gm, tilt = None, 0.0
    Rbc = np.array(make_camera(0.0 if gact else tilt, fx, fx, W, H).R_body_cam)
    T = np.array([fl(r, "t") for r in truth])
    if gact:
        tg, dg, sg = gimbal_series(a, T, ev)
        dint = np.interp(T, tg, dg)
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
        elif gact:
            qc = camera_attitude(qb, float(dint[i]))
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
    t_dive, t_dive_end = dive_times(truth, ev)
    if t_dive is not None:     # ca cam xuong: tach pha cam (+ dive_after s sau cam), bay bang, giam toc cuoi
        t_cut = min((t_dive_end if t_dive_end is not None else t_stop) + a.dive_after, t_stop)
        phases = {"tang_toc": (t_go, t90), "bam_on_dinh": (t90, t_dive), "cam_xuong": (t_dive, t_cut),
                  "bay_bang": (t_cut, t_stop), "giam_toc_cuoi": (t_stop, t_end)}
    else:
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
        res[name] = {"dur": float(tb - ta), "min_d3": float(D[j]), "max_d3": float(D[m].max()), "min_t_rel": float(T[j] - T[0]), "out_n": trans,
                     "out_s": out_t, "out_run_s": longest_run(oo, dts), "ang_min": float(ang[m].min()), "ang_med": float(np.median(ang[m])),
                     "ang_max": float(ang[m].max())}
        r = res[name]
        lines.append("B4 pha %-13s %5.1fs: min d3 %.2f m (t_rel %.1f) max d3 %.2f m ; ra khoi khung %d lan / %.2f s (lien tuc dai nhat %.2f s) ; "
                     "goc(truc day than, huong nhin) min/trung vi/max = %.0f/%.0f/%.0f do" % (
                         name, r["dur"], r["min_d3"], r["min_t_rel"], r["max_d3"], r["out_n"], r["out_s"], r["out_run_s"],
                         r["ang_min"], r["ang_med"], r["ang_max"]))
    if t_dive is not None:     # ca cam: ra khoi khung tren TOAN khoang tu lenh cam den het chuyen (chi bao, tung pha da cham)
        m = (T >= t_dive) & (T <= t_end)
        if m.any():
            oo = out_of[m]
            dts = np.diff(T[m], append=T[m][-1])
            res["cam_den_het"] = {"out_s": float(np.sum(dts[oo])), "out_run_s": longest_run(oo, dts)}
            lines.append("B4 ra khoi khung tu lenh cam toi het chuyen: tong %.2f s, lien tuc dai nhat %.2f s" % (
                res["cam_den_het"]["out_s"], res["cam_den_het"]["out_run_s"]))
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
    if gact:
        mg = (T >= t_go) & (T <= t_end)
        theta = -np.degrees(pp)
        dd = np.degrees(dint)
        sat = sg[np.clip(np.searchsorted((tg[:-1] + tg[1:]) / 2.0, T), 0, len(tg) - 1)]    # mau gimbal.csv gan nhat
        sm = sat[mg]
        rate = np.abs(np.diff(dd[mg])) / np.maximum(np.diff(T[mg]), 1e-6)
        gph = {}
        for name, (ta, tb) in phases.items():
            m = (T >= ta) & (T <= tb)
            if m.any():
                gph[name] = {"delta_med": float(np.median(dd[m])), "delta_min": float(dd[m].min()), "delta_max": float(dd[m].max()),
                             "theta_med": float(np.median(theta[m])), "theta_max": float(theta[m].max()), "spd_med": float(np.median(spd[m]))}
        res["gimbal"] = {"delta_min": float(dd[mg].min()), "delta_max": float(dd[mg].max()), "delta_med": float(np.median(dd[mg])),
                         "rate_max": float(rate.max()) if len(rate) else 0.0,
                         "n_sat_enter": int(np.sum(sm[1:] & ~sm[:-1])) + int(sm[0]), "n_sat": int(sm.sum()), "phases": gph}
        g = res["gimbal"]
        lines.append("B4 khop gat (chu dong): delta that %.1f..%.1f do (trung vi %.1f), toc do quay max %.0f do/s, cham gioi han %d lan / %d mau" % (
            g["delta_min"], g["delta_max"], g["delta_med"], g["rate_max"], g["n_sat_enter"], g["n_sat"]))
    t_ws = ev.get("t_ws")
    if t_ws is not None:
        w = (T >= t_ws) & (T <= t_ws + a.window)
        size = fx * span / D[w]
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
    if res_out is not None:
        res_out.update(res)
    return lines

def load_gimbal_csv(path):
    """gimbal.csv -> (t [s], delta_act [rad], sat [bool]). Nem ValueError/OSError khi thieu file/cot t, delta_act_deg, co NaN, t khong tang chat."""
    rows = read_csv(path)
    if len(rows) > 1 and None in rows[-1].values():     # dong cuoi bi cat do (app bi giet khi chua flush): bo
        rows = rows[:-1]
    if not rows or "t" not in rows[0] or "delta_act_deg" not in rows[0]:
        raise ValueError("gimbal.csv rong hoac thieu cot t/delta_act_deg: %s" % path)
    t = [float(r["t"]) for r in rows]
    d = [float(r["delta_act_deg"]) for r in rows]
    if not (all(math.isfinite(x) for x in t) and all(math.isfinite(x) for x in d)):
        raise ValueError("gimbal.csv co gia tri NaN/inf")
    if any(t[i + 1] <= t[i] for i in range(len(t) - 1)):
        raise ValueError("gimbal.csv: t khong tang chat")
    sat = [bool(int(float(r["sat"]))) for r in rows] if "sat" in rows[0] else [False] * len(rows)
    import numpy as np
    return np.array(t), np.radians(np.array(d)), np.array(sat, bool)


def cfg_gimbal_enabled(out):
    """app_cfg.json (JSON thua) co gimbal.enabled truthy."""
    try:
        return bool(json.load(open(os.path.join(out, "app_cfg.json"))).get("gimbal", {}).get("enabled"))
    except (OSError, ValueError, AttributeError):
        return False


def gimbal_series(a, T, ev):
    """load_gimbal_csv(out/gimbal.csv) + kiem do phu thoi gian: > 2% mau truth trong [t_go, t_end] ngoai file -> ValueError."""
    import numpy as np
    tg, dg, sg = load_gimbal_csv(os.path.join(a.out, "gimbal.csv"))
    t_go = ev.get("t_go")
    if t_go is not None:
        t_end = ev.get("t_both_stopped") or T[-1]
        m = (T >= t_go) & (T <= t_end)
        if m.any():
            Tm = T[m]
            k = np.clip(np.searchsorted(tg, Tm), 1, max(len(tg) - 1, 1))     # Tm trong (tg[k-1], tg[k]]
            lo, hi = tg[np.maximum(k - 1, 0)], tg[k]
            on_row = (np.abs(Tm - lo) <= 1e-6) | (np.abs(Tm - hi) <= 1e-6)
            covered = (Tm >= tg[0] - 1e-6) & (Tm <= tg[-1] + 1e-6) & (on_row | (hi - lo <= 0.5 + 1e-9))
            miss = float(np.mean(~covered))
            if miss > 0.02:
                raise ValueError("gimbal.csv khong phu %.1f%% mau truth trong [t_go, t_end] (ngoai file [%.2f, %.2f] s hoac lo > 0.5 s)" % (
                    100 * miss, tg[0], tg[-1]))
    return tg, dg, sg


def cfg_guidance(out, key, fallback_attr):
    """Gia tri guidance.<key> tu app_cfg.json (neu co), khong co thi mac dinh GuidanceConfig trong dtrack.config."""
    try:
        v = json.load(open(os.path.join(out, "app_cfg.json"))).get("guidance", {}).get(key)
        if v is not None:
            return float(v)
    except (OSError, ValueError):
        pass
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from dtrack.config import GuidanceConfig
    return float(getattr(GuidanceConfig(), fallback_attr))


def cfg_acceptance(out, key):
    """Gia tri acceptance.<key> tu app_cfg.json (JSON thua), khong co thi None."""
    try:
        v = json.load(open(os.path.join(out, "app_cfg.json"))).get("acceptance", {}).get(key)
        return None if v is None else float(v)
    except (OSError, ValueError):
        return None


def dive_and_final_scoring(a, truth, T, D, ev, b4res, crit, lines):
    """Cham pha cam xuong (neu co t_dive_cmd) va pha giam toc/phanh cuoi. Xem docstring dau file."""
    t_dive, t_dive_end = dive_times(truth, ev)
    t_stop, t_end = ev.get("t_stop_target"), ev.get("t_both_stopped") or T[-1]
    dive_run = (ev.get("dive_deg") or 0) > 0 or "t_dive_cmd" in ev or (a.expect_dive or 0) > 0   # cam xuong theo events.json HOAC theo nguoi goi (--expect-dive)
    if dive_run:
        missing = [k for k in ("t_go", "t_dive_cmd", "t_stop_target", "dive_deg", "dive_drop_m") if ev.get(k) is None]
        if missing:
            crit("ca cam xuong: events.json du moc de cham", False, "thieu/rong: %s" % ", ".join(missing))
            return
    if t_stop is None:
        return
    spd = float(ev["speed"]) if ev.get("speed") is not None else a.speed     # toc do da luu trong events.json uu tien hon --speed
    rmin = a.range_min
    if rmin is None:
        rmin = cfg_acceptance(a.out, "dive_range_min_m")
    if rmin is None:
        rmin = cfg_guidance(a.out, "range_min_m", "range_min_m")
    floor = a.alt_floor if a.alt_floor is not None else cfg_guidance(a.out, "min_alt_m", "min_alt_m") - 1.0
    if t_dive is not None:
        crit("hai may dung han o cuoi chuyen (both_stopped)", ev.get("both_stopped") is True,
             "both_stopped = %s" % ev.get("both_stopped"))
        ws = [D[i] for i in range(len(T)) if ev.get("t_ws") is not None and ev["t_ws"] <= T[i] < t_dive]
        if ws:
            lines.append("[tham khao] d3 max doan bay deu truoc lenh cam (t_ws..lenh cam): %.2f m (doi chieu nguong %.0f m)" % (max(ws), a.dmax))
        talt = [(T[i], fl(truth[i], "tgt_alt"), fl(truth[i], "tgt_vd")) for i in range(len(T)) if t_dive <= T[i] <= t_stop]
        if talt:
            drop = talt[0][1] - min(x[1] for x in talt)
            vdp = max(x[2] for x in talt)
            lines.append("cu cam: lenh luc t=%.1f, het cam t=%s ; muc tieu ha %.1f m, toc do xuong max %.2f m/s (goc ~ %.0f do voi %.0f m/s)" % (
                t_dive, ("%.1f" % t_dive_end) if t_dive_end is not None else "?", drop, vdp,
                math.degrees(math.asin(min(1.0, vdp / max(spd, 1e-6)))), spd))
            need = 0.8 * float(ev.get("dive_drop_m", 25.0))
            crit("muc tieu thuc su cam xuong (ha >= %.0f m)" % need, drop >= need, "ha %.1f m" % drop)
            cap = 1.3 * float(ev["dive_drop_m"])
            crit("muc tieu khong cam qua sau (ha <= %.0f m = 1.3 * dive_drop_m)" % cap, drop <= cap, "ha %.1f m" % drop)
            vneed = 0.8 * spd * math.sin(math.radians(float(ev["dive_deg"])))
            crit("toc do ha dinh cua muc tieu >= %.2f m/s (80%% cua %.0f*sin(%.0f do))" % (vneed, spd, float(ev["dive_deg"])),
                 vdp >= vneed, "dinh %.2f m/s" % vdp)
            tgt_end_alt = talt[0][1] - float(ev["dive_drop_m"])      # do cao dich DANH DINH (do cao luc lenh cam - dive_drop_m), khong phai diem thap nhat do duoc
        else:
            tgt_end_alt = None
            crit("muc tieu thuc su cam xuong", False, "khong co dong truth giua lenh cam va stop")
        seg = [i for i in range(len(T)) if t_dive <= T[i] <= t_stop]
        if seg:
            dmin, dmax = min(D[i] for i in seg), max(D[i] for i in seg)
            lines.append("d3 tu luc cam toi stop: min %.2f max %.2f m" % (dmin, dmax))
            crit("pha cam: d3 min >= range_min %.1f m" % rmin, dmin >= rmin, "min = %.2f m" % dmin)
            crit("trong va sau cu cam: d3 max <= %.0f m" % a.dmax, dmax <= a.dmax, "max = %.2f m" % dmax)
        cam = b4res.get("cam_xuong")
        if cam:
            crit("muc tieu ra khoi khung trong pha cam <= %.1f s" % a.out_max, cam["out_s"] <= a.out_max,
                 "%.2f s (%d lan, lien tuc dai nhat %.2f s)" % (cam["out_s"], cam["out_n"], cam.get("out_run_s", float("nan"))))
            bb = b4res.get("bay_bang")
            if bb:
                crit("muc tieu ra khoi khung trong pha bay bang <= %.1f s" % a.out_max, bb["out_s"] <= a.out_max,
                     "%.2f s (%d lan, lien tuc dai nhat %.2f s)" % (bb["out_s"], bb["out_n"], bb.get("out_run_s", float("nan"))))
            else:
                lines.append("pha bay bang: khong co mau truth (pha rong), khong cham ra khoi khung")
        else:
            crit("muc tieu ra khoi khung trong pha cam <= %.1f s" % a.out_max, False, "khong do duoc (B4 loi hoac pha rong)")
        seg = [i for i in range(len(T)) if t_dive <= T[i] <= t_end]
        if seg:
            amin = min(fl(truth[i], "ch_alt") for i in seg)
            crit("do cao chaser >= san %.1f m (tu luc cam toi het chuyen)" % floor, amin >= floor, "min = %.2f m" % amin)
            if tgt_end_alt is not None:
                rel = tgt_end_alt - a.alt_margin
                crit("do cao chaser >= do cao dich danh dinh sau cam - %.0f m = %.1f m" % (a.alt_margin, rel), amin >= rel,
                     "min = %.2f m (do cao dich danh dinh %.1f m)" % (amin, tgt_end_alt))
    # pha giam toc / phanh cuoi
    name = "giam_toc_cuoi" if t_dive is not None else "phanh_cuoi"
    fin = b4res.get(name)
    scored = t_dive is not None or a.score_final
    tag = "" if scored else " [tham khao, khong cham; --score-final de cham]"
    seg = [i for i in range(len(T)) if t_stop <= T[i] <= t_end]
    if not seg:
        return
    dmin, dmax = min(D[i] for i in seg), max(D[i] for i in seg)
    vs = [math.hypot(fl(truth[i], "tgt_vn"), fl(truth[i], "tgt_ve")) for i in seg]
    dec, j = float("nan"), 0
    for k in range(len(seg)):          # giam toc max do tren khoang >= 1 s (tranh nhieu mau)
        while j < len(seg) - 1 and T[seg[j]] - T[seg[k]] < 1.0:
            j += 1
        if T[seg[j]] - T[seg[k]] >= 1.0:
            d_ = (vs[k] - vs[j]) / (T[seg[j]] - T[seg[k]])
            dec = d_ if dec != dec else max(dec, d_)
    lines.append("pha giam toc cuoi (stop..dung)%s: d3 min %.2f max %.2f m ; ra khoi khung %s ; giam toc ngang muc tieu max %.1f m/s^2 (TB 1 s)" % (
        tag, dmin, dmax, ("%.2f s" % fin["out_s"]) if fin else "?", dec))

    def chk(label, ok, detail):
        if scored:
            crit(label, ok, detail)
        else:
            lines.append("[%s tham khao] %s: %s" % ("dat" if ok else "KHONG dat", label, detail))
    chk("giam toc cuoi: d3 min >= range_min %.1f m" % rmin, dmin >= rmin, "min = %.2f m" % dmin)
    chk("giam toc cuoi: d3 max <= %.0f m" % a.dmax, dmax <= a.dmax, "max = %.2f m" % dmax)
    chk("giam toc cuoi: ra khoi khung <= %.1f s" % a.out_max, bool(fin) and fin["out_s"] <= a.out_max,
        ("%.2f s" % fin["out_s"]) if fin else "khong do duoc")


def cfg_search(out):
    """(enabled, climb_m) cua muc 'search' trong app_cfg.json (JSON thua); thieu/loi -> (False, 0.0)."""
    try:
        s = json.load(open(os.path.join(out, "app_cfg.json"))).get("search", {})
        return bool(s.get("enabled")), float(s.get("climb_m") or 0.0)
    except (OSError, ValueError, AttributeError, TypeError):
        return False, 0.0


def _sf(r, k):
    """float an toan cho dong csv (o rong / None / thieu cot -> NaN)."""
    try:
        return float(r[k])
    except (KeyError, ValueError, TypeError):
        return float("nan")


def reacq_metrics(a, truth, T, D, app, search_rows, ev, crit, lines, climb_m=0.0, dist_crit=None):
    """Bo do tim lai muc tieu (.office/design-search.md muc (g), S-2). Chi goi khi search.enabled (app_cfg.json).
    search_rows = search.csv (None neu thieu -> FAIL 'khong do duoc'). Dot = cac hang co ep_s (ep_id giu nguyen sau khi dong).
    Chon dot con mo tai blackout_start (chua dong truoc do) hoac dot dau tien mo sau do.
    Moc: t_ep0 = t - ep_s (hang dau dot); bat lai CHI khi co hang dong dot closed=1 voi t <= RTL (bao theo dau chuoi t - run_s);
    RTL = hang app rtl=1 dau tien. Dot con mo khi het log: > 20.5 s -> FAIL RTL, nguoc lai 'chua ket thuc' + FAIL khong do duoc.
    d3 min / do cao tang tinh trong [t_ep0, bat lai | RTL | hang cuoi search.csv]. RTL doi chieu ca events.json blackout_start (+~0.3 s tre tracker).
    dist_crit: nhu crit nhung cho tieu chi khoang cach (--measure-only -> chi in '[do]')."""
    dist_crit = dist_crit or crit
    if search_rows is None:
        crit("tim lai: do duoc search.csv", False, "khong do duoc: thieu search.csv trong khi search.enabled")
        return
    bs = ev.get("blackout_start")
    eps = {}
    for r in search_rows:
        eid, t, es = _sf(r, "ep_id"), _sf(r, "t"), _sf(r, "ep_s")
        if math.isfinite(eid) and eid > 0 and math.isfinite(t) and math.isfinite(es):
            eps.setdefault(int(eid), []).append(r)
    cand = []
    for k, v in sorted(eps.items()):
        close = next((_sf(r, "t") for r in v if _sf(r, "closed") == 1.0 and math.isfinite(_sf(r, "run_s"))), None)
        if bs is None or close is None or close >= bs:
            cand.append((k, _sf(v[0], "t") - _sf(v[0], "ep_s"), v))
    if not cand:
        crit("tim lai: co dot tim lai trong search.csv", False, "khong do duoc: khong co dot nao con mo tu blackout_start")
        return
    eid, t_ep0, rows = cand[0]
    reacq_t = close_t = None
    for r in rows:
        if _sf(r, "closed") == 1.0 and math.isfinite(_sf(r, "run_s")):
            close_t, reacq_t = _sf(r, "t"), _sf(r, "t") - _sf(r, "run_s")
            break
    rtl_t = None
    for r in app:
        try:
            if float(r["t"]) >= t_ep0 - 1e-6 and int(float(r["rtl"])) >= 1:
                rtl_t = float(r["t"])
                break
        except (KeyError, ValueError, TypeError):
            pass
    if close_t is not None and (rtl_t is None or close_t <= rtl_t):      # bat lai chi khi dong dot (sau 1 s TRACK) khong sau RTL
        rtl_t, end = None, reacq_t
        what = "bat lai sau %.2f s" % (reacq_t - t_ep0)
    elif rtl_t is not None:
        end = rtl_t
        what = "RTL sau %.2f s" % (rtl_t - t_ep0)
    else:
        end = _sf(rows[-1], "t")
        what = "chua ket thuc"
    seg = [i for i in range(len(T)) if t_ep0 - 1e-6 <= T[i] <= end + 1e-6]
    d3min = min((D[i] for i in seg), default=float("nan"))
    climb = max((fl(truth[i], "ch_alt") for i in seg), default=float("nan")) - fl(truth[seg[0]], "ch_alt") if seg else float("nan")
    phases = [int(p) for p in (_sf(r, "phase") for r in rows) if math.isfinite(p)]
    lines.append("TIM LAI: dot=%d bat dau t=%.2f | %s | d3 min luc mu=%.2f m | do cao tang max=%.2f m | pha max=%d" % (
        eid, t_ep0, what, d3min, climb, max(phases, default=0)))
    if rtl_t is not None:
        rs = rtl_t - t_ep0
        ok = abs(rs - 20.0) <= 0.5 and (bs is None or abs(rtl_t - bs - 20.3) <= 0.5)
        crit("RTL o 20 +- 0.5 s", ok, "theo search.csv %.2f s%s" % (
            rs, "" if bs is None else " ; theo blackout_start %.2f s (mong doi 20.3 +- 0.5)" % (rtl_t - bs)))
    if what == "chua ket thuc":
        if end - t_ep0 > 20.5:
            crit("RTL o 20 +- 0.5 s", False, "dot mo %.2f s khi het log, khong RTL, khong bat lai" % (end - t_ep0))
        else:
            crit("tim lai: dot ket thuc do duoc", False, "khong do duoc: dot con mo %.2f s khi het log (chua toi 20 s)" % (end - t_ep0))
    dist_crit("d3 luc mu >= %g m" % a.blind_d3_min, d3min >= a.blind_d3_min, "min = %.2f m" % d3min)
    if climb_m > 0:
        crit("do cao tang <= climb_m + 1", climb <= climb_m + 1.0 + 1e-6, "tang %.2f m (gioi han %.1f m)" % (climb, climb_m + 1.0))


def new_blackout_scenario(ev):
    """Kich ban mat hinh MOI (design-search.md (f)): co cam/ham dung luc mat hinh hoac mat hinh dai hon 3 s (+0.5 s du tre mau cua helper)."""
    if ev.get("blackout_dive") or ev.get("blackout_brake") is not None:
        return True
    bs, be = ev.get("blackout_start"), ev.get("blackout_end")
    s = ev.get("blackout_s")
    if s is None and bs is not None and be is not None:
        s = be - bs
    return s is not None and s > 3.5


def scenario_params_line(a, ev):
    """Dong 'THAM SO KICH BAN: ...' (ghi tham so kich ban vao ket qua)."""
    bs, be, t_ws = ev.get("blackout_start"), ev.get("blackout_end"), ev.get("t_ws")
    ea = ev.get("event_at", (bs - t_ws) if bs is not None and t_ws is not None else float("nan"))
    bsec = ev.get("blackout_s", (be - bs) if bs is not None and be is not None else float("nan"))
    s = "THAM SO KICH BAN: event_at=%g blackout_s=%g post_s=%g blind_d3_min=%g measure_only=%d" % (
        ea, bsec, ev.get("post_s", 15.0), a.blind_d3_min, 1 if a.measure_only else 0)
    if ev.get("blackout_brake") is not None:
        s += " blackout_brake=%g" % ev["blackout_brake"]
    if ev.get("blackout_dive"):
        s += " blackout_dive=1"
    return s


def brake_metrics(truth, T, ev, dist_crit, lines):
    """Muc ham muc tieu dat duoc: (v(t0) - v(t0 + 1 s)) / dt, v = hypot(tgt_vn, tgt_ve), t0 = t_brake_cmd; tieu chi >= 80% yeu cau."""
    req, t0 = float(ev["blackout_brake"]), ev.get("t_brake_cmd")
    name = "ham dat >= 80% yeu cau"
    if t0 is None or not T:
        dist_crit(name, False, "khong do duoc: thieu t_brake_cmd hoac truth")
        return

    pts = [(T[i], math.hypot(fl(truth[i], "tgt_vn"), fl(truth[i], "tgt_ve"))) for i in range(len(T))
           if t0 - 1e-6 <= T[i] <= t0 + 4.0]
    pts = [p for p in pts if math.isfinite(p[1])]

    def v_at(t):                      # noi suy tuyen tinh (chiu duoc khoang trong mau)
        for (ta_, va), (tb_, vb) in zip(pts, pts[1:]):
            if ta_ <= t <= tb_:
                return va if tb_ <= ta_ else va + (vb - va) * (t - ta_) / (tb_ - ta_)
        return None
    # "ham dat duoc" = max do giam toc do ngang TB tren cua so truot 1 s, cua so bat dau trong [t0, t0 + 2.5 s] (tre lenh -> FC);
    # muc tieu dung han truoc khi du 1 s thi cua so ngan hon (>= 0.5 s)
    best, short = None, False
    for ts, vs in pts:
        if ts > t0 + 2.5 + 1e-6 or vs <= 0.05:
            continue
        te, sh = ts + 1.0, False
        stop = next((t for t, v in pts if t > ts and v <= 0.05), None)
        if stop is not None and stop < te:
            te, sh = max(stop, ts + 0.5), True
        ve = v_at(te)
        if ve is None:
            continue
        d = (vs - ve) / (te - ts)
        if best is None or d > best:
            best, short = d, sh
    if best is None:
        dist_crit(name, False, "khong do duoc: truth khong phu cua so 1 s sau t_brake_cmd")
        return
    ach = best
    lines.append("ham dat duoc = %.2f m/s2 (yeu cau %.2f)%s" % (ach, req, " [cua so ngan hon 1 s: muc tieu da dung]" if short else ""))
    dist_crit(name, ach >= 0.8 * req, "%.2f m/s2 (nguong %.2f)" % (ach, 0.8 * req))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out")
    ap.add_argument("--speed", type=float, required=True)
    ap.add_argument("--range", type=float, default=15.0, dest="rng")
    ap.add_argument("--tol", type=float, default=3.0)
    ap.add_argument("--window", type=float, default=120.0)
    ap.add_argument("--range-min", type=float, default=None, help="m; mac dinh guidance.range_min_m cua app_cfg.json, khong co thi cua dtrack.config")
    ap.add_argument("--alt-floor", type=float, default=None, help="m; san do cao chaser, mac dinh guidance.min_alt_m - 1")
    ap.add_argument("--alt-margin", type=float, default=10.0, help="m; chaser khong duoc thap hon do cao dich cua muc tieu sau cam tru so nay")
    ap.add_argument("--dmax",type=float, default=40.0, help="m; d3 lon nhat cho phep trong/sau cu cam va pha giam toc cuoi")
    ap.add_argument("--out-max", type=float, default=2.0, help="s; tong thoi gian muc tieu ra khoi khung cho phep trong pha cam / giam toc cuoi")
    ap.add_argument("--dive-after", type=float, default=5.0, help="s; pha cam keo dai them chung nay sau khi muc tieu het ha")
    ap.add_argument("--score-final", action="store_true", help="cham pha phanh cuoi cua ca KHONG cam xuong (mac dinh chi in)")
    ap.add_argument("--expect-dive", type=float, default=None, help="do; nguoi goi bao day la lan chay cam xuong: thieu events.json/moc cam -> FAIL")
    ap.add_argument("--blind-d3-min", type=float, default=8.0, help="m; d3 nho nhat cho phep luc mu (chi khi search.enabled; ca muc tieu ham dung 6)")
    ap.add_argument("--measure-only", action="store_true", help="tieu chi khoang cach (d3 luc mu, khong bao gio <, ham dat) chi in '[do]', khong doi ma thoat; tieu chi ha tang van cham")
    ap.add_argument("--helper-rc", type=int, default=None, help="ma thoat cua sim_helper; khac 0 -> FAIL (khong truyen = khong kiem)")
    a = ap.parse_args()

    truth = read_csv(os.path.join(a.out, "truth.csv"))
    truth, n_bad = drop_bad_rows(truth)
    ev_exists = os.path.exists(os.path.join(a.out, "events.json"))
    ev = json.load(open(os.path.join(a.out, "events.json"))) if ev_exists else {}
    app = read_csv(os.path.join(a.out, "app_log.csv")) if os.path.exists(os.path.join(a.out, "app_log.csv")) else []
    app_rc = int(open(os.path.join(a.out, "app.rc")).read().strip()) if os.path.exists(os.path.join(a.out, "app.rc")) else None
    scenario = ev.get("scenario", "none")
    ok_all = True
    lines = []

    def crit(name, ok, detail):
        nonlocal ok_all
        ok_all &= bool(ok)
        lines.append("[%s] %s: %s" % ("PASS" if ok else "FAIL", name, detail))

    def dist_crit(name, ok, detail):       # tieu chi khoang cach: --measure-only chi in, khong chan
        if a.measure_only:
            lines.append("[do] %s: %s" % (name, detail))
        else:
            crit(name, ok, detail)

    if len(truth) < 10:
        print("KET QUA: FAIL (truth.csv gan nhu rong)")
        return 1
    search_on, climb_m = cfg_search(a.out)
    if scenario == "blackout" and "blackout_start" in ev and (search_on or new_blackout_scenario(ev)):
        lines.append(scenario_params_line(a, ev))
    T = [fl(r, "t") for r in truth]
    D = [fl(r, "d3") for r in truth]
    dur = T[-1] - T[0]
    gaps = [T[i + 1] - T[i] for i in range(len(T) - 1)]
    lines.append("scenario=%s speed=%.0f  truth rows=%d  duration=%.1f s" % (scenario, a.speed, len(T), dur))
    crit("co events.json", ev_exists, "events.json %s" % ("co" if ev_exists else "THIEU (helper bi giet giua chung?)"))
    if a.helper_rc is not None:
        crit("helper thoat code 0", a.helper_rc == 0, "helper rc = %s" % a.helper_rc)
    if ev.get("speed") is not None and abs(float(ev["speed"]) - a.speed) > 1e-6:
        lines.append("CANH BAO: --speed %.1f lech events.json speed %.1f; dung %.1f trong tieu chi cam xuong" % (
            a.speed, float(ev["speed"]), float(ev["speed"])))
    if a.expect_dive is not None and a.expect_dive > 0 and ev_exists and abs((ev.get("dive_deg") or 0) - a.expect_dive) > 1e-6:
        crit("ca cam xuong: dive_deg trong events.json khop --expect-dive", False,
             "events dive_deg=%s, mong doi %.0f" % (ev.get("dive_deg"), a.expect_dive))
    if n_bad:
        lines.append("CANH BAO: bo %d dong truth.csv thieu/hong gia tri so (khong dua vao min/max/khoang trong)" % n_bad)
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
    if cfg_gimbal_enabled(a.out):     # khop gat chu dong: gimbal.csv phai doc duoc va phu thoi gian (moi kich ban)
        try:
            import numpy as np
            gimbal_series(a, np.array(T), ev)
            crit("gimbal.csv doc duoc va phu thoi gian truth", True, "ok")
        except Exception as exc:
            crit("gimbal.csv doc duoc va phu thoi gian truth", False, "khong do duoc: %s" % exc)
    # khoang cach that min tren toan chuyen bay
    imin = min(range(len(D)), key=lambda i: D[i])
    lines.append("min d3 toan chuyen bay = %.2f m tai t=%.1f s (t_rel=%.1f)" % (D[imin], T[imin], T[imin] - T[0]))
    both_air = [i for i, r in enumerate(truth) if fl(r, "tgt_alt") >= 2.0 and fl(r, "ch_alt") >= 2.0]
    if both_air:
        lines.append("min d3 khi ca hai >= 2 m do cao = %.2f m" % min(D[i] for i in both_air))
    hard_floor = cfg_acceptance(a.out, "hard_floor_m")
    if hard_floor is None:
        hard_floor = 8.0
    dist_crit("khong bao gio < %g m (toan chuyen bay)" % hard_floor, D[imin] >= hard_floor,"min = %.2f m" % D[imin])
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
        if search_on:        # tim lai bat: do bat lai / RTL / d3 luc mu / do cao tang (search.csv); tat thi dau ra khong doi
            sp = os.path.join(a.out, "search.csv")
            reacq_metrics(a, truth, T, D, app, read_csv(sp) if os.path.exists(sp) else None, ev, crit, lines, climb_m, dist_crit)
        elif new_blackout_scenario(ev):
            lines.append("CANH BAO: kich ban mat hinh dai nhung search tat: khong cham tim lai")
            pst = ev.get("post_s", 15.0)
            seg2 = [D[i] for i in range(len(T)) if bs <= T[i] <= be + pst]
            if seg2:
                lines.append("d3 min luc mu = %.2f m (search tat; [blackout_start, blackout_end + post_s])" % min(seg2))
        if ev.get("blackout_brake") is not None:
            brake_metrics(truth, T, ev, dist_crit, lines)
    b4res = {}
    try:
        lines.extend(b4_metrics(a, truth, app, ev, scenario, b4res))
    except Exception as exc:     # do dac B4 khong duoc lam hong ket qua chinh
        lines.append("B4 loi: %r" % (exc,))
    if ev.get("blackout_dive") or ev.get("blackout_brake") is not None:     # ca tim lai (design-search.md (f)): khong cham cam/giam toc cuoi kieu cu
        lines.append("ca mat hinh + cam/ham: bo cham cam xuong va giam toc cuoi kieu cu")
    else:
        dive_and_final_scoring(a, truth, T, D, ev, b4res, crit, lines)
    print("\n".join(lines))
    print("KET QUA: %s" % ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
