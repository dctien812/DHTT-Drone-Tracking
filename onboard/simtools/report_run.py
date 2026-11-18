#!/usr/bin/env python3
"""Dung bao cao hinh anh tu log mot (hoac nhieu) lan mo phong.

  python -m simtools.report_run <run_dir>... [--out <thu muc>] [--batch-html <file.html>]

Mac dinh ghi report.png vao chinh thu muc moi lan chay. Co --batch-html: ghi mot trang HTML tu chua cung cac PNG
(<ten lan chay>.png) vao CUNG thu muc voi file HTML (khi do chi ghi PNG canh HTML, tru khi co them --out).
So lieu hinh hoc camera / pha chay y het bo cham analyze_closed_loop (dung lai ham cua bo cham va dtrack).
"""
import argparse
import html
import json
import math
import os
import re
import sys
import urllib.parse
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np  # noqa: E402

from dtrack.config import make_camera  # noqa: E402
from dtrack.geometry import quat_from_euler, quat_to_matrix  # noqa: E402
from dtrack.gimbal import camera_attitude  # noqa: E402
from simtools.analyze_closed_loop import (NUM_COLS, cfg_gimbal_enabled, dive_times, drop_bad_rows, fl,  # noqa: E402
                                          load_gimbal_csv, read_csv)

GAP_S = 0.5            # nguong khoang trong gimbal.csv (cung bo cham)


# ---------------------------------------------------------------- doc du lieu
def _json(path):
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _sub(d, key):
    v = d.get(key)
    return v if isinstance(v, dict) else {}


def load_run(run_dir):
    """Doc truth.csv (bo dong hong nhu drop_bad_rows cua bo cham), events.json, app_cfg.json, gimbal.csv."""
    run_dir = str(run_dir)
    rows = read_csv(os.path.join(run_dir, "truth.csv"))      # thieu file -> FileNotFoundError
    rows = [{k: ("" if v is None else v) for k, v in r.items() if k is not None} for r in rows]
    good, _ = drop_bad_rows(rows)
    cols = list(good[0].keys()) if good else list(NUM_COLS)
    truth = {c: np.array([fl(r, c) for r in good], dtype=float) for c in cols}
    run = SimpleNamespace(run_dir=run_dir, name=os.path.basename(os.path.normpath(run_dir)), truth=truth,
                          events=_json(os.path.join(run_dir, "events.json")),
                          cfg=_json(os.path.join(run_dir, "app_cfg.json")), gimbal=None)
    gp = os.path.join(run_dir, "gimbal.csv")
    run.unsupported = None
    if os.path.exists(gp):
        try:
            t, d, s = load_gimbal_csv(gp)
            run.gimbal = SimpleNamespace(t=t, delta_rad=d, sat=s, cmd_rad=_gimbal_cmd(gp, len(t)))
        except (ValueError, OSError):
            run.gimbal = None
    if cfg_gimbal_enabled(run_dir):
        if run.gimbal is None:
            run.unsupported = "cấu hình bật khớp camera nhưng gimbal.csv thiếu hoặc hỏng, không dựng được khung hình"
    elif _sub(run.cfg, "camera").get("gimbal_enabled"):
        run.unsupported = "lần chạy dùng mô hình khớp camera kiểu cũ (camera.gimbal_enabled), công cụ này không hỗ trợ"
    return run


def _gimbal_cmd(path, n):
    """delta_cmd_deg [rad] cung bo loc dong cuoi bi cat nhu load_gimbal_csv; None neu khong doc duoc."""
    try:
        rows = read_csv(path)
        if len(rows) > 1 and None in rows[-1].values():
            rows = rows[:-1]
        c = np.radians([float(r["delta_cmd_deg"]) for r in rows])
        return c if len(c) == n and np.all(np.isfinite(c)) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _gimbal_active(run):
    return run.gimbal is not None and cfg_gimbal_enabled(run.run_dir)


def _measurable(run, T):
    """Mat na "do duoc" dung chung: camera co dinh -> tat ca; khop gat -> mau nam trong dai gimbal.csv va khong roi vao
    khoang trong > 0.5 s (cach xac dinh cua analyze_closed_loop.gimbal_series); cau hinh khong ho tro -> khong mau nao."""
    T = np.asarray(T, float)
    if run.unsupported:
        return np.zeros(len(T), bool)
    if not _gimbal_active(run):
        return np.ones(len(T), bool)
    tg = run.gimbal.t
    if len(tg) == 1:
        return np.abs(T - tg[0]) <= 1e-6
    k = np.clip(np.searchsorted(tg, T), 1, len(tg) - 1)
    lo, hi = tg[k - 1], tg[k]
    on_row = (np.abs(T - lo) <= 1e-6) | (np.abs(T - hi) <= 1e-6)
    return (T >= tg[0] - 1e-6) & (T <= tg[-1] + 1e-6) & (on_row | (hi - lo <= GAP_S + 1e-9))


# ---------------------------------------------------------------- hinh hoc camera
def _camera_params(run):
    cam = _sub(run.cfg, "camera")
    return (float(cam.get("fx", 1739.0)), float(cam.get("tilt_up_deg", 15.0)),
            int(cam.get("width", 1456)), int(cam.get("height", 1088)))


