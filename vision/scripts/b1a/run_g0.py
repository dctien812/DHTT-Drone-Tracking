"""B1a buoc 8 - CONG G0: cham yolov8n.pt goc (lop COCO 'airplane') tren du lieu B1a theo A1-A6.

Chi dieu phoi: suy luan (stage infer) + goi ham cham co san (eval_metrics, eval_tracker, prep_crops).
Khong sua module nao, khong huan luyen.

Chay (WSL):  cd /mnt/d/Personal/Drone-Tracking/vision && ~/venv-vision/bin/python scripts/b1a/run_g0.py <stage>
  stage: infer   suy luan CPU imgsz 480 (A6 anh 640 o imgsz 640), conf 0.01, luu phat hien tho (moi lop) vao
                 results/b1a/g0/raw_<tap>.csv (tiep tuc duoc: tap nao co meta_<tap>.json thi bo qua)
         score   doc raw_*.csv (KHONG suy luan lai), chon nguong tren VAL, tinh A1-A6 + doi chung D/D',
                 ghi g0_results.json, g0_report.md, val_curve.csv
         viz     ve 20 vung (phat hien + nhan) vao results/b1a/g0/viz/ de ra mat
Phat hien tho: cot image,cls,conf,x1,y1,x2,y2. Toa do: vung cat 480 (test/val/train/birds) hoac khung 2304
(scan: image = "doan|khung"), hoac anh goc (a6_full_*, a6_crop_* da cong lech vao toa do anh 640x512).
Gia dinh: 30 khung/giay (tan so khung MMFW khong tim duoc); 15 khung/giay de tham khao.
"""
import csv
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import eval_metrics as em  # noqa: E402
import prep_crops as pc  # noqa: E402
import prep_split as ps  # noqa: E402

VISION = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(VISION, "data", "b1a")
YOLO = os.path.join(DATA, "yolo")
INDEX = os.path.join(DATA, "index")
BIRD_FA = os.path.join(DATA, "birds_fa")
ROOT = os.path.join(VISION, "data", "mmfw-uav", "extracted")
OUT = os.path.join(VISION, "results", "b1a", "g0")
WEIGHTS = os.path.join(VISION, "weights", "yolov8n.pt")
MANIFEST = os.path.join(DATA, "split", "test_manifest.tsv")
MANIFEST_SHA = "7c67757cee4d2c3a81d3f87bc9d5519e5765c95f35e976a2178d48b07859e848"
A6_CSV = os.path.join(VISION, "verify_b1", "labels_part1_airplane.csv")
A6_DIR = os.path.join(VISION, "verify_b1", "frames")
CAMTEST = os.path.join(VISION, "..", "pi", "camtest_20261118.jpg")
EXPECT = {"test_pos": 10103, "test_off": 10103, "test_bg": 10103, "val_pos": 1279, "val_bg": 1279,
          "birds": 150, "train_pos": 1153}
CONF_LO = 0.01
FPS = 30.0
FPS_ALT = 15.0
SCAN_EVERY = 10
MERGE_IOU = 0.5
OPS_FIXED = (0.25, 0.10)


def src_img(seg, frame):
    s, d = ps.parse_segment_id(seg)
    return os.path.join(ROOT, ps._PREFIX + s, d, "Wide_Imgs", frame + ".jpg")


def read_index(split):
    with open(os.path.join(INDEX, split + ".csv"), newline="") as f:
        return list(csv.DictReader(f))


def sel_rows(split, kind):
    rows = [r for r in read_index(split) if r["kind"] == kind]
    for r in rows:
        assert r["path"], "vung cat thieu: %s" % r
    return sorted(rows, key=lambda r: (r["segment"], ps.parse_frame_name(r["frame"])))


def set_rows(name):
    sp, kind = name.split("_")
    return sel_rows(sp, kind)


def set_paths(name):
    if name == "birds":
        return [os.path.join(BIRD_FA, f) for f in sorted(os.listdir(BIRD_FA)) if f.endswith(".png")]
    return [os.path.join(YOLO, "images", r["path"]) for r in set_rows(name)]


def set_keys(name):
    if name == "birds":
        return [os.path.basename(p) for p in set_paths(name)]
    return [r["path"] for r in set_rows(name)]


