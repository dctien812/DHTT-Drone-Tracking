"""B1a buoc 12 (c): cham yolov8n.pt goc (lop COCO airplane 4) tren tap kiem cua luot DD = D + D' (8552 khung), nguong 0.12 nhu cong G0.
Dung lai ham co san (run_step6.do_frame de tao vung cat, run_g0.to_frames/a1_block/fa_crops/a4_block de cham). Khong sua gi.
stage: crops | infer | repeat | score
- crops: pos/off/bg cho 8552 khung D,D' vao data/b1a/yolo_dd_test (cung seed/ham voi buoc 6)
- infer: suy luan card (device 0, cudnn tat), imgsz 480, conf 0.01 -> results/b1a/g0_dd/raw_dd_<pos|off|bg>.csv
- repeat: suy luan lai 3 lan tren 512 anh dau cua dd_pos, kiem ket qua giong het
- score: A1 theo dai co + theo huong, A3 (vung nen D/D' + chim lay tu raw_birds cua G0), A4 (tran) o 30 va 15 khung/giay, A5 lech tam
Luu y: G0 cu suy luan tren CPU (torch 2.15 cpu, WSL); o day suy luan tren card => co the lech so nho do khac duong tinh toan.
"""
import csv
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import eval_metrics as em  # noqa: E402
import prep_split as ps  # noqa: E402
import run_g0 as g  # noqa: E402
import run_step6 as rs  # noqa: E402

VISION = g.VISION
DATA = g.DATA
DDT = os.path.join(DATA, "yolo_dd_test")
OUT = os.path.join(VISION, "results", "b1a", "g0_dd")
G0_OUT = g.OUT
THR = 0.12
EXPECT_DD = 8552
KINDS = ("pos", "off", "bg")
COLS = rs.COLS


def dd_frames():
    sp = ps.all_folds(ps.discover_segments(rs.ROOT), val_sparse_n=3)["DD"]
    n = sum(len(v) for v in sp["test"].values())
    assert n == EXPECT_DD, n
    assert all(ps.parse_segment_id(s)[0] in ("D", "D'") for s in sp["test"])
    return [(s, f) for s in sorted(sp["test"]) for f in sp["test"][s]]


