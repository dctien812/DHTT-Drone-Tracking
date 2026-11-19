"""B1a viec B1a: cham model YOLOv8n da huan luyen (luot EE, DD) theo cach cong G0 (run_g0.py), CPU.

Dung lai ham cua run_g0 (to_frames, a1_block, a4_block, hit_seq, set_rows...), eval_metrics, prep_crops.
Khong sua module nao. Khong dung card (device="cpu"). Nguong chon tren VAL cua luot (quy tac G0:
nguong thap nhat tren luoi 0.005 co BDG val <= 1/100 vung nen), KHONG chon tren tap kiem.

Chay (WSL): cd /mnt/d/Personal/Drone-Tracking/vision && ~/venv-vision/bin/python -I scripts/b1a/run_eval_trained.py <stage> <tag>
  tag: EE | DD | ORIG (ORIG = yolov8n.pt goc, lop airplane 4, chi dung cho stage verify)
  stage: verify   chay model goc tren mau E+E' (300 khung dau moi doan + 1/10 vung nen) -> so voi raw G0 cung anh
         infer    suy luan CPU imgsz 480 conf 0.01 val_pos,val_bg,birds,test_pos,test_bg (tiep tuc duoc)
         score    chon nguong tren val, tinh A1,A2,A3,A4 -> results.json, report.md
         sample   (tuy chon) nhu infer nhung chi mot mau theo doan, xem SAMPLE_EVERY
Luot EE: kiem = E+E' (10103 khung, vung cat da co trong data/b1a/yolo/images/test).
Luot DD: kiem = D+D' (8552 khung, theo prep_split.all_folds); vung cat pos/bg tao TRONG BO NHO bang cung ham/seed
 voi run_step6.do_frame (khong ghi PNG).
"""
import csv
import hashlib
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import eval_metrics as em  # noqa: E402
import prep_crops as pc  # noqa: E402
import prep_split as ps  # noqa: E402
import run_g0 as g  # noqa: E402
import run_step6 as rs  # noqa: E402

VISION = g.VISION
DATA = g.DATA
OUT_ROOT = os.path.join(VISION, "results", "b1a", "eval_trained")
G0_OUT = os.path.join(VISION, "results", "b1a", "g0")
W = {"EE": os.path.join(VISION, "results", "b1a", "train", "runs", "b1a_EE_s0", "weights", "best.pt"),
     "DD": os.path.join(VISION, "results", "b1a", "train", "runs", "b1a_DD_s0", "weights", "best.pt"),
     "ORIG": g.WEIGHTS, "ORIG_DD": g.WEIGHTS}
DONE_FLAG = {"EE": "EE.done", "DD": "DD.done"}
THREADS = 8
FPS = g.FPS
GRID = [round(0.01 + 0.005 * i, 3) for i in range(198)]
EXTRA_THR = (0.25,)  # chi de tham khao, khong dung chon
WORKERS = 6
VERIFY_FIRST = 300
VERIFY_BG_EVERY = 10
EXPECT_DD = 8552


def cls_of(model):
    names = {int(k): v for k, v in model.names.items()}
    if len(names) == 1 and 0 in names:  # model lop don (single_cls): ten lop co the la 'item', lop 0 = may bay
        return 0
    assert names.get(4) == "airplane", names
    return 4


def sha_manifest():
    s = hashlib.sha256(open(g.MANIFEST, "rb").read()).hexdigest()
    assert s == g.MANIFEST_SHA, s
    return s


# ---------------------------------------------------------------- tap anh
def index_by_name():
    d = {}
    for part in ("train", "val", "test"):
        with open(os.path.join(g.INDEX, part + ".csv"), newline="") as f:
            for r in csv.DictReader(f):
                if r["path"]:
                    d[os.path.splitext(os.path.basename(r["path"]))[0]] = r
    return d


def val_rows(tag, kind):
    """Anh val cua luot (sets/<tag>/images/val), tra (rows, paths) sap theo (doan, khung)."""
    fold = {"EE": "EE", "DD": "DD", "ORIG": "EE", "ORIG_DD": "DD"}[tag]
    vdir = os.path.join(DATA, "sets", fold, "images", "val")
    idx = index_by_name()
    out = []
    for fn in os.listdir(vdir):
        r = idx[os.path.splitext(fn)[0]]
        if r["kind"] == kind:
            out.append((r, os.path.join(vdir, fn)))
    out.sort(key=lambda t: (t[0]["segment"], ps.parse_frame_name(t[0]["frame"])))
    return [t[0] for t in out], [t[1] for t in out]