def scan_frames():
    """Mau moi SCAN_EVERY khung (vi tri 0,10,20,...) cua moi doan test: [(row_pos, ...)]."""
    rows = sel_rows("test", "pos")
    by = defaultdict(list)
    for r in rows:
        by[r["segment"]].append(r)
    out = []
    for seg in sorted(by):
        out.extend(by[seg][::SCAN_EVERY])
    return out


# ------------------------------------------------------------------ infer
def _rows_of(res, dx=0, dy=0):
    b = res.boxes
    if b is None or len(b) == 0:
        return []
    xy, cf, cl = b.xyxy.numpy(), b.conf.numpy(), b.cls.numpy()
    return [(int(c), float(p), x1 + dx, y1 + dy, x2 + dx, y2 + dy) for (x1, y1, x2, y2), p, c in zip(xy, cf, cl)]


def _fmt(img, d):
    return [img, d[0], "%.5f" % d[1]] + ["%.2f" % v for v in d[2:]]


def _write_set(name, writer_rows, n_images, secs, extra=None):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "raw_%s.csv" % name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "cls", "conf", "x1", "y1", "x2", "y2"])
        w.writerows(writer_rows)
    meta = {"set": name, "n_images": n_images, "n_det_rows": len(writer_rows), "seconds": round(secs, 1),
            "imgs_per_s": round(n_images / secs, 2) if secs else None}
    meta.update(extra or {})
    with open(os.path.join(OUT, "meta_%s.json" % name), "w") as f:
        json.dump(meta, f, indent=1)
    print("XONG", meta, flush=True)


def _predict(model, items, imgsz, chunk=64):
    """items: duong dan hoac mang BGR. Tra ve danh sach ket qua theo dung thu tu."""
    out = []
    for i in range(0, len(items), chunk):
        out.extend(model.predict(items[i:i + chunk], imgsz=imgsz, conf=CONF_LO, device="cpu", verbose=False))
    return out


def stage_infer(only=None):
    import torch
    from PIL import Image
    from ultralytics import YOLO
    model = YOLO(WEIGHTS)
    names = {int(k): v for k, v in model.names.items()}
    air = [k for k, v in names.items() if v == "airplane"]
    assert air == [4], air
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "classes.json"), "w") as f:
        json.dump({"names": names, "airplane": 4, "bird": 14, "kite": 33,
                   "ultralytics": __import__("ultralytics").__version__, "torch": torch.__version__,
                   "threads": torch.get_num_threads(), "conf": CONF_LO, "weights": WEIGHTS}, f, indent=1)
    todo = lambda n: (only is None or n in only) and not os.path.exists(os.path.join(OUT, "meta_%s.json" % n))

    for name in ("val_pos", "val_bg", "birds", "test_pos", "test_off", "test_bg", "train_pos"):
        if not todo(name):
            continue
        paths, keys = set_paths(name), set_keys(name)
        assert len(paths) == EXPECT[name], (name, len(paths))
        rows = set_rows(name) if name != "birds" else None
        t0 = time.time()
        wr = []
        for i in range(0, len(paths), 512):
            res = _predict(model, paths[i:i + 512], 480)
            for k, r in zip(keys[i:i + 512], res):
                wr.extend(_fmt(k, d) for d in _rows_of(r))
            print(name, min(i + 512, len(paths)), "/", len(paths), "%.0fs" % (time.time() - t0), flush=True)
        _write_set(name, wr, len(paths), time.time() - t0)

    if todo("scan"):
        fr = scan_frames()
        tiles = pc.tile_frame()
        assert len(tiles) == 32
        t0, wr = time.time(), []
        for i, r in enumerate(fr):
            img = pc.resize_to_width(np.asarray(Image.open(src_img(r["segment"], r["frame"])).convert("RGB")))
            arrs = [np.ascontiguousarray(pc.extract_crop(img, x, y)[:, :, ::-1]) for x, y in tiles]  # RGB -> BGR
            res = _predict(model, arrs, 480, chunk=32)
            key = "%s|%s" % (r["segment"], r["frame"])
            for (x, y), rr in zip(tiles, res):
                wr.extend(_fmt(key, d) for d in _rows_of(rr, x, y))
            if (i + 1) % 50 == 0:
                print("scan", i + 1, "/", len(fr), "%.0fs" % (time.time() - t0), flush=True)
        _write_set("scan", wr, len(fr), time.time() - t0, {"tiles_per_frame": 32, "n_tile_images": 32 * len(fr)})

    if todo("a6"):
        t0, wf, wc, wt = time.time(), [], [], []
        with open(A6_CSV, newline="") as f:
            lab = list(csv.DictReader(f))
        nimg = 0
        for r in lab:
            p = os.path.join(A6_DIR, "%s_f%04d.png" % (r["video"], int(r["frame"])))
            assert os.path.exists(p), p
            key = os.path.basename(p)
            im = Image.open(p).convert("RGB")
            W, H = im.size
            assert (W, H) == (640, 512), (W, H)
            bgr = np.ascontiguousarray(np.asarray(im)[:, :, ::-1])
            wf.extend(_fmt(key, d) for d in _rows_of(_predict(model, [bgr], 640)[0]))
            cx, cy = (int(r["x1"]) + int(r["x2"])) / 2, (int(r["y1"]) + int(r["y2"])) / 2
            x0 = int(min(max(round(cx - 240), 0), W - 480))
            y0 = int(min(max(round(cy - 240), 0), H - 480))
            wc.extend(_fmt(key, d) for d in _rows_of(_predict(model, [np.ascontiguousarray(bgr[y0:y0 + 480, x0:x0 + 480])], 480)[0], x0, y0))
            nimg += 1
        _write_set("a6_full", wf, nimg, time.time() - t0, {"imgsz": 640})
        _write_set("a6_crop", wc, nimg, 0.0, {"imgsz": 480, "crop": "480x480 quanh tam nhan, kep vao anh"})
        im = Image.open(CAMTEST).convert("RGB")
        img = pc.resize_to_width(np.asarray(im))
        h, w = img.shape[:2]
        tl = pc.tile_frame(frame_h=h)
        arrs = [np.ascontiguousarray(pc.extract_crop(img, x, y)[:, :, ::-1]) for x, y in tl]
        t1 = time.time()
        res = _predict(model, arrs, 480, chunk=32)
        wt = []
        for (x, y), rr in zip(tl, res):
            wt.extend(_fmt("camtest", d) for d in _rows_of(rr, x, y))
        _write_set("a6_camtest", wt, 1, time.time() - t1,
                   {"orig_size": list(im.size), "resized": [w, h], "n_tiles": len(tl)})