def stage_crops():
    from multiprocessing import Pool
    fr = dd_frames()
    jobs = [(DDT, "test", s, f, KINDS) for s, f in fr]
    t = time.time()
    rows = []
    with Pool(rs.WORKERS) as p:
        for i, r in enumerate(p.imap(rs.do_frame, jobs, chunksize=8)):
            rows.extend(r)
            if (i + 1) % 1000 == 0:
                print("crops", i + 1, "/", len(jobs), "%.0fs" % (time.time() - t), flush=True)
    os.makedirs(os.path.join(DDT, "index"), exist_ok=True)
    with open(os.path.join(DDT, "index", "dd_test.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print("vung cat:", dict(Counter((r["kind"], "none" if r["path"] == "" else "ok") for r in rows)), "%.0fs" % (time.time() - t))


def sel(kind):
    with open(os.path.join(DDT, "index", "dd_test.csv"), newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["kind"] == kind]
    for r in rows:
        assert r["path"], r
    return sorted(rows, key=lambda r: (r["segment"], ps.parse_frame_name(r["frame"])))


def predict(model, paths, chunk=64):
    out = []
    for i in range(0, len(paths), chunk):
        for r in model.predict(paths[i:i + chunk], imgsz=480, conf=g.CONF_LO, device=0, verbose=False):
            b = r.boxes
            if b is None or len(b) == 0:
                out.append([])
                continue
            xy, cf, cl = b.xyxy.cpu().numpy(), b.conf.cpu().numpy(), b.cls.cpu().numpy()
            out.append([(int(c), float(p), *[float(v) for v in xy_]) for xy_, p, c in zip(xy, cf, cl)])
    return out


def load_model():
    import torch
    torch.backends.cudnn.enabled = False
    from ultralytics import YOLO
    m = YOLO(g.WEIGHTS)
    assert {int(k): v for k, v in m.names.items()}[4] == "airplane"
    return m, torch


def stage_infer():
    model, torch = load_model()
    os.makedirs(OUT, exist_ok=True)
    meta_all = {"torch": torch.__version__, "device": torch.cuda.get_device_name(0), "weights": g.WEIGHTS, "conf": g.CONF_LO}
    for kind in KINDS:
        rows = sel(kind)
        assert len(rows) == EXPECT_DD, (kind, len(rows))
        paths = [os.path.join(DDT, "images", r["path"]) for r in rows]
        t0 = time.time()
        wr = []
        for i in range(0, len(paths), 512):
            res = predict(model, paths[i:i + 512])
            for r, ds in zip(rows[i:i + 512], res):
                wr.extend(g._fmt(r["path"], d) for d in ds)
            print(kind, min(i + 512, len(paths)), "/", len(paths), "%.0fs" % (time.time() - t0), flush=True)
        secs = time.time() - t0
        with open(os.path.join(OUT, "raw_dd_%s.csv" % kind), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["image", "cls", "conf", "x1", "y1", "x2", "y2"])
            w.writerows(wr)
        meta_all[kind] = {"n_images": len(paths), "n_det_rows": len(wr), "seconds": round(secs, 1), "imgs_per_s": round(len(paths) / secs, 2)}
        print("XONG", kind, meta_all[kind], flush=True)
    json.dump(meta_all, open(os.path.join(OUT, "infer_meta.json"), "w"), indent=1)


def stage_repeat():
    model, _ = load_model()
    rows = sel("pos")[:512]
    paths = [os.path.join(DDT, "images", r["path"]) for r in rows]
    runs = []
    for k in range(3):
        t0 = time.time()
        runs.append(predict(model, paths))
        print("lan", k + 1, "%.1fs" % (time.time() - t0))
    same12 = runs[0] == runs[1]
    same13 = runs[0] == runs[2]
    mx = 0.0
    for a, b in zip(runs[0], runs[2]):
        if len(a) == len(b):
            for x, y in zip(a, b):
                mx = max(mx, max(abs(p - q) for p, q in zip(x[1:], y[1:])))
    print("giong het lan1==lan2:", same12, "lan1==lan3:", same13, "so phat hien:", [sum(map(len, r)) for r in runs], "lech toi da:", mx)
    os.makedirs(OUT, exist_ok=True)
    json.dump({"identical_1_2": same12, "identical_1_3": same13, "n_dets": [sum(map(len, r)) for r in runs], "max_abs_diff": mx},
              open(os.path.join(OUT, "repeat_check.json"), "w"), indent=1)


def raw(name, directory):
    old = g.OUT
    g.OUT = directory
    try:
        return g.load_raw(name)
    finally:
        g.OUT = old


def stage_score():
    import hashlib
    sha = hashlib.sha256(open(g.MANIFEST, "rb").read()).hexdigest()
    assert sha == g.MANIFEST_SHA
    rows = {k: sel(k) for k in KINDS}
    dets = {k: raw("dd_" + k, OUT) for k in KINDS}
    for k in KINDS:
        assert set(dets[k]) <= {r["path"] for r in rows[k]}
    F = {k: g.to_frames(rows[k], dets[k]) for k in ("pos", "off")}
    R = {"thr": THR, "n_frames": len(rows["pos"]), "manifest_sha256_unchanged": True, "fps_assumed": g.FPS,
         "set": "D + D' (8552 khung, kiem cua luot DD)"}
    a = {}
    a["A1"] = g.a1_block(F["pos"], THR)
    bg = g.fa_crops(rows["bg"], dets["bg"], lambda r: r["background_kind"])
    birds = raw("birds", G0_OUT)
    bird_crops = [{"kind": "bird", "confs": [d[1] for d in birds.get(k, []) if d[0] == g.AIR]} for k in g.set_keys("birds")]
    a["A3"] = {"dd_bg": em.false_alarm_stats(bg, THR, g.FPS, 1), "birds_from_G0_cpu_run": em.false_alarm_stats(bird_crops, THR, g.FPS, 1)}
    a["A4"] = {"fps30": g.a4_block(F["pos"], THR, g.FPS), "fps15": g.a4_block(F["pos"], THR, g.FPS_ALT)}
    a["A5_off"] = {"by_band": g.compact_rb(g.rb(F["off"], THR))}
    grp = lambda s: [f for f in F["pos"] if f["seg"].split("/")[0] == s]
    a["by_set"] = {s: g.compact_rb(g.rb(grp(s), THR)) for s in ("D", "D'")}
    R["metrics"] = a
    json.dump(R, open(os.path.join(OUT, "g0_dd_results.json"), "w"), indent=1, default=str)
    L = ["# G0 (yolov8n.pt goc) tren D + D' (tap kiem luot DD), nguong %.2f, %d khung, 30 khung/giay (gia dinh)\n" % (THR, R["n_frames"]),
         "## A1 (IoU 0.5; spread = bootstrap theo doan)", "| dai | n | recall | lo | hi |", "|---|---|---|---|---|"]
    for b in ("16-57", "57-200", ">200", "all"):
        s, v = a["A1"]["spread"][b], a["A1"]["by_band"][b]
        L.append("| %s | %d | %s | %s | %s |" % (b, v["n"], g.pct(s["recall"]), g.pct(s["lo"]), g.pct(s["hi"])))
    L.append("\n## A1 theo huong")
    for d, v in a["A1"]["by_direction"].items():
        L.append("- %s: " % d + ", ".join("%s=%s (n=%d)" % (b, g.pct(v[b]["recall"]), v[b]["n"]) for b in ("16-57", "57-200", ">200", "all")))
    L.append("\n## A1 theo doan")
    for d, v in a["A1"]["by_segment"].items():
        L.append("- %s: " % d + ", ".join("%s=%s (n=%d)" % (b, g.pct(v[b]["recall"]), v[b]["n"]) for b in ("16-57", "57-200", ">200", "all")))
    L.append("\n## A3 (bao dong gia theo vung)")
    for k, grpd in a["A3"].items():
        for gg, v in grpd.items():
            L.append("- %s %s: %d/%d vung (%.2f/100), %d phat hien" % (k, gg, v["crops_with_fa"], v["n_crops"], v["per_100"], v["n_dets"]))
    L.append("\n## A4")
    for fk in ("fps30", "fps15"):
        for m in ("all", "top1"):
            v = a["A4"][fk][m]
            L.append("- %s %s: model %.3f, tran %.3f, ti so %.3f" % (fk, m, v["model"], v["ceiling"], v["ratio"]))
    L.append("\n## A5 lech tam: " + ", ".join("%s=%s (n=%d)" % (b, g.pct(a["A5_off"]["by_band"][b]["recall"]), a["A5_off"]["by_band"][b]["n"]) for b in ("16-57", "57-200", ">200", "all")))
    open(os.path.join(OUT, "g0_dd_report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else ""
    if st == "crops":
        stage_crops()
    elif st == "infer":
        stage_infer()
    elif st == "repeat":
        stage_repeat()
    elif st == "score":
        stage_score()
    else:
        raise SystemExit("stage: crops | infer | repeat | score")