def target_pixels(run):
    """(t, u, v, in_frame) cho moi mau truth; cung hinh hoc voi analyze_closed_loop.b4_metrics."""
    fx, tilt, W, H = _camera_params(run)
    tr = run.truth
    T = tr["t"]
    n = len(T)
    gact = _gimbal_active(run)
    Rbc = np.array(make_camera(0.0 if gact else tilt, fx, fx, W, H).R_body_cam)
    u_out, v_out, ok = np.full(n, np.nan), np.full(n, np.nan), np.zeros(n, bool)
    if n == 0:
        return T, u_out, v_out, ok
    if gact:
        dint = np.interp(T, run.gimbal.t, run.gimbal.delta_rad)
    covered = _measurable(run, T)
    vec = np.stack([tr["tgt_n"] - tr["ch_n"], tr["tgt_e"] - tr["ch_e"], -(tr["tgt_alt"] - tr["ch_alt"])], 1)
    for i in range(n):
        if not covered[i]:
            continue
        qb = quat_from_euler(tr["ch_roll"][i], tr["ch_pitch"][i], tr["ch_yaw"][i])
        qc = camera_attitude(qb, float(dint[i])) if gact else qb
        ray = (quat_to_matrix(qc) @ Rbc).T @ vec[i]
        if ray[2] <= 1e-6:
            continue
        px, py = fx * ray[0] / ray[2] + W / 2.0, fx * ray[1] / ray[2] + H / 2.0
        u_out[i], v_out[i] = px, py
        ok[i] = 0.0 <= px <= W and 0.0 <= py <= H
    return T, u_out, v_out, ok


# ---------------------------------------------------------------- pha, khoang trong, bao hoa, ket qua
def phases(run, dive_after=5.0):
    """Moc pha y het analyze_closed_loop.b4_metrics (t90 thieu speed -> t_stop)."""
    ev, T = run.events, run.truth["t"]
    t_go, t_stop = ev.get("t_go"), ev.get("t_stop_target")
    if t_go is None or t_stop is None or len(T) == 0:
        return {}
    t_end = ev.get("t_both_stopped") or T[-1]
    spd = np.hypot(run.truth["tgt_vn"], run.truth["tgt_ve"])
    i90 = np.where((T >= t_go) & (spd >= 0.9 * float(ev["speed"])))[0] if ev.get("speed") is not None else []
    t90 = T[i90[0]] if len(i90) else t_stop
    t_dive, t_dive_end = dive_times([{"t": a, "tgt_vd": b} for a, b in zip(T, run.truth["tgt_vd"])], ev)
    if t_dive is not None:
        t_cut = min((t_dive_end if t_dive_end is not None else t_stop) + dive_after, t_stop)
        ph = {"tang_toc": (t_go, t90), "bam_on_dinh": (t90, t_dive), "cam_xuong": (t_dive, t_cut),
              "bay_bang": (t_cut, t_stop), "giam_toc_cuoi": (t_stop, t_end)}
    else:
        ph = {"tang_toc": (t_go, t90), "bam_on_dinh": (t90, t_stop), "phanh_cuoi": (t_stop, t_end)}
    return {k: (float(a), float(b)) for k, (a, b) in ph.items()}


def gimbal_gaps(run):
    """Cac doan khong do duoc goc khop (de to xam); camera co dinh -> []."""
    T = run.truth["t"]
    if not _gimbal_active(run) or len(T) == 0:
        return []
    tg = run.gimbal.t
    out = []
    if T[0] < tg[0] - 1e-6:
        out.append((float(T[0]), float(tg[0])))
    for a, b in zip(tg[:-1], tg[1:]):
        if b - a > GAP_S + 1e-9:
            out.append((float(a), float(b)))
    if T[-1] > tg[-1] + 1e-6:
        out.append((float(tg[-1]), float(T[-1])))
    return out


def saturation_spans(run):
    """Moi doan lien tiep sat>0: (t dong sat dau, t dong ke sau doan; het file thi t dong cuoi)."""
    if run.gimbal is None:
        return []
    tg, sat = run.gimbal.t, run.gimbal.sat
    out, i, n = [], 0, len(tg)
    while i < n:
        if sat[i]:
            j = i
            while j < n and sat[j]:
                j += 1
            out.append((float(tg[i]), float(tg[j]) if j < n else float(tg[-1])))
            i = j
        else:
            i += 1
    return out