# ------------------------------------------------------------------ score helpers
def load_raw(name):
    d = defaultdict(list)
    with open(os.path.join(OUT, "raw_%s.csv" % name), newline="") as f:
        for r in csv.DictReader(f):
            d[r["image"]].append((int(r["cls"]), float(r["conf"]), float(r["x1"]), float(r["y1"]),
                                  float(r["x2"]), float(r["y2"])))
    return d


def load_meta(name):
    with open(os.path.join(OUT, "meta_%s.json" % name)) as f:
        return json.load(f)


AIR, BIRD, KITE = 4, 14, 33


def to_frames(rows, dets, cls=AIR):
    """frames cho eval_metrics: gt va dets (x1,y1,x2,y2,conf) o thang khung 2304."""
    out = []
    for r in rows:
        x0, y0 = int(r["x0"]), int(r["y0"])
        ds = [pc.crop_to_frame(d[2:6], x0, y0) + (d[1],) for d in dets.get(r["path"], []) if d[0] == cls]
        out.append({"seg": r["segment"], "frame": r["frame"], "gt": tuple(float(r[k]) for k in ("fx1", "fy1", "fx2", "fy2")),
                    "dets": ds})
    return out


def direction(seg):
    return seg.split("/")[1]


def rb(frames, thr):
    return em.recall_by_band(frames, 0.5, thr)


def compact_rb(res):
    return {b: {"n": v["n"], "hit": v["hit"], "recall": v["recall"]} for b, v in res.items()}


def spread(frames, thr, band=None):
    r = em.recall_with_spread(frames, band=band, conf_thr=thr)
    return {"recall": r["recall"], "lo": r["lo"], "hi": r["hi"], "n_groups": r["n_groups"],
            "computable": r["computable"], "per_group": r["per_group"]}


def a1_block(frames, thr):
    out = {"by_band": compact_rb(rb(frames, thr)), "spread": {}}
    for b in (None,) + em.BANDS:
        out["spread"]["all" if b is None else b] = spread(frames, thr, b)
    out["by_direction"] = {d: compact_rb(rb([f for f in frames if direction(f["seg"]) == d], thr))
                           for d in ("Top_Down", "Horizontal", "Bottom_Up")}
    out["by_segment"] = {s: compact_rb(rb([f for f in frames if f["seg"] == s], thr))
                         for s in sorted({f["seg"] for f in frames})}
    return out