def ee_test(kind):
    rows = g.sel_rows("test", kind)
    return rows, [os.path.join(g.YOLO, "images", r["path"]) for r in rows]


def dd_frames():
    sp = ps.all_folds(ps.discover_segments(rs.ROOT), val_sparse_n=3)["DD"]
    assert sum(len(v) for v in sp["test"].values()) == EXPECT_DD
    assert all(ps.parse_segment_id(s)[0] in ("D", "D'") for s in sp["test"])
    return [(s, f) for s in sorted(sp["test"]) for f in sp["test"][s]]


def dd_job(job):
    """Tao vung cat pos + bg (BGR) cho mot khung, cung cach run_step6.do_frame. Tra (rows, arrays)."""
    import cv2
    from PIL import Image
    seg, frame = job
    ip, xp = rs.src_paths(seg, frame)
    ann = pc.parse_voc(xp)
    fbox = pc.scale_box(ann["box"], pc.FRAME_W / ann["size"][0])
    img = pc.resize_to_width(np.asarray(Image.open(ip).convert("RGB")))
    d = ps.parse_segment_id(seg)[1]
    wdt = fbox[2] - fbox[0]
    rows, arrs = {}, {}
    for kind in ("pos", "bg"):
        seed = rs.frame_seed_for(kind, seg, frame)
        name = "%s_%s_%s" % (rs.tag(seg), frame, kind)
        base = dict(kind=kind, segment=seg, frame=frame, fx1=fbox[0], fy1=fbox[1], fx2=fbox[2], fy2=fbox[3],
                    box_w=wdt, background_kind=em.background_kind(d), path="test/%s.png" % name)
        if kind == "pos":
            c = pc.positive_crop(fbox, seed)
            base.update(x0=c["x0"], y0=c["y0"], truncated=int(c["truncated"]))
        else:
            c = pc.background_crop([fbox], seed)
            if c is None:
                continue
            base.update(x0=c["x0"], y0=c["y0"], truncated=0)
        rows[kind] = base
        arrs[kind] = np.ascontiguousarray(pc.extract_crop(img, base["x0"], base["y0"])[:, :, ::-1])
    return rows, arrs


# ---------------------------------------------------------------- suy luan
def load_model(tag):
    import torch
    torch.set_num_threads(THREADS)
    from ultralytics import YOLO
    m = YOLO(W[tag])
    return m, cls_of(m), torch


def rows_of(res, cid):
    b = res.boxes
    if b is None or len(b) == 0:
        return []
    xy, cf, cl = b.xyxy.numpy(), b.conf.numpy(), b.cls.numpy()
    return [(int(c), float(p), *[float(v) for v in xyxy]) for xyxy, p, c in zip(xy, cf, cl)]


def predict_timed(model, items, tm, chunk=64):
    out = []
    for i in range(0, len(items), chunk):
        t0 = time.time()
        res = model.predict(items[i:i + chunk], imgsz=480, conf=g.CONF_LO, device="cpu", verbose=False)
        tm[0] += time.time() - t0
        out.extend(res)
    return out


def write_raw(outdir, name, keys, dets_list, n_images, secs, extra=None):
    os.makedirs(outdir, exist_ok=True)
    wr = []
    for k, ds in zip(keys, dets_list):
        wr.extend(g._fmt(k, d) for d in ds)
    with open(os.path.join(outdir, "raw_%s.csv" % name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "cls", "conf", "x1", "y1", "x2", "y2"])
        w.writerows(wr)
    meta = {"set": name, "n_images": n_images, "n_det_rows": len(wr), "infer_seconds": round(secs, 1),
            "ms_per_tile": round(1000 * secs / n_images, 2) if n_images else None}
    meta.update(extra or {})
    with open(os.path.join(outdir, "meta_%s.json" % name), "w") as f:
        json.dump(meta, f, indent=1)
    print("XONG", meta, flush=True)