def parse_result(run_dir):
    """result.txt -> (verdict | None, [(ten, "PASS"|"FAIL", chi tiet)])."""
    try:
        with open(os.path.join(str(run_dir), "result.txt"), encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None, []
    verdict, crit = None, []
    for ln in lines:
        if ln.startswith("KET QUA: "):
            w = ln[len("KET QUA: "):].split()
            verdict = w[0] if w else None
        m = re.match(r"\[(PASS|FAIL)\] (.*)$", ln)
        if m:
            name, _, detail = m.group(2).partition(": ")
            crit.append((name, m.group(1), detail))
    return verdict, crit


# ---------------------------------------------------------------- tinh so lieu tom tat
def out_of_frame_stats(run, t0, t1, px=None):
    """(so lan, so giay) ra khung trong [t0, t1] -- cong thuc cua bo cham, nhung mau KHONG do duoc (ngoai dai/khoang
    trong gimbal.csv) khong tinh; mau sau camera van tinh. None neu khong co mau, hoac cau hinh khong ho tro."""
    if run.unsupported:
        return None
    t, ok = (px[0], px[3]) if px is not None else target_pixels(run)[::3]
    m = (t >= t0) & (t <= t1)
    if not m.any():
        return None
    oo = (~ok & _measurable(run, t))[m]
    dts = np.diff(t[m], append=t[m][-1])
    return int(np.sum(oo[1:] & ~oo[:-1])) + int(oo[0]), float(np.sum(dts[oo]))


def effective_gimbal_limits(run):
    """(delta_min_deg, delta_max_deg): cfg ghi ro -> suy tu mau sat>0 cua gimbal.csv -> mac dinh (10, 110)."""
    gm = _sub(run.cfg, "gimbal")
    lo, hi = gm.get("delta_min_deg"), gm.get("delta_max_deg")
    if (lo is None or hi is None) and run.gimbal is not None and run.gimbal.sat.any():
        d = np.degrees(run.gimbal.delta_rad)
        med = float(np.median(d))
        up, dn = d[run.gimbal.sat & (d > med)], d[run.gimbal.sat & (d < med)]
        if hi is None and len(up):
            hi = float(up.max())
        if lo is None and len(dn):
            lo = float(dn.min())
    return (10.0 if lo is None else float(lo)), (110.0 if hi is None else float(hi))


def _window(run):
    """[t_go, t_end] neu co moc, khong thi toan bo truth."""
    T = run.truth["t"]
    if len(T) == 0:
        return 0.0, 1.0
    t_go = run.events.get("t_go")
    if t_go is None:
        return float(T[0]), float(T[-1])
    return float(t_go), float(run.events.get("t_both_stopped") or T[-1])


def _summary(run, px, ph):
    t, ok = px[0], px[3]
    w0, w1 = _window(run)
    m = (t >= w0) & (t <= w1)
    s = {"out_dive": None, "out_final": None, "d3_min": None, "delta_min": None, "delta_max": None}
    if "cam_xuong" in ph:
        s["out_dive"] = out_of_frame_stats(run, *ph["cam_xuong"], px=px)
    for k in ("giam_toc_cuoi", "phanh_cuoi"):
        if k in ph:
            s["out_final"] = out_of_frame_stats(run, *ph[k], px=px)
    d3 = run.truth.get("d3", np.array([]))
    if m.any() and len(d3) == len(t):
        s["d3_min"] = float(np.nanmin(d3[m]))
    if _gimbal_active(run):
        g = run.gimbal
        mg = (g.t >= w0) & (g.t <= w1)
        if mg.any():
            s["delta_min"], s["delta_max"] = (float(np.degrees(g.delta_rad[mg].min())),
                                              float(np.degrees(g.delta_rad[mg].max())))
    return s


def _config_info(run):
    gm, gd = _sub(run.cfg, "gimbal"), _sub(run.cfg, "guidance")
    active = _gimbal_active(run)
    seed = re.search(r"_s(\d+)(?:_|$)", run.name)
    lo, hi = effective_gimbal_limits(run)
    return {"range": float(gd.get("range_set_m", 15.0)), "scenario": str(run.events.get("scenario", "none")),
            "seed": seed.group(1) if seed else "?", "speed": run.events.get("speed"),
            "dive": run.events.get("dive_deg"), "gimbal": active, "dmin": lo, "dmax": hi,
            "floor": float(_sub(run.cfg, "acceptance").get("hard_floor_m", 8.0)),
            "frozen": bool(gm.get("frozen")), "init": float(gm.get("delta_init_deg", 90.0)),
            "tilt": _camera_params(run)[1], "unsupported": run.unsupported}


def _cfg_text(ci, short=False):
    parts = ["giữ khoảng cách %g m" % ci["range"], "kịch bản %s" % ci["scenario"], "seed %s" % ci["seed"]]
    if ci["speed"] is not None:
        parts.append("tốc độ mục tiêu %g m/s" % ci["speed"])
    if ci["dive"]:
        parts.append("cắm %g°" % ci["dive"])
    if ci["unsupported"]:
        parts.append("KHÔNG DỰNG ĐƯỢC KHUNG HÌNH%s" % (" (lý do ở ô 3)" if short else ": " + ci["unsupported"]))
    elif ci["gimbal"]:
        parts.append("khớp đứng yên ở %g°" % ci["init"] if ci["frozen"] else "dải khớp %g°–%g°" % (ci["dmin"], ci["dmax"]))
    else:
        parts.append("camera cố định (nghiêng lên %g°)" % ci["tilt"])
    if ci["scenario"] == "disengage":
        parts.append("kịch bản hủy bám: bộ chấm không chấm số đo bám")
    return " · ".join(parts)


# ---------------------------------------------------------------- ve hinh
OK_C, BAD_C, GREY = "#2e7d32", "#c62828", "#78909c"
PHASE_VN = {"tang_toc": "Tăng tốc", "bam_on_dinh": "Bám ổn định", "cam_xuong": "Cắm xuống",
            "bay_bang": "Bay bằng", "giam_toc_cuoi": "Giảm tốc cuối", "phanh_cuoi": "Phanh cuối"}
PHASE_C = {"tang_toc": "#eceff1", "bam_on_dinh": "#e8f5e9", "cam_xuong": "#ffe0b2", "bay_bang": "#e3f2fd",
           "giam_toc_cuoi": "#f8bbd0", "phanh_cuoi": "#f8bbd0"}
STATE_VN = {"track": ("BÁM (TRACK)", "#2e7d32"), "coast": ("QUÁN TÍNH (COAST)", "#f9a825"),
            "search": ("TÌM (SEARCH)", "#1e88e5"), "lost": ("MẤT (LOST)", "#c62828"),
            "abort": ("HỦY (ABORT)", "#6a1b1b"), "idle": ("CHỜ (IDLE)", "#b0bec5")}


def _style():
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False, "font.size": 10,
                                "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
                                "axes.grid": True, "grid.color": "#e0e0e0", "grid.linewidth": 0.6,
                                "axes.edgecolor": "#90a4ae", "axes.facecolor": "#fcfcfc"})


def _note(ax, text):
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes, color=GREY, fontsize=12)
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)


def _pname(k, scenario):
    """Ten pha hien thi; ca disengage: pha cuoi la luc drone da nha muc tieu (IDLE), khong phai phanh."""
    if k == "phanh_cuoi" and scenario == "disengage":
        return "Sau khi hủy bám"
    return PHASE_VN.get(k, k)


