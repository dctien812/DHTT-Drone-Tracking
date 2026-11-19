"""B1a buoc 6: chia tap, ghi danh sach, dong bang tap kiem thu, tao vung cat YOLO, thong ke, tat dinh.

Chi goi ham da co (prep_split, prep_crops, eval_metrics); phan them o day chi la dieu phoi, ghi file, thong ke.
Chay (WSL):  cd /mnt/d/Personal/Drone-Tracking/vision && ~/venv-vision/bin/python scripts/b1a/run_step6.py <stage>
stage: split | crops | birds | stats | determinism | all(= split crops birds stats)

Cach lam (ghi lai de tai hien):
- Anh goc 3840x2160 -> resize_to_width 2304 (1296 cao); khung nhan x0.6 (scale_box).
- Hoc/val: 1 vung cat duong (positive_crop, seed=frame_seed(6001,...)) + 1 vung nen (background_crop, seed 6003), nhan rong.
- Kiem thu: pos + off (offcenter_crop, seed 6002) + bg. Vung 480x480 PNG (compress_level=1), nhan YOLO 1 lop.
- Ten file: <bo>_<huong>_<khung>_<loai>.png, dau nhay trong ten bo doi thanh 'p' (D' -> Dp).
- Anh chim coco-neg\\bird (858): 150 anh giu rieng cho bao dong gia (random.Random(20260).sample tren danh sach da sap),
  708 con lai vao tap hoc lam anh am: cat vuong giua theo canh ngan roi resize 480x480 (INTER_AREA), nhan rong.
- 32 o lat khung (tile_frame) cho moi khung KHONG luu san: luc cham, goi tile_frame() tren anh 2304 va cat tai cho.
"""
import csv
import hashlib
import os
import random
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import prep_crops as pc  # noqa: E402
import prep_split as ps  # noqa: E402
from eval_metrics import background_kind, size_band  # noqa: E402

cv2.setNumThreads(1)
VISION = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.join(VISION, "data", "mmfw-uav", "extracted")
BIRD_DIR = os.path.join(VISION, "data", "coco-neg", "bird")
DATA = os.path.join(VISION, "data", "b1a")
RES = os.path.join(VISION, "results", "b1a", "step6")
SPLIT_DIR = os.path.join(DATA, "split")
YOLO = os.path.join(DATA, "yolo")
INDEX = os.path.join(DATA, "index")
BIRD_FA = os.path.join(DATA, "birds_fa")
SEED_POS, SEED_OFF, SEED_BG = 6001, 6002, 6003
BIRD_SEED = 20260
N_BIRD_FA = 150
EXPECT = {"train": 1153, "val": 1279, "test": 10103}
COLS = ["path", "split", "kind", "segment", "frame", "x0", "y0", "fx1", "fy1", "fx2", "fy2",
        "box_w", "band", "background_kind", "truncated", "seed"]
WORKERS = int(os.environ.get("WORKERS", "12"))


def tag(seg):
    s, d = ps.parse_segment_id(seg)
    return "%s_%s" % (s.replace("'", "p"), d)


def src_paths(seg, frame):
    s, d = ps.parse_segment_id(seg)
    base = os.path.join(ROOT, ps._PREFIX + s, d)
    return os.path.join(base, "Wide_Imgs", frame + ".jpg"), os.path.join(base, "Wide_Anns", frame + ".xml")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def get_split():
    return ps.split_segments(ps.discover_segments(ROOT))


def stage_split():
    sp = get_split()
    os.makedirs(SPLIT_DIR, exist_ok=True)
    counts = {k: sum(len(v) for v in sp[k].values()) for k in sp}
    print("so khung:", counts)
    assert counts == EXPECT, counts
    test_segs, trainval_segs = set(sp["test"]), set(sp["train"]) | set(sp["val"])
    print("doan o ca kiem thu va hoc/val:", len(test_segs & trainval_segs))
    assert not (test_segs & trainval_segs), "doan kiem thu nam trong hoc/val"
    print("so doan: train %d val %d test %d" % (len(sp["train"]), len(sp["val"]), len(sp["test"])))
    for k in ("train", "val", "test"):
        with open(os.path.join(SPLIT_DIR, k + ".txt"), "w", newline="\n") as f:
            for seg in sorted(sp[k]):
                for fr in sp[k][seg]:
                    f.write("%s\t%s\t%s\n" % (src_paths(seg, fr)[0], seg, fr))
    man = os.path.join(SPLIT_DIR, "test_manifest.tsv")
    digest = ps.write_test_manifest(sp, man)
    ok = ps.verify_test_manifest(man)
    print("test_manifest sha256:", digest, "verify:", ok)
    assert ok
    # train/val trung khung?
    tv = {(s, f) for s in sp["train"] for f in sp["train"][s]} & {(s, f) for s in sp["val"] for f in sp["val"][s]}
    print("khung trung giua train va val:", len(tv))
    return sp


