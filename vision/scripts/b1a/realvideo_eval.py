"""Cham yolov8n.pt goc tren nhan video that (B1a A6). Dung eval_metrics va prep_crops co san (khong sua).
 (i)  vung cat 480 chua tron khung bao, vi tri ngau nhien co seed (prep_crops.positive_crop, frame 1080x1920): lac quan.
 (ii) quet toan khung bang o lat 480 chong lan 200 (realvideo_common.tiles) roi gop (prep_crops.merge_detections, IoU 0,5).
Chi lop 'airplane' (id 4) tinh la phat hien dung. Mau so: nhan 'chac'. IoU >= 0,5.
Dau ra (RES): recall.csv, loss.csv, fa.csv, confusion.csv, fa_top20.csv + anh ghep FA trong IMG/fa.
Dung: realvideo_eval.py"""
import csv
import json
import os
import sys
import numpy as np
import cv2
from ultralytics import YOLO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *
import eval_metrics as em
import prep_crops as pc

THRS = [0.25, 0.12, 0.10]
SEED = 7001
NAMES = {int(k): v for k, v in json.load(open(ROOT + "/vision/results/b1a/g0/classes.json"))["names"].items()}


def load_labels():
    return [r for r in csv.DictReader(open(IMG + "/labels.csv"))]


def box_of(r):
    return tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))


def load_raw(paths):
    d = {}
    for p in paths:
        have = set(d)           # khung da co tu tep truoc thi bo qua (tranh trung)
        for r in csv.DictReader(open(p)):
            if int(r["frame"]) in have:
                continue
            d.setdefault(int(r["frame"]), []).append((int(r["cls"]), float(r["conf"]), float(r["x1"]), float(r["y1"]),
                                                       float(r["x2"]), float(r["y2"])))
    return d


def scan_dets(raw, f, thr):
    """(ii) gop cac o lat: chi lop airplane, conf >= thr; tra ve [(x1,y1,x2,y2,conf)]."""
    ds = [(d[2], d[3], d[4], d[5], d[1]) for d in raw.get(f, []) if d[0] == 4 and d[1] >= thr]
    return pc.merge_detections(ds, 0.5)


def crop_results(model, rows):
    """(i) tra ve {(frame,obj): [(cls,conf,x1,y1,x2,y2) toa do khung]} tu vung cat 480."""
    items = []
    for r in rows:
        b = box_of(r)
        c = pc.positive_crop(b, pc.frame_seed(SEED, r["obj"], r["frame"]), frame_w=1080, frame_h=1920)
        items.append(((int(r["frame"]), r["obj"]), c))
    frames = sorted({k[0] for k, _ in items})
    imgs = {}
    out = {}
    for f, img in iter_frames(frames):
        todo = [(k, c) for k, c in items if k[0] == f]
        arrs = [np.ascontiguousarray(img[c["y0"]:c["y0"] + 480, c["x0"]:c["x0"] + 480]) for _, c in todo]
        res = model.predict(arrs, imgsz=480, conf=0.01, device="cpu", verbose=False)
        for (k, c), rr in zip(todo, res):
            out[k] = [(int(cl), float(cf), b[0] + c["x0"], b[1] + c["y0"], b[2] + c["x0"], b[3] + c["y0"])
                      for b, cf, cl in zip(rr.boxes.xyxy.numpy(), rr.boxes.conf.numpy(), rr.boxes.cls.numpy())]
    return out