def _shade(ax, ph, t0, label=False, scenario=""):
    for k, (a, b) in ph.items():
        ax.axvspan(a - t0, b - t0, color=PHASE_C.get(k, "#eee"), alpha=0.85, lw=0, zorder=0)
        if label and b > a:
            ax.text((a + b) / 2 - t0, 1.015, _pname(k, scenario), transform=ax.get_xaxis_transform(), ha="center",
                    va="bottom", fontsize=8.5, color="#455a64")


def _read_states(run_dir, w0, w1):
    p = os.path.join(run_dir, "app_log.csv")
    if not os.path.exists(p):
        return None
    try:
        rows = read_csv(p)
    except OSError:
        return None
    out = []
    for r in rows:
        t = fl(r, "t")
        if math.isfinite(t) and r.get("state") and w0 <= t <= w1:
            out.append((t, r["state"]))
    return out


# Bang dich ten tieu chi hay gap trong result.txt (khong khop -> giu nguyen chu goc). Mau khop toan bo ten.
_NAME_VN = [
    (r"co events\.json", "Có tệp events.json"),
    (r"helper thoat code 0", "Trình điều khiển mô phỏng thoát mã 0"),
    (r"khoang trong truth toi da <= ([\d.]+) s(?: \(trong cua so do\))?",
     r"Khoảng trống dữ liệu vị trí thật tối đa ≤ \1 s (trong cửa sổ đo)"),
    (r"tan so ghi truth >= (\d+) Hz", r"Tần số ghi vị trí thật ≥ \1 Hz"),
    (r"gimbal\.csv doc duoc va phu thoi gian truth", "gimbal.csv đọc được và phủ thời gian chuyến bay"),
    (r"khong bao gio < ([\d.]+) m \(toan chuyen bay\)", r"Không bao giờ gần hơn \1 m (toàn chuyến bay)"),
    (r"app thoat code 0", "Ứng dụng bám thoát mã 0"),
    (r"cua so du (\d+) s", r"Cửa sổ đo đủ \1 s"),
    (r"sai so TB < ([\d.]+) m", r"Sai số khoảng cách trung bình < \1 m"),
    (r"muc tieu doi huong >= (\d+) lan trong cua so", r"Mục tiêu đổi hướng ≥ \1 lần trong cửa sổ"),
    (r"ty le thoi gian o TRACK >= (\d+)%", r"Tỉ lệ thời gian ở trạng thái BÁM ≥ \1%"),
    (r"hai may dung han o cuoi chuyen \(both_stopped\)", "Hai máy bay dừng hẳn ở cuối chuyến"),
    (r"muc tieu thuc su cam xuong \(ha >= (\d+) m\)", r"Mục tiêu thực sự cắm xuống (hạ ≥ \1 m)"),
    (r"muc tieu khong cam qua sau \(ha <= (\d+) m = 1\.3 \* dive_drop_m\)", r"Mục tiêu không cắm quá sâu (hạ ≤ \1 m)"),
    (r"toc do ha dinh cua muc tieu >= ([\d.]+) m/s.*", r"Tốc độ hạ đỉnh của mục tiêu ≥ \1 m/s"),
    (r"pha cam", "Pha cắm"),
    (r"trong va sau cu cam", "Trong và sau cú cắm"),
    (r"muc tieu ra khoi khung trong pha cam <= ([\d.]+) s", r"Mục tiêu ra khỏi khung trong pha cắm ≤ \1 s"),
    (r"muc tieu ra khoi khung trong pha bay bang <= ([\d.]+) s", r"Mục tiêu ra khỏi khung trong pha bay bằng ≤ \1 s"),
    (r"do cao chaser >= san ([\d.]+) m.*", r"Độ cao drone ≥ sàn \1 m (từ lúc cắm đến hết chuyến)"),
    (r"do cao chaser >= do cao dich danh dinh sau cam - (\d+) m = ([\d.]+) m",
     r"Độ cao drone ≥ độ cao đích của mục tiêu sau cắm trừ \1 m (= \2 m)"),
    (r"giam toc cuoi", "Giảm tốc cuối"),
    (r"do tre disengage", "Độ trễ khi hủy bám"),
    (r"app ngung gui lenh <= ([\d.]+) s sau lenh doi mode", r"Ứng dụng ngừng gửi lệnh ≤ \1 s sau lệnh đổi chế độ"),
    (r"sau disengage khong gui lai lenh nao", "Sau khi hủy bám không gửi lại lệnh nào"),
]
_DETAIL_VN = [(r"^d3 min >= range_min", "khoảng cách nhỏ nhất ≥ ngưỡng"), (r"^d3 max <=", "khoảng cách lớn nhất ≤"),
              (r"^ra khoi khung", "ra khỏi khung"), (r"lien tuc dai nhat", "liên tục dài nhất"), (r"\blan\b", "lần"),
              (r"\bmin =", "nhỏ nhất ="), (r"\bmax =", "lớn nhất ="), (r"^ha ", "hạ "), (r"^dinh ", "đỉnh "),
              (r"khong co dong", "không có dòng")]


def _vn_name(name):
    for pat, rep in _NAME_VN:
        if re.fullmatch(pat, name):
            return re.sub(pat, rep, name)
    return name


def _vn_detail(detail):
    for pat, rep in _DETAIL_VN:
        detail = re.sub(pat, rep, detail)
    return detail


def _wrap(s, n):
    import textwrap
    return "\n".join(textwrap.wrap(s, n))


def _fmt_out(x):
    return "—" if x is None else "%.2f s" % x[1]