def fa_crops(rows, dets, kindfn):
    return [{"kind": kindfn(r), "confs": [d[1] for d in dets.get(r["path"], []) if d[0] == AIR]} for r in rows]


def hit_seq(frames, thr):
    return [bool(rb([f], thr)["all"]["hit"]) for f in frames]


def by_seg(frames):
    d = defaultdict(list)
    for f in frames:
        d[f["seg"]].append(f)
    return {s: sorted(v, key=lambda f: ps.parse_frame_name(f["frame"])) for s, v in sorted(d.items())}


def a4_block(frames, thr, fps):
    import eval_tracker as et
    segs = by_seg(frames)
    out = {"fps": fps, "thr": thr}
    for mode in ("all", "top1"):
        m_t = m_n = c_t = c_n = 0
        per = {}
        for s, fl in segs.items():
            mf = [{"t": i / fps, "dets": [em.xyxy_to_cxcywh(d) for d in f["dets"] if d[4] >= thr]} for i, f in enumerate(fl)]
            cf = [{"t": i / fps, "dets": [em.xyxy_to_cxcywh(f["gt"] + (1.0,))]} for i, f in enumerate(fl)]
            a, n = et.track_time_fraction(mf, mode=mode, return_counts=True)
            b, n2 = et.track_time_fraction(cf, mode=mode, return_counts=True)
            m_t += a
            m_n += n
            c_t += b
            c_n += n2
            per[s] = {"model": a / n, "ceiling": b / n2, "ratio": (a / n) / (b / n2) if b else None}
        mm, cc = m_t / m_n, c_t / c_n
        out[mode] = {"model": mm, "ceiling": cc, "ratio": mm / cc, "per_segment": per}
    return out


def leak28():
    """28 khung E'/Horizontal tuong quan >=0.98 voi khung hoc/val (cong thuc cua leak_step6.stage_near,
    doc leak_feats.npz va split/*.txt da co)."""
    z = np.load(os.path.join(VISION, "results", "b1a", "step6", "leak_feats.npz"))
    seg, frame, F = z["seg"], z["frame"], z["F"]
    key = {(str(s), str(f)): i for i, (s, f) in enumerate(zip(seg, frame))}
    tv = []
    for k in ("train", "val"):
        with open(os.path.join(DATA, "split", k + ".txt")) as f:
            tv += [key[(l.split("\t")[1], l.rstrip("\n").split("\t")[2])] for l in f]
    te = [i for i, s in enumerate(seg) if str(s).split("/")[0] in ("E", "E'")]

    def norm(A):
        A = A - A.mean(1, keepdims=True)
        return A / np.maximum(np.linalg.norm(A, axis=1, keepdims=True), 1e-6)
    c = (norm(F[te]) @ norm(F[tv]).T).max(1)
    return sorted((str(seg[te[i]]), str(frame[te[i]])) for i in np.where(c >= 0.98)[0])