def infer_paths(model, cid, paths, tm):
    out = []
    for i in range(0, len(paths), 512):
        res = predict_timed(model, paths[i:i + 512], tm)
        out.extend(rows_of(r, cid) for r in res)
        print("  ", min(i + 512, len(paths)), "/", len(paths), "%.0fs" % tm[0], flush=True)
    return out


def stage_infer(tag, outdir=None, limit_frac=None):
    outdir = outdir or os.path.join(OUT_ROOT, "orig_DD" if tag == "ORIG_DD" else tag)
    os.makedirs(outdir, exist_ok=True)
    sha_manifest()
    model, cid, torch = load_model(tag)
    info = {"tag": tag, "weights": W[tag], "weights_sha256": hashlib.sha256(open(W[tag], "rb").read()).hexdigest(),
            "cls": cid, "torch": torch.__version__, "threads": torch.get_num_threads(), "device": "cpu",
            "ultralytics": __import__("ultralytics").__version__, "conf": g.CONF_LO}
    json.dump(info, open(os.path.join(outdir, "infer_info.json"), "w"), indent=1)
    todo = lambda n: not os.path.exists(os.path.join(outdir, "meta_%s.json" % n))

    for kind in ("pos", "bg"):
        n = "val_" + kind
        if todo(n):
            rows, paths = val_rows(tag, kind)
            tm = [0.0]
            ds = infer_paths(model, cid, paths, tm)
            write_raw(outdir, n, [r["path"] for r in rows], ds, len(paths), tm[0])
    if todo("birds"):
        paths = g.set_paths("birds")
        tm = [0.0]
        ds = infer_paths(model, cid, paths, tm)
        write_raw(outdir, "birds", [os.path.basename(p) for p in paths], ds, len(paths), tm[0])

    if tag in ("EE", "ORIG"):
        for kind in ("pos", "bg"):
            n = "test_" + kind
            if todo(n):
                rows, paths = ee_test(kind)
                tm = [0.0]
                ds = infer_paths(model, cid, paths, tm)
                write_raw(outdir, n, [r["path"] for r in rows], ds, len(paths), tm[0])
    else:  # DD: tao vung cat trong bo nho
        if todo("test_pos") or todo("test_bg"):
            from multiprocessing import Pool
            fr = dd_frames()
            keys = {"pos": [], "bg": []}
            dets = {"pos": [], "bg": []}
            buf = {"pos": [], "bg": []}
            meta_rows = {"pos": [], "bg": []}
            tm = [0.0]
            t0 = time.time()
            nbg_none = 0

            def flush(kind):
                if buf[kind]:
                    res = predict_timed(model, buf[kind], tm)
                    dets[kind].extend(rows_of(r, cid) for r in res)
                    buf[kind] = []
            with Pool(WORKERS) as p:
                for i, (rows, arrs) in enumerate(p.imap(dd_job, fr, chunksize=4)):
                    for kind in ("pos", "bg"):
                        if kind in rows:
                            keys[kind].append(rows[kind]["path"])
                            meta_rows[kind].append(rows[kind])
                            buf[kind].append(arrs[kind])
                            if len(buf[kind]) >= 128:
                                flush(kind)
                        else:
                            nbg_none += 1
                    if (i + 1) % 500 == 0:
                        print("DD", i + 1, "/", len(fr), "wall %.0fs infer %.0fs" % (time.time() - t0, tm[0]), flush=True)
            flush("pos")
            flush("bg")
            for kind in ("pos", "bg"):
                write_raw(outdir, "test_" + kind, keys[kind], dets[kind], len(keys[kind]), tm[0] * len(keys[kind]) / max(1, len(keys["pos"]) + len(keys["bg"])),
                          {"wall_incl_cropping_s": round(time.time() - t0, 1), "n_bg_none": nbg_none})
                with open(os.path.join(outdir, "rows_test_%s.json" % kind), "w") as f:
                    json.dump(meta_rows[kind], f)
    open(os.path.join(outdir, "infer.done"), "w").write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    print("INFER XONG", tag, flush=True)