def read_list(k):
    out = []
    with open(os.path.join(SPLIT_DIR, k + ".txt")) as f:
        for line in f:
            _, seg, fr = line.rstrip("\n").split("\t")
            out.append((seg, fr))
    return out


def _save(arr, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr).save(path, format="PNG", compress_level=1)


def _label(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write(text)


def do_frame(job):
    out_root, split, seg, frame, kinds = job
    ip, xp = src_paths(seg, frame)
    ann = pc.parse_voc(xp)
    fbox = pc.scale_box(ann["box"], pc.FRAME_W / ann["size"][0])
    img = pc.resize_to_width(np.asarray(Image.open(ip).convert("RGB")))
    d = ps.parse_segment_id(seg)[1]
    w = fbox[2] - fbox[0]
    rows = []
    for kind in kinds:
        seed = frame_seed_for(kind, seg, frame)
        name = "%s_%s_%s" % (tag(seg), frame, kind)
        rel = "%s/%s.png" % (split, name)
        base = dict(split=split, kind=kind, segment=seg, frame=frame, fx1=fbox[0], fy1=fbox[1],
                    fx2=fbox[2], fy2=fbox[3], box_w=w, band=size_band(w) or "<16",
                    background_kind=background_kind(d), seed=seed)
        if kind in ("pos", "off"):
            c = (pc.positive_crop if kind == "pos" else pc.offcenter_crop)(fbox, seed)
            _save(pc.extract_crop(img, c["x0"], c["y0"]), os.path.join(out_root, "images", rel))
            _label(os.path.join(out_root, "labels", split, name + ".txt"), pc.to_yolo_label(c["box"]) + "\n")
            rows.append(dict(base, path=rel, x0=c["x0"], y0=c["y0"], truncated=int(c["truncated"])))
        else:
            c = pc.background_crop([fbox], seed)
            if c is None:
                rows.append(dict(base, path="", x0="", y0="", truncated=0))
            else:
                _save(pc.extract_crop(img, c["x0"], c["y0"]), os.path.join(out_root, "images", rel))
                _label(os.path.join(out_root, "labels", split, name + ".txt"), "")
                rows.append(dict(base, path=rel, x0=c["x0"], y0=c["y0"], truncated=0))
    return rows


def frame_seed_for(kind, seg, frame):
    return pc.frame_seed({"pos": SEED_POS, "off": SEED_OFF, "bg": SEED_BG}[kind], seg, frame)


KINDS = {"train": ("pos", "bg"), "val": ("pos", "bg"), "test": ("pos", "off", "bg")}


def stage_crops(out_root=YOLO, limit=None, splits=("train", "val", "test")):
    os.makedirs(INDEX, exist_ok=True)
    all_rows = {}
    for k in splits:
        fr = read_list(k)
        if limit:
            fr = fr[:limit]
        jobs = [(out_root, k, s, f, KINDS[k]) for s, f in fr]
        t = time.time()
        rows = []
        with Pool(WORKERS) as p:
            for i, r in enumerate(p.imap(do_frame, jobs, chunksize=8)):
                rows.extend(r)
                if (i + 1) % 1000 == 0:
                    print(k, i + 1, "/", len(jobs), "%.0fs" % (time.time() - t), flush=True)
        print(k, "xong", len(jobs), "khung,", "%.0fs" % (time.time() - t), flush=True)
        all_rows[k] = rows
        if out_root == YOLO:
            with open(os.path.join(INDEX, k + ".csv"), "w", newline="") as f:
                w = csv.DictWriter(f, COLS)
                w.writeheader()
                w.writerows(rows)
    return all_rows


def square_480(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    s = min(w, h)
    l, t = (w - s) // 2, (h - s) // 2
    a = np.asarray(im)[t:t + s, l:l + s]
    return cv2.resize(a, (480, 480), interpolation=cv2.INTER_AREA)


def stage_birds():
    names = sorted(f for f in os.listdir(BIRD_DIR) if f.lower().endswith(".jpg"))
    fa = sorted(random.Random(BIRD_SEED).sample(names, N_BIRD_FA))
    tr = [n for n in names if n not in set(fa)]
    print("chim:", len(names), "bao dong gia:", len(fa), "hoc:", len(tr))
    for lst, d, split in ((tr, YOLO, "train"), (fa, BIRD_FA, None)):
        for n in lst:
            stem = "bird_" + n[:-4]
            a = square_480(os.path.join(BIRD_DIR, n))
            if split:
                _save(a, os.path.join(d, "images", split, stem + ".png"))
                _label(os.path.join(d, "labels", split, stem + ".txt"), "")
            else:
                _save(a, os.path.join(d, stem + ".png"))
    for nm, lst in (("bird_fa150.txt", fa), ("bird_train.txt", tr)):
        with open(os.path.join(SPLIT_DIR, nm), "w", newline="\n") as f:
            f.writelines(os.path.join(BIRD_DIR, n) + "\n" for n in lst)


def write_yaml():
    with open(os.path.join(YOLO, "b1a.yaml"), "w", newline="\n") as f:
        f.write("path: %s\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: airplane\n"
                % YOLO.replace("\\", "/"))


def stage_stats():
    write_yaml()
    L = []
    rows = {}
    for k in ("train", "val", "test"):
        with open(os.path.join(INDEX, k + ".csv")) as f:
            rows[k] = list(csv.DictReader(f))
    L.append("# Thong ke buoc 6\n")
    L.append("## So vung cat theo tap va loai (bg None = khong tao duoc)")
    for k in rows:
        c = Counter((r["kind"], "none" if r["path"] == "" else "ok") for r in rows[k])
        L.append("- %s: %s" % (k, dict(c)))
    nb = len([f for f in os.listdir(os.path.join(YOLO, "images", "train")) if f.startswith("bird_")])
    L.append("- train chim (am): %d; birds_fa: %d" % (nb, len(os.listdir(BIRD_FA))))
    L.append("\n## Phan bo dai co (theo be rong khung o thang 2304), moi KHUNG dem 1 lan (loai pos)")
    for k in rows:
        P = [r for r in rows[k] if r["kind"] == "pos"]
        c = Counter(r["band"] for r in P)
        L.append("- %s (n=%d): %s" % (k, len(P), {b: "%d (%.1f%%)" % (c[b], 100 * c[b] / len(P)) for b in ("<16", "16-57", "57-200", ">200")}))
        for d in ("Top_Down", "Horizontal", "Bottom_Up"):
            Q = [r for r in P if r["segment"].endswith("/" + d)]
            cq = Counter(r["band"] for r in Q)
            ws = np.array([float(r["box_w"]) for r in Q])
            L.append("    - %s n=%d: %s; be rong trung vi %.1f, p5-p95 %.1f-%.1f" % (
                d, len(Q), dict(cq), np.median(ws), *np.percentile(ws, [5, 95])))
    L.append("\n## Truncated (vung cat duong/lech tam)")
    for k in rows:
        for kind in ("pos", "off"):
            R = [r for r in rows[k] if r["kind"] == kind]
            if R:
                t = sum(int(r["truncated"]) for r in R)
                L.append("- %s %s: %d/%d = %.3f%%" % (k, kind, t, len(R), 100 * t / len(R)))
    L.append("\n## Huong theo tap (so khung)")
    for k in rows:
        P = [r for r in rows[k] if r["kind"] == "pos"]
        L.append("- %s: %s" % (k, dict(Counter(r["segment"].split("/")[1] for r in P))))
    L.append("\n## Kiem nhat quan crop_to_frame: khung nhan o crop + (x0,y0) = khung nhan o 2304 khi khong truncated")
    bad = 0
    n = 0
    lab_bad = 0
    for k in rows:
        for r in rows[k]:
            if r["kind"] in ("pos", "off") and r["path"]:
                n += 1
                name = os.path.splitext(os.path.basename(r["path"]))[0]
                with open(os.path.join(YOLO, "labels", k, name + ".txt")) as f:
                    v = f.read().split()
                ok = len(v) == 5 and v[0] == "0" and all(0 <= float(x) <= 1 for x in v[1:])
                lab_bad += (not ok)
                if int(r["truncated"]) == 0 and ok:
                    cx, cy, bw, bh = (float(x) * 480 for x in v[1:])
                    got = pc.crop_to_frame((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), int(r["x0"]), int(r["y0"]))
                    want = tuple(float(r[c]) for c in ("fx1", "fy1", "fx2", "fy2"))
                    if max(abs(a - b) for a, b in zip(got, want)) > 0.01:
                        bad += 1
    L.append("- nhan duong da kiem: %d; nhan khong hop le (5 so, [0,1]): %d; khong khop crop_to_frame (>0.01 px): %d" % (n, lab_bad, bad))
    L.append("\n## So anh = so nhan, nhan nen rong")
    for k in rows:
        imgs = sorted(os.listdir(os.path.join(YOLO, "images", k)))
        labs = sorted(os.listdir(os.path.join(YOLO, "labels", k)))
        same = [os.path.splitext(a)[0] for a in imgs] == [os.path.splitext(a)[0] for a in labs]
        L.append("- %s: anh %d, nhan %d, ten khop %s" % (k, len(imgs), len(labs), same))
    tot = 0
    for dp, _, fs in os.walk(DATA):
        tot += sum(os.path.getsize(os.path.join(dp, x)) for x in fs)
    L.append("\n## Dung luong %s: %.2f GB" % (DATA, tot / 1e9))
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, "stats.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


def stage_determinism():
    """Chay lai chia tap va 200 hang dau moi tap (vao thu muc tam), so sha256 voi lan dau."""
    ok = True
    sp = get_split()
    tmp_man = os.path.join(DATA, "_rerun", "test_manifest.tsv")
    os.makedirs(os.path.dirname(tmp_man), exist_ok=True)
    d2 = ps.write_test_manifest(sp, tmp_man)
    d1 = sha_file(os.path.join(SPLIT_DIR, "test_manifest.tsv"))
    print("manifest lan 2 == lan 1:", d1 == d2, d1, d2)
    ok &= d1 == d2
    for k in ("train", "val", "test"):
        h = hashlib.sha256()
        for seg in sorted(sp[k]):
            for fr in sp[k][seg]:
                h.update(("%s\t%s\t%s\n" % (src_paths(seg, fr)[0], seg, fr)).encode())
        same = h.hexdigest() == sha_file(os.path.join(SPLIT_DIR, k + ".txt"))
        print("danh sach", k, "trung:", same)
        ok &= same
    rr = os.path.join(DATA, "_rerun")
    for k in ("train", "val", "test"):
        with open(os.path.join(INDEX, k + ".csv")) as f:
            first = list(csv.DictReader(f))[:200]
        seen, jobs = set(), []
        for r in first:
            if (r["segment"], r["frame"]) not in seen:
                seen.add((r["segment"], r["frame"]))
                jobs.append((rr, k, r["segment"], r["frame"], KINDS[k]))
        with Pool(WORKERS) as p:
            res = p.map(do_frame, jobs)
        new = {x["path"]: x for rs in res for x in rs if x["path"]}
        n_ok = n = 0
        for r in first:
            if not r["path"]:
                continue
            n += 1
            a = sha_file(os.path.join(YOLO, "images", r["path"]))
            b = sha_file(os.path.join(rr, "images", r["path"]))
            lname = os.path.splitext(os.path.basename(r["path"]))[0] + ".txt"
            la = sha_file(os.path.join(YOLO, "labels", k, lname))
            lb = sha_file(os.path.join(rr, "labels", k, lname))
            n_ok += (a == b and la == lb and str(new[r["path"]]["x0"]) == r["x0"])
        print("vung cat %s: %d/%d trung sha256 (anh + nhan)" % (k, n_ok, n))
        ok &= n_ok == n
    print("TAT DINH:", "DAT" if ok else "KHONG DAT")


def stage_selfcheck():
    """make_positive_sample (ham co san) cho cung ket qua voi duong dieu phoi o tren tren 20 khung."""
    sp = read_list("train")[:20]
    bad = 0
    for seg, fr in sp:
        ip, xp = src_paths(seg, fr)
        s = pc.make_positive_sample(ip, xp, frame_seed_for("pos", seg, fr))
        name = "%s_%s_pos" % (tag(seg), fr)
        a = np.asarray(Image.open(os.path.join(YOLO, "images", "train", name + ".png")))
        with open(os.path.join(YOLO, "labels", "train", name + ".txt")) as f:
            lab = f.read().strip()
        bad += not (np.array_equal(a, s["image"]) and lab == s["label"])
    print("make_positive_sample khop dieu phoi: %d/20 khac" % bad)


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    t0 = time.time()
    if st in ("split", "all"):
        stage_split()
    if st in ("crops", "all"):
        stage_crops()
    if st in ("birds", "all"):
        stage_birds()
    if st in ("stats", "all"):
        stage_stats()
    if st == "selfcheck":
        stage_selfcheck()
    if st == "determinism":
        stage_determinism()
    print("tong thoi gian: %.0fs" % (time.time() - t0))
