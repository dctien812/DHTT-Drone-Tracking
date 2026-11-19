"""Cong thuc cham B1a (A1-A3): recall theo co muc tieu + dao dong theo nhom, cum mat, bao dong gia.

box = (x1, y1, x2, y2) o thang 2304. Quy tac: xem docstring tests_b1/test_eval_metrics.py.
"""
import numpy as np

BANDS = ("16-57", "57-200", ">200")
_EPS = 1e-9


def size_band(w):
    if w < 16:
        return None
    if w < 57:
        return "16-57"
    if w <= 200:
        return "57-200"
    return ">200"


def iou(a, b):
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def xyxy_to_cxcywh(det):
    x1, y1, x2, y2 = det[:4]
    return ((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1) + tuple(det[4:5])


def cxcywh_to_xyxy(det):
    cx, cy, w, h = det[:4]
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2) + tuple(det[4:5])


def _hit(frame, iou_thr, conf_thr):
    return any(d[4] >= conf_thr and iou(d[:4], frame["gt"]) >= iou_thr for d in frame["dets"])


def _band_of(frame):
    return size_band(frame["gt"][2] - frame["gt"][0])


def recall_by_band(frames, iou_thr=0.5, conf_thr=0.0):
    out = {b: {"n": 0, "hit": 0} for b in BANDS + ("all",)}
    for f in frames:
        h = int(_hit(f, iou_thr, conf_thr))
        for b in ("all", _band_of(f)):
            if b is not None:
                out[b]["n"] += 1
                out[b]["hit"] += h
    for v in out.values():
        v["recall"] = v["hit"] / v["n"] if v["n"] else None
    return out


def recall_with_spread(frames, band=None, iou_thr=0.5, conf_thr=0.0, n_boot=1000, seed=0,
                       group_of=None, min_groups=5):
    cnt = {}   # nhom -> [hit, n]
    for f in frames:
        if band is not None and _band_of(f) != band:
            continue
        g = f["seg"] if group_of is None else group_of.get(f["seg"], f["seg"])
        c = cnt.setdefault(g, [0, 0])
        c[0] += int(_hit(f, iou_thr, conf_thr))
        c[1] += 1
    n_groups = len(cnt)
    tot_n = sum(c[1] for c in cnt.values())
    res = {"recall": sum(c[0] for c in cnt.values()) / tot_n if tot_n else None,
           "lo": None, "hi": None, "n_groups": n_groups,
           "computable": n_groups >= min_groups and n_groups > 0 and n_boot > 0,
           "per_group": {g: c[0] / c[1] for g, c in cnt.items()}}
    if res["computable"]:
        arr = np.array(list(cnt.values()), dtype=float)
        idx = np.random.default_rng(seed).integers(0, n_groups, size=(n_boot, n_groups))
        rec = arr[idx, 0].sum(axis=1) / arr[idx, 1].sum(axis=1)
        res["lo"], res["hi"] = (float(x) for x in np.percentile(rec, [2.5, 97.5]))
    return res


def background_kind(direction):
    try:
        return {"Bottom_Up": "sky", "Top_Down": "ground", "Horizontal": "mixed"}[direction]
    except KeyError:
        raise ValueError("huong khong hop le: %r" % (direction,)) from None


def _check(detected, fps):
    if fps <= 0:
        raise ValueError("fps phai > 0")
    if len(detected) == 0:
        raise ValueError("chuoi rong")


def loss_runs(detected, fps):
    runs, n = [], 0
    for d in detected:
        if d:
            if n:
                runs.append(n / fps)
            n = 0
        else:
            n += 1
    if n:
        runs.append(n / fps)
    return runs


def _summary(runs, duration, short_s, long_s):
    n_short = sum(r >= short_s - _EPS for r in runs)
    return {"n_short": n_short, "n_long": sum(r >= long_s - _EPS for r in runs),
            "longest_s": max(runs, default=0.0), "per_minute": n_short / (duration / 60.0),
            "duration_s": duration}


def loss_summary(detected, fps, short_s=0.25, long_s=3.0):
    _check(detected, fps)
    return _summary(loss_runs(detected, fps), len(detected) / fps, short_s, long_s)


def loss_summary_multi(list_of_detected, fps, short_s=0.25, long_s=3.0):
    for d in list_of_detected:
        _check(d, fps)
    if not list_of_detected:
        raise ValueError("khong co chuoi")
    runs = [r for d in list_of_detected for r in loss_runs(d, fps)]
    return _summary(runs, sum(len(d) for d in list_of_detected) / fps, short_s, long_s)


def false_alarm_stats(crops, conf_thr, fps, crops_per_frame):
    if not crops:
        raise ValueError("khong co vung nen")
    groups = {}
    for c in crops:
        n_det = sum(x >= conf_thr for x in c["confs"])
        for k in (c["kind"], "all"):
            g = groups.setdefault(k, {"n_crops": 0, "crops_with_fa": 0, "n_dets": 0})
            g["n_crops"] += 1
            g["crops_with_fa"] += int(n_det > 0)
            g["n_dets"] += n_det
    for g in groups.values():
        rate = g["crops_with_fa"] / g["n_crops"]
        g["per_100"] = 100.0 * rate
        g["per_second"] = rate * crops_per_frame * fps
    return groups