def _draw(run, run_dir, px, ph, summ, verdict, crit, out_png):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle
    _style()
    fig = plt.figure(figsize=(16, 20), dpi=100, facecolor="white")
    name = run.name if run is not None else os.path.basename(os.path.normpath(run_dir))
    ci = _config_info(run) if run is not None else None
    ok_v = {"PASS": (OK_C, "ĐẠT"), "FAIL": (BAD_C, "KHÔNG ĐẠT")}.get(verdict, (GREY, "CHƯA CÓ KẾT QUẢ"))
    fig.text(0.03, 0.972, name, fontsize=21, fontweight="bold", va="center", color="#263238")
    fig.text(0.97, 0.972, ok_v[1], fontsize=18, fontweight="bold", color="white", ha="right", va="center",
             bbox=dict(boxstyle="round,pad=0.4", fc=ok_v[0], ec="none"))
    if run is None:
        fig.text(0.03, 0.948, "Không đọc được dữ liệu: thiếu truth.csv trong thư mục lần chạy.", fontsize=12, color=BAD_C)
        fig.savefig(out_png, dpi=100, facecolor="white")
        plt.close(fig)
        return
    fig.text(0.03, 0.947, _cfg_text(ci, short=True), fontsize=12, color="#455a64", va="center")
    d3m = "—" if summ["d3_min"] is None else "%.1f m" % summ["d3_min"]
    fig.text(0.03, 0.926, "Ra khỏi khung hình: pha cắm %s · %s %s     Khoảng cách gần nhất (từ lúc xuất phát): %s"
             % (_fmt_out(summ["out_dive"]), "sau khi hủy bám" if ci["scenario"] == "disengage" else "giảm tốc cuối",
                _fmt_out(summ["out_final"]), d3m),
             fontsize=11, color="#455a64", va="center")
    sc_name = ci["scenario"]
    fig.text(0.03, 0.905, "Mốc pha (số trên hình 1a, 1b): " + " · ".join(
        "%d %s" % (j + 1, _pname(k, sc_name)) for j, k in enumerate(ph)) + "     Nền màu: các pha chuyến bay",
        fontsize=10, color="#455a64", va="center")

    gs = fig.add_gridspec(4, 2, left=0.065, right=0.975, top=0.885, bottom=0.035, hspace=0.34, wspace=0.2,
                          height_ratios=[3.1, 2.3, 3.9, 4.6])
    tr, T = run.truth, run.truth["t"]
    w0, w1 = _window(run)
    wm = (T >= w0) & (T <= w1)
    Tw = T[wm] - w0

    # (1) quy dao
    ax_s, ax_t = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    ax_s.set_title("1a. Quỹ đạo nhìn ngang"); ax_t.set_title("1b. Quỹ đạo nhìn từ trên xuống")
    if wm.sum() >= 2:
        n0, e0 = tr["tgt_n"][wm][0], tr["tgt_e"][wm][0]
        stop = run.events.get("t_stop_target")
        k1 = np.searchsorted(T, stop) if stop is not None else len(T) - 1
        dn, de = tr["tgt_n"][min(k1, len(T) - 1)] - n0, tr["tgt_e"][min(k1, len(T) - 1)] - e0
        nr = math.hypot(dn, de)
        dn, de = (dn / nr, de / nr) if nr > 1.0 else (1.0, 0.0)
        tn, te, ta = tr["tgt_n"][wm] - n0, tr["tgt_e"][wm] - e0, tr["tgt_alt"][wm]
        cn, ce, ca = tr["ch_n"][wm] - n0, tr["ch_e"][wm] - e0, tr["ch_alt"][wm]
        t_al, c_al = tn * dn + te * de, cn * dn + ce * de
        for a in range(0, len(Tw), max(1, int(len(Tw) / 25))):
            ax_s.plot([t_al[a], c_al[a]], [ta[a], ca[a]], color="#cfd8dc", lw=0.8, zorder=1)
            ax_t.plot([te[a], ce[a]], [tn[a], cn[a]], color="#cfd8dc", lw=0.8, zorder=1)
        ax_s.plot(t_al, ta, color="#e65100", lw=2, label="Mục tiêu", zorder=3)
        ax_s.plot(c_al, ca, color="#1565c0", lw=2, label="Drone", zorder=3)
        ax_t.plot(te, tn, color="#e65100", lw=2, label="Mục tiêu", zorder=3)
        ax_t.plot(ce, cn, color="#1565c0", lw=2, label="Drone", zorder=3)
        for j, (k, (a, _)) in enumerate(ph.items()):
            i = int(np.clip(np.searchsorted(T[wm], a), 0, len(Tw) - 1))
            off = (0, 13 if j % 2 == 0 else -15)
            for ax, x, y in ((ax_s, t_al[i], ta[i]), (ax_t, te[i], tn[i])):
                ax.plot(x, y, "o", color="#263238", ms=5, zorder=4)
                ax.annotate(str(j + 1), (x, y), textcoords="offset points", xytext=off, ha="center", va="center",
                            fontsize=9, fontweight="bold", color="#263238", zorder=5,
                            bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec="#90a4ae", lw=0.6),
                            arrowprops=dict(arrowstyle="-", color="#90a4ae", lw=0.6))
        ax_s.set_xlabel("Quãng đường dọc hướng bay (m)  —  độ cao được phóng đại"); ax_s.set_ylabel("Độ cao (m)")
        ax_t.set_xlabel("Hướng đông (m)"); ax_t.set_ylabel("Hướng bắc (m)")
        half = max(abs(np.concatenate([te, ce])).max() * 1.2, 30.0)      # khong dung ti le 1:1: chuyen bay dai vai km
        ax_t.set_xlim(-half, half)
        ax_t.set_xlabel("Hướng đông (m)  —  trục ngang được phóng đại")
        ax_s.legend(loc="best", fontsize=9, framealpha=0.9)
        ax_s.text(0.99, 0.02, "đường xám: nối drone–mục tiêu mỗi ~%.0f s" % max(1.0, (Tw[-1] - Tw[0]) / 25),
                  transform=ax_s.transAxes, ha="right", fontsize=8, color=GREY)
    else:
        _note(ax_s, "Không đủ dữ liệu quỹ đạo"); _note(ax_t, "Không đủ dữ liệu quỹ đạo")

    # (2) khoang cach
    ax_d = fig.add_subplot(gs[1, :])
    ax_d.set_title("2. Khoảng cách drone–mục tiêu theo thời gian", pad=22)
    if wm.sum() >= 1 and "d3" in tr:
        _shade(ax_d, ph, w0, label=True, scenario=sc_name)
        ax_d.plot(Tw, tr["d3"][wm], color="#1565c0", lw=1.6, label="Khoảng cách 3D", zorder=3)
        ax_d.axhline(ci["range"], color=OK_C, ls="--", lw=1.2, label="Khoảng cách giữ %g m" % ci["range"], zorder=2)
        ax_d.axhline(ci["floor"], color=BAD_C, ls="-", lw=1.4, label="Sàn an toàn %g m" % ci["floor"], zorder=2)
        ax_d.set_ylim(min(0.0, ci["floor"] * 0.5), max(float(np.nanmax(tr["d3"][wm])), ci["range"]) * 1.3)
        if Tw[-1] > Tw[0]:
            ax_d.set_xlim(Tw[0], Tw[-1])
        ax_d.set_xlabel("Thời gian từ lúc mục tiêu xuất phát (s)")
        ax_d.set_ylabel("Mét"); ax_d.legend(loc="upper right", fontsize=9, ncol=3, framealpha=0.95)
    else:
        _note(ax_d, "Không có dữ liệu khoảng cách")

    # (3) khung hinh camera
    ax_f = fig.add_subplot(gs[2, 0])
    ax_f.set_title("3. Khung hình camera: vệt tâm mục tiêu")
    fx, _, W, H = _camera_params(run)
    t_px, u, v, inf = px
    mf = wm & np.isfinite(u)
    ax_f.add_patch(Rectangle((0, 0), W, H, fc="white", ec="#263238", lw=2.2, zorder=1))
    ax_f.plot([W / 2], [H / 2], "+", color=GREY, ms=14, zorder=2)
    if mf.any():
        sc = ax_f.scatter(u[mf & inf], v[mf & inf], c=(t_px[mf & inf] - w0), cmap="viridis", s=7, zorder=3)
        ax_f.scatter(u[mf & ~inf], v[mf & ~inf], c=BAD_C, s=14, zorder=4, label="ngoài khung")
        if (mf & inf).any():
            cb = fig.colorbar(sc, ax=ax_f, orientation="horizontal", pad=0.12, fraction=0.04)
            cb.set_label("thời gian (s)")
        if (mf & ~inf).any():
            ax_f.legend(loc="lower right", fontsize=9)
    if run.unsupported:
        ax_f.text(0.5, 0.5, "Không dựng được khung hình:\n" + _wrap(run.unsupported, 38), transform=ax_f.transAxes,
                  ha="center", va="center", fontsize=11, color=BAD_C, zorder=6,
                  bbox=dict(boxstyle="round", fc="white", ec=BAD_C))
    else:
        unm = int(np.sum(wm & ~_measurable(run, T)))
        if unm > 0.02 * max(int(wm.sum()), 1):      # quá 2% mẫu: ngưỡng cho phép của bộ chấm
            ax_f.text(0.5, 1.0, "%d mẫu khớp không đo được (không vẽ)" % unm, transform=ax_f.transAxes, ha="center",
                      va="top", fontsize=8, color=GREY, zorder=6)
    ax_f.set_xlim(-0.2 * W, 1.2 * W); ax_f.set_ylim(1.2 * H, -0.2 * H); ax_f.set_aspect("equal")
    ax_f.set_xlabel("pixel ngang (khung %d × %d)" % (W, H)); ax_f.set_ylabel("pixel dọc")

    sub = gs[2, 1].subgridspec(2, 1, hspace=0.55, height_ratios=[3, 1.6])
    ax_g, ax_c = fig.add_subplot(sub[0]), fig.add_subplot(sub[1])
    ax_g.set_title("4. Góc khớp camera δ")
    if ci["gimbal"] and run.gimbal is not None:
        g = run.gimbal
        _shade(ax_g, ph, w0, scenario=sc_name)
        for a, b in gimbal_gaps(run):
            ax_g.axvspan(a - w0, b - w0, color="#9e9e9e", alpha=0.55, lw=0, zorder=1)
        for a, b in saturation_spans(run):
            ax_g.axvspan(a - w0, b - w0, color="#ff9800", alpha=0.6, lw=0, zorder=1)
        if g.cmd_rad is not None:
            ax_g.plot(g.t - w0, np.degrees(g.cmd_rad), color="#90caf9", lw=1.2, ls="--", label="δ lệnh", zorder=2)
        ax_g.plot(g.t - w0, np.degrees(g.delta_rad), color="#0d47a1", lw=1.6, label="δ thực", zorder=3)
        ax_g.axhline(ci["dmin"], color=BAD_C, ls=":", lw=1.2); ax_g.axhline(ci["dmax"], color=BAD_C, ls=":", lw=1.2)
        ax_g.text(0.005, ci["dmax"], " giới hạn trên %g°" % ci["dmax"], transform=ax_g.get_yaxis_transform(),
                  va="bottom", fontsize=8, color=BAD_C)
        ax_g.text(0.005, ci["dmin"], " giới hạn dưới %g°" % ci["dmin"], transform=ax_g.get_yaxis_transform(),
                  va="top", fontsize=8, color=BAD_C)
        ax_g.set_xlim(Tw[0] if len(Tw) else 0, Tw[-1] if len(Tw) else 1)
        ax_g.set_ylim(ci["dmin"] - 12, ci["dmax"] + 12); ax_g.set_ylabel("độ (°)")
        h, _ = ax_g.get_legend_handles_labels()
        ax_g.legend(handles=h + [Patch(color="#ff9800", alpha=0.6, label="chạm giới hạn"),
                                 Patch(color="#9e9e9e", alpha=0.55, label="không đo được")],
                    loc="lower right", fontsize=8, ncol=2, framealpha=0.95)
    elif run.unsupported:
        _note(ax_g, "không dựng được:\n" + _wrap(run.unsupported, 50))
    else:
        _note(ax_g, "camera cố định")

    ax_c.set_title("5. Trạng thái bám của drone")
    states = _read_states(run.run_dir, w0, w1)
    if states:
        order = [s for s in STATE_VN if any(x[1] == s for x in states)] + sorted(
            {x[1] for x in states if x[1] not in STATE_VN})
        lane = {s: i for i, s in enumerate(order)}
        i = 0
        for j in range(1, len(states) + 1):
            if j == len(states) or states[j][1] != states[i][1]:
                te_ = states[j][0] if j < len(states) else states[-1][0]
                ax_c.broken_barh([(states[i][0] - w0, max(te_ - states[i][0], 0.05))], (lane[states[i][1]] - 0.4, 0.8),
                                 color=STATE_VN.get(states[i][1], (0, "#607d8b"))[1], lw=0)
                i = j
        ax_c.set_yticks(range(len(order)))
        ax_c.set_yticklabels([STATE_VN.get(s, (s.upper(), 0))[0] for s in order], fontsize=8)
        ax_c.set_ylim(-0.7, len(order) - 0.3); ax_c.set_xlim(ax_g.get_xlim() if ci["gimbal"] else (Tw[0], Tw[-1]))
        ax_c.invert_yaxis()
    else:
        _note(ax_c, "không có app_log.csv trong khoảng này")
    for ax in (ax_g, ax_c):
        if ax.has_data():
            ax.set_xlabel("thời gian từ lúc mục tiêu xuất phát (s)")

    # (6) bang tieu chi
    ax_k = fig.add_subplot(gs[3, :])
    ax_k.set_title("6. Các tiêu chí chấm điểm (từ result.txt)")
    ax_k.set_xticks([]); ax_k.set_yticks([]); ax_k.grid(False)
    for s in ax_k.spines.values():
        s.set_visible(False)
    if not crit:
        _note(ax_k, "không có result.txt (hoặc chưa có tiêu chí)")
    else:
        n = len(crit)
        ax_k.set_xlim(0, 1); ax_k.set_ylim(n + 1, 0)
        fs = max(6.5, min(10.5, 330.0 / (n + 1) * 0.62))
        cut = lambda s, k: s if len(s) <= k else s[:k - 1] + "…"
        ax_k.text(0.01, 0.5, "Kết quả", fontsize=fs, fontweight="bold", va="center", color="#455a64")
        ax_k.text(0.11, 0.5, "Tiêu chí", fontsize=fs, fontweight="bold", va="center", color="#455a64")
        ax_k.text(0.63, 0.5, "Chi tiết", fontsize=fs, fontweight="bold", va="center", color="#455a64")
        for i, (nm, st, dt) in enumerate(crit):
            y = i + 1.5
            c = OK_C if st == "PASS" else BAD_C
            ax_k.add_patch(Rectangle((0, y - 0.5), 1, 1, fc="#fdecea" if st == "FAIL" else ("#f6f8f9" if i % 2 else "white"),
                                     ec="none", zorder=0))
            ax_k.text(0.012, y, "✓ đạt" if st == "PASS" else "✗ không đạt", color="white", fontsize=fs, va="center",
                      fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", fc=c, ec="none"))
            ax_k.text(0.11, y, cut(_vn_name(nm), 92), fontsize=fs, va="center", color="#263238")
            ax_k.text(0.63, y, cut(_vn_detail(dt), 70), fontsize=fs, va="center",
                      color="#263238" if st == "PASS" else BAD_C)
    fig.savefig(out_png, dpi=100, facecolor="white")
    plt.close(fig)


def _render(run_dir, out_png):
    """Ve PNG va tra (run | None, verdict, crit, summary | None)."""
    run_dir = str(run_dir)
    try:
        run = load_run(run_dir)
    except FileNotFoundError:
        run = None
    verdict, crit = parse_result(run_dir)
    if run is None:
        summ, px, ph = None, None, {}
    else:
        px, ph = target_pixels(run), phases(run)
        summ = _summary(run, px, ph)
    _draw(run, run_dir, px, ph, summ, verdict, crit, str(out_png))
    return run, verdict, crit, summ


def render_run(run_dir, out_png):
    _render(run_dir, out_png)


# ---------------------------------------------------------------- trang lo HTML
_CSS = """
body{font-family:'Segoe UI',Roboto,Arial,sans-serif;margin:0;background:#f5f7f8;color:#263238}
header{background:#fff;padding:14px 18px;border-bottom:1px solid #cfd8dc}
h1{font-size:1.3rem;margin:0 0 4px}.sub{color:#546e7a;font-size:.9rem}
main{padding:14px 18px;max-width:1700px;margin:auto}
.wrap{overflow-x:auto;background:#fff;border:1px solid #cfd8dc;border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:7px 10px;border-bottom:1px solid #eceff1;text-align:left;vertical-align:top}
th{background:#eceff1;font-weight:600;white-space:nowrap}
a{color:#1565c0;text-decoration:none;word-break:break-all}a:hover{text-decoration:underline}
.badge{display:inline-block;padding:2px 9px;border-radius:10px;color:#fff;font-weight:700;font-size:.8rem}
.ok{background:#2e7d32}.bad{background:#c62828}.na{background:#78909c}
.card{background:#fff;border:1px solid #cfd8dc;border-radius:8px;margin-top:18px;padding:10px 12px}
.card h2{font-size:1.05rem;margin:0 0 8px;word-break:break-all}
img{max-width:100%;height:auto;display:block}
@media(max-width:600px){main{padding:8px}header{padding:10px}th,td{padding:5px 6px}}
"""


def _anchor(name):
    return "run-" + re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def render_batch(run_dirs, out_html):
    out_html = os.path.abspath(str(out_html))
    out_dir = os.path.dirname(out_html)
    os.makedirs(out_dir, exist_ok=True)
    used, rows = set(), []
    for d in run_dirs:
        base = os.path.basename(os.path.normpath(str(d)))
        png, k = base + ".png", 1
        while png in used:
            k += 1
            png = "%s_%d.png" % (base, k)
        used.add(png)
        try:
            run, verdict, crit, s = _render(d, os.path.join(out_dir, png))
            cfg_txt, err = (_cfg_text(_config_info(run)) if run is not None else "không đọc được truth.csv"), None
        except Exception as exc:        # mot lan hong khong duoc lam mat ca trang
            run, (verdict, _), s, png = None, parse_result(d), None, None
            cfg_txt, err = "", "%s: %s" % (type(exc).__name__, exc)
        rows.append((base, png, cfg_txt, verdict, s, err))
    n_ok = sum(1 for r in rows if r[3] == "PASS")
    n_bad = sum(1 for r in rows if r[3] == "FAIL")
    out = ["<!DOCTYPE html>\n<html lang=\"vi\"><head><meta charset=\"utf-8\">",
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
           "<title>Báo cáo mô phỏng Drone Tracking</title><style>%s</style></head><body>" % _CSS,
           "<header><h1>Báo cáo mô phỏng Drone Tracking</h1><div class=\"sub\">%d lần chạy: %d đạt, %d không đạt, "
           "%d chưa có kết quả. Bấm vào tên để xem hình chi tiết.</div></header><main>" % (
               len(rows), n_ok, n_bad, len(rows) - n_ok - n_bad),
           "<div class=\"wrap\"><table><tr><th>Lần chạy</th><th>Cấu hình</th><th>Kết quả</th>"
           "<th>Ra khung: pha cắm / giảm tốc cuối</th><th>Khoảng cách gần nhất (từ lúc xuất phát)</th><th>δ nhỏ nhất / lớn nhất</th></tr>"]
    for base, png, cfg_txt, verdict, s, err in rows:
        cls = {"PASS": "ok", "FAIL": "bad"}.get(verdict, "na")
        cfg = html.escape(cfg_txt) if err is None else "<b>lỗi dựng hình</b>: %s" % html.escape(err)
        if s is None:
            s = {"out_dive": None, "out_final": None, "d3_min": None, "delta_min": None, "delta_max": None}
        d3 = "—" if s["d3_min"] is None else "%.1f m" % s["d3_min"]
        dl = ("—" if err or "KHÔNG DỰNG" in cfg_txt else "camera cố định") if s["delta_min"] is None else "%.1f° / %.1f°" % (s["delta_min"], s["delta_max"])
        out.append("<tr><td><a href=\"#%s\">%s</a></td><td>%s</td><td><span class=\"badge %s\">%s</span></td>"
                   "<td>%s / %s</td><td>%s</td><td>%s</td></tr>" % (
                       _anchor(base), html.escape(base), cfg, cls, verdict or "—", _fmt_out(s["out_dive"]),
                       _fmt_out(s["out_final"]), d3, dl))
    out.append("</table></div>")
    for base, png, _, _, _, err in rows:
        body = ("<p>Lỗi dựng hình, không có hình cho lần chạy này.</p>" if png is None else
                "<img src=\"%s\" alt=\"Báo cáo %s\" loading=\"lazy\">" % (html.escape(urllib.parse.quote(png)),
                                                                          html.escape(base)))
        out.append("<section class=\"card\" id=\"%s\"><h2>%s</h2>%s</section>" % (_anchor(base), html.escape(base), body))
    out.append("</main></body></html>\n")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", metavar="run_dir")
    ap.add_argument("--out", default=None, help="thu muc ghi <ten lan chay>.png (mac dinh: report.png trong moi run_dir)")
    ap.add_argument("--batch-html", default=None, help="ghi trang lo HTML (PNG ghi canh file nay)")
    a = ap.parse_args(argv)
    rc = 0
    if a.batch_html:
        render_batch(a.run_dirs, a.batch_html)
        print("ghi", a.batch_html)
    if a.out or not a.batch_html:
        for d in a.run_dirs:
            base = os.path.basename(os.path.normpath(d))
            if a.out:
                os.makedirs(a.out, exist_ok=True)
                png = os.path.join(a.out, base + ".png")
            else:
                png = os.path.join(d, "report.png")
            try:
                render_run(d, png)
                print("ghi", png)
            except Exception as exc:     # mot lan chay hong khong chan cac lan con lai
                print("LOI %s: %r" % (d, exc), file=sys.stderr)
                rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