# ---------------------------------------------------------------- cham
def load_raw_dir(outdir, name):
    d = defaultdict(list)
    with open(os.path.join(outdir, "raw_%s.csv" % name), newline="") as f:
        for r in csv.DictReader(f):
            d[r["image"]].append((int(r["cls"]), float(r["conf"]), float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"])))
    return d


def fa_crops(rows, dets, cid):
    return [{"kind": r["background_kind"], "confs": [d[1] for d in dets.get(r["path"], []) if d[0] == cid]} for r in rows]


def frames_of(rows, dets, cid):
    return g.to_frames(rows, dets, cls=cid)


def select_threshold(val_pos_frames, val_bg_crops):
    curve = []
    for t in GRID:
        fa = em.false_alarm_stats(val_bg_crops, t, FPS, 1)["all"]
        rec = g.rb(val_pos_frames, t)
        curve.append({"thr": t, "val_fa_per_100": fa["per_100"], "val_fa_crops": fa["crops_with_fa"],
                      "val_recall": rec["all"]["recall"], **{"val_recall_" + b: rec[b]["recall"] for b in em.BANDS}})
    ok = [c for c in curve if c["val_fa_per_100"] <= 1.0]
    return (ok[0]["thr"] if ok else None), curve


def metrics_at(F, bgc, thr, birds):
    a = {}
    a["A1"] = g.a1_block(F, thr)
    seqs = {s: g.hit_seq(fl, thr) for s, fl in g.by_seg(F).items()}
    a["A2"] = {"pooled": em.loss_summary_multi(list(seqs.values()), FPS),
               "per_segment": {s: em.loss_summary(v, FPS) for s, v in seqs.items()}}
    a["A3"] = {"test_bg": em.false_alarm_stats(bgc, thr, FPS, 1), "birds": em.false_alarm_stats(birds, thr, FPS, 1)}
    a["A4"] = {"fps30": g.a4_block(F, thr, FPS), "fps15": g.a4_block(F, thr, g.FPS_ALT)}
    return a


def test_rows(tag, outdir):
    if tag in ("EE", "ORIG"):
        return {k: ee_test(k)[0] for k in ("pos", "bg")}
    return {k: json.load(open(os.path.join(outdir, "rows_test_%s.json" % k))) for k in ("pos", "bg")}


def stage_score(tag, outdir=None):
    outdir = outdir or os.path.join(OUT_ROOT, "orig_DD" if tag == "ORIG_DD" else tag)
    sha = sha_manifest()
    assert ps.verify_test_manifest(g.MANIFEST)
    info = json.load(open(os.path.join(outdir, "infer_info.json")))
    cid = info["cls"]
    vp_rows, _ = val_rows(tag, "pos")
    vb_rows, _ = val_rows(tag, "bg")
    vp = load_raw_dir(outdir, "val_pos")
    vb = load_raw_dir(outdir, "val_bg")
    thr, curve = select_threshold(frames_of(vp_rows, vp, cid), fa_crops(vb_rows, vb, cid))
    with open(os.path.join(outdir, "val_curve.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(curve[0]))
        w.writeheader()
        w.writerows(curve)
    R = {"tag": tag, "infer_info": info, "manifest_sha256": sha, "threshold": thr, "n_val_pos": len(vp_rows),
         "n_val_bg": len(vb_rows), "threshold_rule": "thap nhat tren luoi 0.005 co BDG val <= 1/100 vung nen (cua luot)",
         "fps_assumed": FPS}
    if thr is None:
        json.dump(R, open(os.path.join(outdir, "results.json"), "w"), indent=1, default=str)
        print("KHONG co nguong dat")
        return
    tr = test_rows(tag, outdir)
    dp, db = load_raw_dir(outdir, "test_pos"), load_raw_dir(outdir, "test_bg")
    assert set(dp) <= {r["path"] for r in tr["pos"]} and set(db) <= {r["path"] for r in tr["bg"]}
    R["n_test_pos"], R["n_test_bg"] = len(tr["pos"]), len(tr["bg"])
    R["n_truncated_test_pos"] = sum(int(r["truncated"]) for r in tr["pos"])
    R["n_test_segments"] = len({r["segment"] for r in tr["pos"]})
    F = frames_of(tr["pos"], dp, cid)
    bgc = fa_crops(tr["bg"], db, cid)
    bd = load_raw_dir(outdir, "birds")
    birds = [{"kind": "bird", "confs": [d[1] for d in bd.get(k, []) if d[0] == cid]} for k in g.set_keys("birds")]
    R["by_threshold"] = {str(t): metrics_at(F, bgc, t, birds) for t in (thr,) + tuple(x for x in EXTRA_THR + ((0.12,) if tag == "ORIG_DD" else ()) if x != thr)}
    R["meta"] = {n: json.load(open(os.path.join(outdir, "meta_%s.json" % n))) for n in ("val_pos", "val_bg", "birds", "test_pos", "test_bg")}
    json.dump(R, open(os.path.join(outdir, "results.json"), "w"), indent=1, default=str)
    write_md(R, outdir)
    print("score xong", tag, "nguong", thr)


def write_md(R, outdir):
    L = ["# Cham %s (CPU, %d luong), nguong chon tren val = %s (val: %d pos, %d bg), test: %d khung pos / %d vung bg, %d doan, 30 khung/giay (gia dinh)\n"
         % (R["tag"], R["infer_info"]["threads"], R["threshold"], R["n_val_pos"], R["n_val_bg"], R["n_test_pos"], R["n_test_bg"], R["n_test_segments"])]
    for t, a in R["by_threshold"].items():
        L.append("\n## nguong %s" % t)
        L.append("| dai | n | recall | lo | hi |\n|---|---|---|---|---|")
        for b in ("16-57", "57-200", ">200", "all"):
            s, v = a["A1"]["spread"][b], a["A1"]["by_band"][b]
            L.append("| %s | %d | %s | %s | %s |" % (b, v["n"], g.pct(s["recall"]), g.pct(s["lo"]), g.pct(s["hi"])))
        for d, v in a["A1"]["by_direction"].items():
            L.append("- %s: " % d + ", ".join("%s=%s (n=%d)" % (b, g.pct(v[b]["recall"]), v[b]["n"]) for b in ("16-57", "57-200", ">200", "all")))
        for s, v in a["A1"]["by_segment"].items():
            L.append("- doan %s: all=%s (n=%d)" % (s, g.pct(v["all"]["recall"]), v["all"]["n"]))
        p = a["A2"]["pooled"]
        L.append("A2: cum>=0.25s %d (%.2f/phut), cum>=3s %d, dai nhat %.2fs, tong %.0fs" % (p["n_short"], p["per_minute"], p["n_long"], p["longest_s"], p["duration_s"]))
        for k in ("test_bg", "birds"):
            for gg, v in a["A3"][k].items():
                L.append("A3 %s %s: %d/%d vung co BDG (%.2f/100)" % (k, gg, v["crops_with_fa"], v["n_crops"], v["per_100"]))
        for fk in ("fps30", "fps15"):
            for m in ("all", "top1"):
                v = a["A4"][fk][m]
                L.append("A4 %s %s: model %.3f, tran %.3f, ti so %.3f" % (fk, m, v["model"], v["ceiling"], v["ratio"]))
    L.append("\nThoi gian suy luan CPU: " + json.dumps({k: v["ms_per_tile"] for k, v in R["meta"].items()}) + " (ms/o)")
    open(os.path.join(outdir, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


# ---------------------------------------------------------------- verify (a)
def stage_verify():
    """Model goc, mau E+E': chay script nay, so voi raw G0 (cung anh, cung ham cham)."""
    outdir = os.path.join(OUT_ROOT, "verify_orig")
    os.makedirs(outdir, exist_ok=True)
    sha_manifest()
    model, cid, torch = load_model("ORIG")
    assert cid == 4
    rows_pos, paths_pos = ee_test("pos")
    by = defaultdict(list)
    for r, p in zip(rows_pos, paths_pos):
        by[r["segment"]].append((r, p))
    sel_pos = [x for s in sorted(by) for x in by[s][:VERIFY_FIRST]]
    rows_bg, paths_bg = ee_test("bg")
    sel_bg = list(zip(rows_bg, paths_bg))[::VERIFY_BG_EVERY]
    res = {"n_pos": len(sel_pos), "n_bg": len(sel_bg), "threads": torch.get_num_threads()}
    mine = {}
    for kind, sel in (("pos", sel_pos), ("bg", sel_bg)):
        tm = [0.0]
        ds = infer_paths(model, cid, [p for _, p in sel], tm)
        mine[kind] = {r["path"]: [(d[0], float(("%.5f" % d[1])), *[float("%.2f" % v) for v in d[2:]]) for d in dd] for (r, _), dd in zip(sel, ds)}
        res["ms_per_tile_" + kind] = round(1000 * tm[0] / len(sel), 2)
    g0 = {"pos": load_raw_dir(G0_OUT, "test_pos"),
          "bg": load_raw_dir(G0_OUT, "test_bg")}
    thr = 0.12
    # (1) so phat hien tho (lop may bay, conf >= 0.01) tung anh
    for kind in ("pos", "bg"):
        nd = n_same = 0
        mx_conf = mx_xy = 0.0
        for k, dm in mine[kind].items():
            a = sorted([d for d in dm if d[0] == 4], key=lambda d: -d[1])
            b = sorted([d for d in g0[kind].get(k, []) if d[0] == 4], key=lambda d: -d[1])
            nd += 1
            if len(a) == len(b):
                n_same += 1
                for x, y in zip(a, b):
                    mx_conf = max(mx_conf, abs(x[1] - y[1]))
                    mx_xy = max(mx_xy, max(abs(p - q) for p, q in zip(x[2:], y[2:])))
        res["raw_" + kind] = {"images": nd, "same_n_airplane_dets": n_same, "max_abs_conf_diff": mx_conf, "max_abs_xy_diff_px": mx_xy}
    # (2) chi so (cung ham cham, cung nguong 0.12)
    prow = [r for r, _ in sel_pos]
    brow = [r for r, _ in sel_bg]
    out = {}
    for nm, dp, db in (("moi_chay_lai", mine["pos"], mine["bg"]), ("G0_raw", {k: g0["pos"].get(k, []) for k in mine["pos"]}, {k: g0["bg"].get(k, []) for k in mine["bg"]})):
        F = frames_of(prow, dp, 4)
        bgc = fa_crops(brow, db, 4)
        a = g.a1_block(F, thr)
        a4 = g.a4_block(F, thr, FPS)
        fa = em.false_alarm_stats(bgc, thr, FPS, 1)["all"]
        out[nm] = {"A1": {b: a["by_band"][b] for b in ("16-57", "57-200", ">200", "all")},
                   "A1_dir_all": {d: {"n": v["all"]["n"], "recall": v["all"]["recall"]} for d, v in a["by_direction"].items()},
                   "A3_fa_crops": fa["crops_with_fa"], "A3_n_crops": fa["n_crops"], "A3_per_100": fa["per_100"],
                   "A4_all": {k: a4["all"][k] for k in ("model", "ceiling", "ratio")}, "A4_top1": {k: a4["top1"][k] for k in ("model", "ceiling", "ratio")}}
    res["metrics_thr0.12"] = out
    # (3) quy tac chon nguong tren raw val cua G0 (phai ra 0.12 nhu g0_results.json)
    vp_rows = g.set_rows("val_pos")
    vb_rows = g.set_rows("val_bg")
    gvp, gvb = load_raw_dir(G0_OUT, "val_pos"), load_raw_dir(G0_OUT, "val_bg")
    t2, _ = select_threshold(frames_of(vp_rows, gvp, 4), fa_crops(vb_rows, gvb, 4))
    res["threshold_rule_on_G0_val"] = t2
    res["g0_results_threshold"] = json.load(open(os.path.join(G0_OUT, "g0_results.json")))["operating_threshold"]
    json.dump(res, open(os.path.join(outdir, "verify.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else ""
    tg = sys.argv[2] if len(sys.argv) > 2 else ""
    if st == "verify":
        stage_verify()
    elif st == "infer":
        assert tg in ("EE", "DD", "ORIG_DD"), tg
        if tg in DONE_FLAG:
            assert os.path.exists(os.path.join(VISION, "results", "b1a", "train", DONE_FLAG[tg])), "chua co %s" % DONE_FLAG[tg]
        stage_infer(tg)
    elif st == "score":
        assert tg in ("EE", "DD", "ORIG_DD"), tg
        stage_score(tg)
    else:
        raise SystemExit("stage: verify | infer <EE|DD> | score <EE|DD>")