def main():
    labs = load_labels()
    chac = [r for r in labs if r["flag"] == "chac"]
    pairs = {}
    for r in chac:
        pairs.setdefault((int(r["frame"]), r["obj"]), r)      # cung (khung, vat) co o sparse va cont: tinh mot lan
    rows = list(pairs.values())
    raw = load_raw([RES + "/raw_pass1.csv", RES + "/raw_cont.csv"])
    model = YOLO(ROOT + "/vision/weights/yolov8n.pt")
    crop = crop_results(model, rows)
    os.makedirs(RES, exist_ok=True)

    def frames_for(method, thr, sel):
        out = []
        for r in sel:
            k = (int(r["frame"]), r["obj"])
            if method == "crop":
                ds = [(d[2], d[3], d[4], d[5], d[1]) for d in crop[k] if d[0] == 4 and d[1] >= thr]
            else:
                ds = scan_dets(raw, k[0], thr)
            out.append({"gt": box_of(r), "dets": ds, "seg": r["seg"], "obj": r["obj"], "frame": k[0], "set": r["set"]})
        return out

    # ---- recall ----
    rec = []
    for method in ("crop", "scan"):
        for thr in THRS:
            for setn in ("sparse", "cont"):
                sel = [r for r in chac if r["set"] == setn]
                fr = frames_for(method, thr, sel)
                for gname, key in (("tat_ca", None), ("doan", "seg"), ("vat", "obj")):
                    groups = {"tat_ca": fr} if key is None else {}
                    if key:
                        for f in fr:
                            groups.setdefault(f[key], []).append(f)
                    for g, gf in sorted(groups.items()):
                        rb = em.recall_by_band(gf, 0.5, 0.0)       # dets da loc theo thr
                        for band in em.BANDS + ("all",):
                            v = rb[band]
                            rec.append([method, thr, setn, gname, g, band, v["n"], v["hit"],
                                        "" if v["recall"] is None else "%.4f" % v["recall"]])
    with open(RES + "/recall.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cach", "nguong", "tap", "nhom", "gia_tri", "dai_rong_px_video", "n", "trung", "recall"])
        w.writerows(rec)

    # ---- cum mat tren doan lien tuc (moi khung) ----
    cont = {"M1": [r for r in labs if r["set"] == "cont" and r["obj"] == "M1"],
            "M2": [r for r in labs if r["set"] == "cont" and r["obj"] == "M2" and r["flag"] == "chac"]}
    loss = []
    for method in ("crop", "scan"):
        for thr in THRS:
            seqs = {}
            for obj, rr in cont.items():
                rr = sorted(rr, key=lambda r: int(r["frame"]))
                fr = frames_for(method, thr, rr)
                seqs[obj] = [em._hit(f, 0.5, 0.0) for f in fr]
            for obj, s in seqs.items():
                ls = em.loss_summary(s, 30.0)
                loss.append([method, thr, obj, len(s), sum(s), "%.4f" % (sum(s) / len(s)), ls["n_short"], ls["n_long"],
                             "%.2f" % ls["longest_s"], "%.2f" % ls["per_minute"]])
    with open(RES + "/loss.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cach", "nguong", "vat", "so_khung", "so_khung_trung", "ti_le", "cum_mat_>=0.25s", "cum_mat_>=3s",
                    "cum_dai_nhat_s", "cum_>=0.25s_moi_phut"])
        w.writerows(loss)

    # ---- nham lop khi truot airplane (nguong 0,10) ----
    conf = []
    thr = 0.10
    for method in ("crop", "scan"):
        for r in rows:
            k = (int(r["frame"]), r["obj"])
            gt = box_of(r)
            if method == "crop":
                air = [(d[2], d[3], d[4], d[5], d[1]) for d in crop[k] if d[0] == 4 and d[1] >= thr]
                allds = [d for d in crop[k] if d[1] >= thr]
            else:
                air = scan_dets(raw, k[0], thr)
                allds = [d for d in raw.get(k[0], []) if d[1] >= thr]
            if any(em.iou(d[:4], gt) >= 0.5 for d in air):
                continue
            c = [(em.iou(d[2:6], gt), d) for d in allds if d[0] != 0 and em.iou(d[2:6], gt) >= 0.3]
            if c:
                best = max(c, key=lambda t: t[1][1])[1]
                lab = NAMES.get(best[0], str(best[0]))
            else:
                lab = "khong_phat_hien_nao"
            conf.append([method, r["set"], r["seg"], r["frame"], r["obj"], lab])
    from collections import Counter
    cnt = Counter((m, lab) for m, _, _, _, _, lab in conf)
    with open(RES + "/confusion.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cach", "lop_model_gan_cho_may_bay_khi_truot_airplane_o_0.10", "so_nhan"])
        for (m, lab), n in sorted(cnt.items()):
            w.writerow([m, lab, n])
        w.writerow([])
        w.writerow(["cach", "tap", "doan", "khung", "vat", "lop"])
        w.writerows(conf)

    # ---- bao dong gia (cach ii): khung day du nhan (khong khung khong chac/loai), tu 1260 tro di ----
    byf = {}
    for r in labs:
        byf.setdefault((int(r["frame"]), r["set"]), []).append(r)
    fa_frames = []      # (khung, tap, nhan, quan the): 'sau1260' = khung to sau khi cat lang; 'dat_xa' = khung dau (con may bay thu hai nho/chua gan nhan)
    for (f, st), rs in byf.items():
        if all(r["flag"] in ("chac", "am") for r in rs):
            fa_frames.append((f, st, rs, "sau1260" if f >= 1260 else "dat_xa"))
        # khung 0-1259 co 'loai' hoac 'khong_chac' bi bo
    fa_rows = []
    top = []
    for thr in THRS + [0.03]:
        for pop in ("sau1260", "dat_xa"):
            for setn in ("sparse", "cont"):
                fs = [x for x in fa_frames if x[1] == setn and x[3] == pop]
                if not fs:
                    continue
                n_fa = n_mis = 0
                for f, st, rs, _ in fs:
                    gts = [box_of(r) for r in rs if r["x1"] != ""]
                    for d in scan_dets(raw, f, thr):
                        m = max([em.iou(d[:4], g) for g in gts] or [0.0])
                        if m >= 0.5:
                            continue
                        if m >= 0.1:
                            n_mis += 1
                        else:
                            n_fa += 1
                            if thr == 0.03:
                                top.append((d[4], f, pop, d[:4]))
                fa_rows.append([thr, pop, setn, len(fs), n_fa, "%.4f" % (n_fa / len(fs)), n_mis])
    with open(RES + "/fa.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["nguong", "quan_the", "tap", "so_khung", "bao_dong_gia_airplane", "bdg_moi_khung", "lech_vi_tri_IoU0.1-0.5"])
        w.writerows(fa_rows)
    # 20 bao dong gia cao nhat (conf, san 0,03), moi khung mot cai
    top.sort(key=lambda t: (-t[0], t[1]))
    seen, sel = set(), []
    for t in top:
        if t[1] in seen:
            continue
        seen.add(t[1])
        sel.append(t)
        if len(sel) == 20:
            break
    with open(RES + "/fa_top20.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["thu_tu", "conf", "khung", "quan_the", "x1", "y1", "x2", "y2"])
        for i, (c, f, pop, b) in enumerate(sel):
            w.writerow([i + 1, "%.3f" % c, f, pop] + ["%.0f" % v for v in b])
    imgs = dict(iter_frames(sorted({t[1] for t in sel})))
    os.makedirs(IMG + "/fa", exist_ok=True)
    vs = []
    for i, (c, f, st, b) in enumerate(sel):
        w_ = max(b[2] - b[0], b[3] - b[1])
        win = int(max(160, min(480, 4 * w_)))
        vs.append(crop_view(imgs[f], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, win, 360.0 / win, [tuple(b) + ((0, 0, 255),)],
                            "#%d f%d c%.2f w%d" % (i + 1, f, c, round(b[2] - b[0]))))
    for k in range(0, len(vs), 12):
        cv2.imwrite("%s/fa/fa_top20_%d.jpg" % (IMG, k // 12), montage(vs[k:k + 12], 4, (360, 360)), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print("xong; nhan chac:", len(chac), "cap (khung,vat):", len(rows), "khung FA:", len(fa_frames))


if __name__ == "__main__":
    main()