# ------------------------------------------------------------------ score
def stage_score():
    assert ps.verify_test_manifest(MANIFEST), "verify_test_manifest KHONG dat"
    import hashlib
    sha = hashlib.sha256(open(MANIFEST, "rb").read()).hexdigest()
    assert sha == MANIFEST_SHA, sha
    R = {"manifest_verified": True, "manifest_sha256": sha, "fps_assumed": FPS}
    meta = {n: load_meta(n) for n in EXPECT}
    for n, k in EXPECT.items():
        assert meta[n]["n_images"] == k, (n, meta[n])
    raw = {n: load_raw(n) for n in EXPECT}
    rows = {n: set_rows(n) for n in EXPECT if n != "birds"}
    for n in raw:  # moi anh trong raw phai thuoc chi muc
        valid = set(set_keys(n))
        assert len(valid) == EXPECT[n] and set(raw[n]) <= valid, n
    R["images_scored"] = {n: len(set_keys(n)) for n in EXPECT}
    R["inference_seconds"] = {n: meta[n]["seconds"] for n in EXPECT}
    R["inference_imgs_per_s"] = {n: meta[n]["imgs_per_s"] for n in EXPECT}
    R["truncated"] = {n: sum(int(r["truncated"]) for r in rows[n]) for n in ("test_pos", "test_off", "val_pos", "train_pos")}

    F = {n: to_frames(rows[n], raw[n]) for n in ("test_pos", "test_off", "val_pos", "train_pos")}
    # ---- (b) nguong tren VAL
    val_bg = fa_crops(rows["val_bg"], raw["val_bg"], lambda r: r["background_kind"])
    grid = [round(0.01 + 0.005 * i, 3) for i in range(198)]
    curve = []
    for t in grid:
        fa = em.false_alarm_stats(val_bg, t, FPS, 1)["all"]
        rec = rb(F["val_pos"], t)
        curve.append({"thr": t, "val_fa_per_100": fa["per_100"], "val_fa_crops": fa["crops_with_fa"],
                      "val_recall": rec["all"]["recall"], **{"val_recall_" + b: rec[b]["recall"] for b in em.BANDS}})
    ok = [c for c in curve if c["val_fa_per_100"] <= 1.0]
    op = ok[0]["thr"] if ok else None
    with open(os.path.join(OUT, "val_curve.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(curve[0]))
        w.writeheader()
        w.writerows(curve)
    R["operating_threshold"] = op
    R["op_selection"] = {"rule": "nguong thap nhat tren luoi 0.005 co bao dong gia val <= 1/100 vung nen (recall giam dan theo nguong nen nguong thap nhat cho recall cao nhat)",
                         "n_val_bg": len(val_bg), "chosen": ok[0] if ok else None,
                         "feasible": bool(ok)}
    if op is None:
        print("KHONG co nguong nao dat FA val <= 1/100", flush=True)
        json.dump(R, open(os.path.join(OUT, "g0_results.json"), "w"), indent=1, default=str)
        return
    thrs = [op] + [t for t in OPS_FIXED if t != op]
    R["thresholds"] = thrs

    excl = leak28()
    R["leak28"] = {"n": len(excl), "frames": [list(x) for x in excl]}
    exset = set(excl)
    segs6 = sorted({f["seg"] for f in F["test_pos"]})
    assert len(segs6) == 6, segs6
    A = {}
    bgk = lambda r: r["background_kind"]
    birds_crops = [{"kind": "bird", "confs": [d[1] for d in raw["birds"].get(k, []) if d[0] == AIR]} for k in set_keys("birds")]
    test_bg = fa_crops(rows["test_bg"], raw["test_bg"], bgk)
    scan_rows = scan_frames()
    scan_raw = load_raw("scan")
    assert load_meta("scan")["n_images"] == len(scan_rows)
    assert set(scan_raw) <= {"%s|%s" % (r["segment"], r["frame"]) for r in scan_rows}
    scan_fr = []
    for r in scan_rows:
        k = "%s|%s" % (r["segment"], r["frame"])
        scan_fr.append({"seg": r["segment"], "frame": r["frame"], "gt": tuple(float(r[c]) for c in ("fx1", "fy1", "fx2", "fy2")),
                        "dets": [(d[2], d[3], d[4], d[5], d[1]) for d in scan_raw.get(k, []) if d[0] == AIR]})

    for t in thrs:
        a = {}
        a["A1"] = a1_block(F["test_pos"], t)
        a["A1_excl28"] = a1_block([f for f in F["test_pos"] if (f["seg"], f["frame"]) not in exset], t)
        a["A1_excl28"]["n_excluded"] = sum((f["seg"], f["frame"]) in exset for f in F["test_pos"])
        seqs = {s: hit_seq(fl, t) for s, fl in by_seg(F["test_pos"]).items()}
        a["A2"] = {"fps": FPS, "pooled": em.loss_summary_multi(list(seqs.values()), FPS),
                   "per_segment": {s: em.loss_summary(v, FPS) for s, v in seqs.items()},
                   "frames_detected_fraction": {s: sum(v) / len(v) for s, v in seqs.items()}}
        a["A3"] = {"test_bg": em.false_alarm_stats(test_bg, t, FPS, 1),
                   "birds": em.false_alarm_stats(birds_crops, t, FPS, 1),
                   "val_bg": em.false_alarm_stats(val_bg, t, FPS, 1), "note": "per_second = ti le vung co BDG x crops_per_frame(1) x fps(30)"}
        a["A4"] = {"fps30": a4_block(F["test_pos"], t, FPS), "fps15": a4_block(F["test_pos"], t, FPS_ALT)}
        # A5
        a["A5_off"] = {"by_band": compact_rb(rb(F["test_off"], t)),
                       "spread": {("all" if b is None else b): spread(F["test_off"], t, b) for b in (None,) + em.BANDS}}
        sc = []
        for f in scan_fr:
            ds = pc_merge([d for d in f["dets"] if d[4] >= t])
            sc.append({"seg": f["seg"], "frame": f["frame"], "gt": f["gt"], "dets": ds})
        n_fa0 = [sum(em.iou(d[:4], f["gt"]) == 0 for d in f["dets"]) for f in sc]
        n_fa5 = [sum(em.iou(d[:4], f["gt"]) < 0.5 for d in f["dets"]) for f in sc]
        a["A5_scan"] = {"n_frames": len(sc), "merge_iou": MERGE_IOU, "by_band": compact_rb(rb(sc, 0.0)),
                        "spread": {("all" if b is None else b): spread(sc, 0.0, b) for b in (None,) + em.BANDS},
                        "fa_per_frame_no_overlap": float(np.mean(n_fa0)), "fa_per_frame_iou_lt_0.5": float(np.mean(n_fa5)),
                        "frames_with_fa_no_overlap": float(np.mean([x > 0 for x in n_fa0])),
                        "by_segment_fa_no_overlap": {s: float(np.mean([x for x, f in zip(n_fa0, sc) if f["seg"] == s])) for s in segs6},
                        "by_segment_recall": {s: compact_rb(rb([f for f in sc if f["seg"] == s], 0.0))["all"] for s in segs6}}
        # doi chung D/D' vs E/E' (cung nguong)
        ctrl = F["val_pos"] + F["train_pos"]
        grp = lambda fl, sets: [f for f in fl if f["seg"].split("/")[0] in sets]
        a["control"] = {
            "D_Dprime_valtrain": {"n": len(ctrl), "by_band": compact_rb(rb(ctrl, t))},
            "E_Eprime_test": {"by_band": compact_rb(rb(F["test_pos"], t))},
            "by_set": {s: {"by_band": compact_rb(rb(grp(ctrl if s in ("D", "D'") else F["test_pos"], (s,)), t))} for s in ("D", "D'", "E", "E'")},
            "by_segment_ctrl": {s: compact_rb(rb([f for f in ctrl if f["seg"] == s], t))["all"] for s in sorted({f["seg"] for f in ctrl})},
        }
        A[str(t)] = a
    R["by_threshold"] = A

    # ---- lop COCO gan cho may bay mo hinh (test pos): khung co phat hien lop X IoU>=0.5
    cls_stats = {}
    names = json.load(open(os.path.join(OUT, "classes.json")))["names"]
    for t in (0.01, 0.10, 0.25, op):
        hits = Counter()
        top = Counter()
        for r in rows["test_pos"]:
            gt = tuple(float(r[c]) for c in ("fx1", "fy1", "fx2", "fy2"))
            best = None
            seen = set()
            for d in sorted(raw["test_pos"].get(r["path"], []), key=lambda d: -d[1]):
                if d[1] < t:
                    continue
                bx = pc.crop_to_frame(d[2:6], int(r["x0"]), int(r["y0"]))
                if em.iou(bx, gt) >= 0.5:
                    if d[0] not in seen:
                        hits[d[0]] += 1
                        seen.add(d[0])
                    if best is None:
                        best = d[0]
            top[best if best is not None else -1] += 1
        cls_stats[str(t)] = {"frames_with_class_hit_iou0.5": {names[str(k)]: v for k, v in hits.most_common()},
                             "top_conf_class_among_hits": {(names[str(k)] if k >= 0 else "none"): v for k, v in top.most_common()},
                             "bird_hits": hits[BIRD], "kite_hits": hits[KITE], "airplane_hits": hits[AIR], "n": len(rows["test_pos"])}
    R["coco_class_on_model_plane"] = cls_stats

    # ---- A6
    lab = list(csv.DictReader(open(A6_CSV, newline="")))
    a6 = {"n_labeled": len(lab), "sure_counts": dict(Counter(r["sure"] for r in lab))}
    for nm in ("a6_full", "a6_crop"):
        d = load_raw(nm)
        assert load_meta(nm)["n_images"] == len(lab)
        res = {}
        for t in [0.01] + thrs:
            hit = anyair = 0
            hit_cls = Counter()
            for r in lab:
                key = "%s_f%04d.png" % (r["video"], int(r["frame"]))
                gt = tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))
                ds = [x for x in d.get(key, []) if x[1] >= t]
                h = any(x[0] == AIR and em.iou(x[2:6], gt) >= 0.5 for x in ds)
                hit += h
                anyair += any(x[0] == AIR for x in ds)
                for c in {x[0] for x in ds if em.iou(x[2:6], gt) >= 0.5}:
                    hit_cls[names[str(c)]] += 1
            res[str(t)] = {"frames_airplane_iou0.5": hit, "frames_any_airplane_det": anyair, "iou0.5_by_class": dict(hit_cls)}
        a6[nm] = res
    cam = load_raw("a6_camtest")
    mc = load_meta("a6_camtest")
    a6["camtest"] = {"meta": {k: mc[k] for k in ("orig_size", "resized", "n_tiles")}}
    for t in [0.01] + thrs:
        ds = pc_merge([(d[2], d[3], d[4], d[5], d[1]) for d in cam.get("camtest", []) if d[0] == AIR and d[1] >= t])
        a6["camtest"][str(t)] = {"airplane_dets_after_merge": len(ds), "max_conf": max([d[4] for d in ds], default=None)}
    a6["camtest"]["all_class_dets_conf>=0.25"] = dict(Counter(names[str(d[0])] for d in cam.get("camtest", []) if d[1] >= 0.25))
    R["A6"] = a6
    with open(os.path.join(OUT, "g0_results.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    write_md(R)
    print("score xong, nguong van hanh", op)


def pc_merge(dets):
    return pc.merge_detections(dets, MERGE_IOU)


def pct(v):
    return "n/a" if v is None else "%.3f" % v


def write_md(R):
    L = ["# G0 - yolov8n.pt goc (airplane) tren B1a\n",
         "manifest sha256 %s verify %s; 30 khung/giay (gia dinh)\n" % (R["manifest_sha256"], R["manifest_verified"]),
         "Nguong van hanh (chon tren VAL, FA val<=1/100): **%s**; chi tiet: %s\n" % (R["operating_threshold"], json.dumps(R["op_selection"]["chosen"]))]
    L.append("Anh da cham: %s\nThoi gian suy luan (s): %s\nTruncated: %s\n" % (R["images_scored"], R["inference_seconds"], R["truncated"]))
    for t, a in R["by_threshold"].items():
        L.append("\n## Nguong %s\n" % t)
        L.append("### A1 test (recall IoU0.5; spread = bootstrap theo doan)\n| dai | n | recall | lo | hi | n_nhom |\n|---|---|---|---|---|---|")
        for b in ("16-57", "57-200", ">200", "all"):
            s, v = a["A1"]["spread"][b], a["A1"]["by_band"][b]
            L.append("| %s | %d | %s | %s | %s | %d |" % (b, v["n"], pct(s["recall"]), pct(s["lo"]), pct(s["hi"]), s["n_groups"]))
        L.append("\nA1 theo huong / doan (recall: 16-57, 57-200, >200, all)")
        for k in ("by_direction", "by_segment"):
            for g, v in a["A1"][k].items():
                L.append("- %s: " % g + ", ".join("%s=%s (n=%d)" % (b, pct(v[b]["recall"]), v[b]["n"]) for b in ("16-57", "57-200", ">200", "all")))
        e = a["A1_excl28"]
        L.append("\nA1 loai %d khung: " % e["n_excluded"] + ", ".join("%s=%s" % (b, pct(e["spread"][b]["recall"])) for b in ("16-57", "57-200", ">200", "all")))
        p = a["A2"]["pooled"]
        L.append("\n### A2 (30 fps)\npooled: cum>=0.25s %d (%.2f/phut), cum>=3s %d, dai nhat %.2fs, tong %.0fs" % (p["n_short"], p["per_minute"], p["n_long"], p["longest_s"], p["duration_s"]))
        for s, v in a["A2"]["per_segment"].items():
            L.append("- %s: cum>=0.25s %d, >=3s %d, dai nhat %.2fs, %.2f/phut" % (s, v["n_short"], v["n_long"], v["longest_s"], v["per_minute"]))
        L.append("\n### A3 (bao dong gia theo vung; per_100)")
        for k in ("test_bg", "birds", "val_bg"):
            for g, v in a["A3"][k].items():
                L.append("- %s %s: %d/%d vung co BDG (%.2f/100), %d phat hien, %.3f/s" % (k, g, v["crops_with_fa"], v["n_crops"], v["per_100"], v["n_dets"], v["per_second"]))
        L.append("\n### A4 (ti le bam)")
        for fk in ("fps30", "fps15"):
            for m in ("all", "top1"):
                v = a["A4"][fk][m]
                L.append("- %s %s: model %.3f, tran %.3f, ti so %.3f" % (fk, m, v["model"], v["ceiling"], v["ratio"]))
        L.append("\n### A5")
        L.append("lech tam: " + ", ".join("%s=%s (n=%d)" % (b, pct(a["A5_off"]["by_band"][b]["recall"]), a["A5_off"]["by_band"][b]["n"]) for b in ("16-57", "57-200", ">200", "all")))
        s = a["A5_scan"]
        L.append("quet 32 o (%d khung): " % s["n_frames"] + ", ".join("%s=%s (n=%d)" % (b, pct(s["by_band"][b]["recall"]), s["by_band"][b]["n"]) for b in ("16-57", "57-200", ">200", "all"))
                 + "; BDG/khung (khong chong lan) %.3f, (IoU<0.5) %.3f" % (s["fa_per_frame_no_overlap"], s["fa_per_frame_iou_lt_0.5"]))
        L.append("\n### Doi chung (recall theo dai)")
        for g, v in a["control"]["by_set"].items():
            L.append("- %s: " % g + ", ".join("%s=%s (n=%d)" % (b, pct(v["by_band"][b]["recall"]), v["by_band"][b]["n"]) for b in ("16-57", "57-200", ">200", "all")))
    L.append("\n## Lop COCO tren may bay mo hinh (test pos)\n```\n%s\n```" % json.dumps(R["coco_class_on_model_plane"], indent=1))
    L.append("\n## A6\n```\n%s\n```" % json.dumps(R["A6"], indent=1))
    with open(os.path.join(OUT, "g0_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ------------------------------------------------------------------ viz
def stage_viz():
    import cv2
    R = json.load(open(os.path.join(OUT, "g0_results.json")))
    op = R["operating_threshold"]
    raw = {n: load_raw(n) for n in ("test_pos", "test_off", "test_bg")}
    os.makedirs(os.path.join(OUT, "viz"), exist_ok=True)
    rng = random.Random(1)
    pick = []

    def choose(name, verdict_fn, n_true, n_false):
        rows = set_rows(name)
        t, f = [], []
        for r in rows:
            (t if verdict_fn(r) else f).append(r)
        pick.extend((name, v) for v in rng.sample(t, n_true) + rng.sample(f, n_false))

    def hit(name):
        def fn(r):
            fr = to_frames([r], raw[name])[0]
            return bool(rb([fr], op)["all"]["hit"])
        return fn

    def fa(r):
        return any(d[0] == AIR and d[1] >= op for d in raw["test_bg"].get(r["path"], []))
    choose("test_pos", hit("test_pos"), 5, 5)
    choose("test_off", hit("test_off"), 2, 2)
    choose("test_bg", fa, 3, 3)
    lines = ["id\tfile\tloai\tscript"]
    for i, (name, r) in enumerate(pick):
        img = cv2.imread(os.path.join(YOLO, "images", r["path"]))
        x0, y0 = int(r["x0"]), int(r["y0"])
        if name != "test_bg":
            gt = [float(r[k]) for k in ("fx1", "fy1", "fx2", "fy2")]
            cv2.rectangle(img, (int(gt[0] - x0), int(gt[1] - y0)), (int(gt[2] - x0), int(gt[3] - y0)), (0, 255, 0), 1)
        for d in raw[name].get(r["path"], []):
            if d[1] >= op:
                col = (0, 0, 255) if d[0] == AIR else (255, 128, 0)
                cv2.rectangle(img, (int(d[2]), int(d[3])), (int(d[4]), int(d[5])), col, 1)
                cv2.putText(img, "%d:%.2f" % (d[0], d[1]), (int(d[2]), max(int(d[3]) - 3, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1)
        if name == "test_bg":
            v = "BDG" if fa(r) else "sach"
        else:
            v = "TRUNG" if hit(name)(r) else "TRUOT"
        cv2.imwrite(os.path.join(OUT, "viz", "%02d_%s.png" % (i, v)), img)
        lines.append("%02d\t%s\t%s\t%s" % (i, r["path"], name, v))
    open(os.path.join(OUT, "viz", "viz_list.tsv"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else "score"
    if st == "infer":
        stage_infer(set(sys.argv[2:]) or None)
    elif st == "score":
        stage_score()
    elif st == "viz":
        stage_viz()
    else:
        raise SystemExit("stage: infer | score | viz")
