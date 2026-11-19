"""So model final voi model goc tren dung cac nhan/khung cua realvideo_eval (IoU 0,5; nhan 'chac'; 2 cach: scan = quet o lat, crop = cat quanh nhan).
Cau hinh: base (yolov8n goc, lop 4, khung nguyen), fin1 (final, lop 0, khung nguyen), fin2 (final, lop 0, khung phong 2304/1080 = thang huan luyen).
Ghi RES/final/summary_<cfg>.csv, top20_<cfg>.csv (+ anh ghep IMG/fa_final). Khong ghi de ket qua model goc.
Dung: realvideo_final_eval.py"""
import csv
import os
import sys
from collections import defaultdict
import numpy as np
import cv2
from ultralytics import YOLO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *
import eval_metrics as em
import prep_crops as pc
import realvideo_eval as ev

OUT = RES + "/final"
THRS = [0.25, 0.12, 0.10, 0.085]
FW = ROOT + "/vision/results/b1a/train/runs/b1a_final_s0/weights/best.pt"
CFG = {"base": dict(weights=ROOT + "/vision/weights/yolov8n.pt", cls=4, s=1.0,
                    raw=[RES + "/raw_pass1.csv", RES + "/raw_cont.csv"]),
       "fin1": dict(weights=FW, cls=0, s=1.0, raw=[OUT + "/raw_final_s1.csv"]),
       "fin2": dict(weights=FW, cls=0, s=2.1333333, raw=[OUT + "/raw_final_s2.csv"])}


def crops(model, rows, cls, s):
    """Vung cat 480 quanh nhan tren khung phong s; tra ve {(khung,vat): [(conf,x1,y1,x2,y2) toa do video]}."""
    W, H = int(round(1080 * s)), int(round(1920 * s))
    items = []
    for r in rows:
        b = tuple(v * s for v in ev.box_of(r))
        c = pc.positive_crop(b, pc.frame_seed(ev.SEED, r["obj"], r["frame"]), frame_w=W, frame_h=H)
        items.append(((int(r["frame"]), r["obj"]), c))
    out = {}
    for f, img in iter_frames(sorted({k[0] for k, _ in items})):
        if s != 1.0:
            img = cv2.resize(img, (W, H), interpolation=cv2.INTER_CUBIC)
        todo = [(k, c) for k, c in items if k[0] == f]
        arrs = [np.ascontiguousarray(img[c["y0"]:c["y0"] + 480, c["x0"]:c["x0"] + 480]) for _, c in todo]
        res = model.predict(arrs, imgsz=480, conf=0.01, device="cpu", verbose=False)
        for (k, c), rr in zip(todo, res):
            out[k] = [(float(cf), (b[0] + c["x0"]) / s, (b[1] + c["y0"]) / s, (b[2] + c["x0"]) / s, (b[3] + c["y0"]) / s)
                      for b, cf, cl in zip(rr.boxes.xyxy.numpy(), rr.boxes.conf.numpy(), rr.boxes.cls.numpy()) if int(cl) == cls]
    return out


def run(name):
    cf = CFG[name]
    labs = ev.load_labels()
    chac = [r for r in labs if r["flag"] == "chac"]
    pairs = {}
    for r in chac:
        pairs.setdefault((int(r["frame"]), r["obj"]), r)
    rows = list(pairs.values())
    raw = ev.load_raw(cf["raw"])
    cr = crops(YOLO(cf["weights"]), rows, cf["cls"], cf["s"])
    cls = cf["cls"]

    def dets(method, k, thr):
        if method == "crop":
            return [(d[1], d[2], d[3], d[4], d[0]) for d in cr[k] if d[0] >= thr]
        ds = [(d[2], d[3], d[4], d[5], d[1]) for d in raw.get(k[0], []) if d[0] == cls and d[1] >= thr]
        return pc.merge_detections(ds, 0.5)

    out = []   # metric, method, thr, group, value
    for method in ("scan", "crop"):
        for thr in THRS:
            for setn in ("sparse", "cont"):
                fr = [{"gt": ev.box_of(r), "dets": dets(method, (int(r["frame"]), r["obj"]), thr), "seg": r["seg"]}
                      for r in chac if r["set"] == setn]
                rb = em.recall_by_band(fr, 0.5, 0.0)
                for b in em.BANDS + ("all",):
                    out.append(["recall", method, thr, "%s/%s" % (setn, b), "%d/%d" % (rb[b]["hit"], rb[b]["n"])])
                for seg in ("dat_xa", "duong_bang", "cat_canh", "bay_gan", "bay_xa"):
                    sub = [f for f in fr if f["seg"] == seg]
                    if sub:
                        rs = em.recall_by_band(sub, 0.5, 0.0)["all"]
                        out.append(["recall", method, thr, "%s/%s" % (setn, seg), "%d/%d" % (rs["hit"], rs["n"])])
            for obj in ("M1", "M2"):
                rr = sorted([r for r in labs if r["set"] == "cont" and r["obj"] == obj and (obj == "M1" or r["flag"] == "chac")],
                            key=lambda r: int(r["frame"]))
                seq = [em._hit({"gt": ev.box_of(r), "dets": dets(method, (int(r["frame"]), r["obj"]), thr)}, 0.5, 0.0) for r in rr]
                ls = em.loss_summary(seq, 30.0)
                out.append(["loss", method, thr, obj, "%d/%d hit; cum>=0.25s=%d; dai_nhat=%.2fs; >=3s=%d" % (
                    sum(seq), len(seq), ls["n_short"], ls["longest_s"], ls["n_long"])])
    # bao dong gia (quet)
    byf = defaultdict(list)
    for r in labs:
        byf[(int(r["frame"]), r["set"])].append(r)
    fa_frames = [(f, st, rs, "sau1260" if f >= 1260 else "dat_xa") for (f, st), rs in byf.items()
                 if all(r["flag"] in ("chac", "am") for r in rs)]
    top = []
    for thr in THRS + [0.03]:
        for pop in ("sau1260", "dat_xa"):
            for setn in ("sparse", "cont"):
                fs = [x for x in fa_frames if x[1] == setn and x[3] == pop]
                if not fs:
                    continue
                n_fa = 0
                for f, st, rs, _ in fs:
                    gts = [ev.box_of(r) for r in rs if r["x1"] != ""]
                    for d in dets("scan", (f, ""), thr):
                        if max([em.iou(d[:4], g) for g in gts] or [0.0]) < 0.1:
                            n_fa += 1
                            if thr == 0.03:
                                top.append((d[4], f, pop, d[:4]))
                out.append(["fa", "scan", thr, "%s/%s" % (pop, setn), "%d FA / %d khung" % (n_fa, len(fs))])
    with open("%s/summary_%s.csv" % (OUT, name), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["chi_so", "cach", "nguong", "nhom", "gia_tri"])
        w.writerows(out)
    top.sort(key=lambda t: (-t[0], t[1]))
    seen, sel = set(), []
    for t in top:
        if t[1] not in seen:
            seen.add(t[1])
            sel.append(t)
        if len(sel) == 20:
            break
    with open("%s/top20_%s.csv" % (OUT, name), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["thu_tu", "conf", "khung", "quan_the", "x1", "y1", "x2", "y2"])
        for i, (c, f, pop, b) in enumerate(sel):
            w.writerow([i + 1, "%.3f" % c, f, pop] + ["%.0f" % v for v in b])
    imgs = dict(iter_frames(sorted({t[1] for t in sel})))
    os.makedirs(IMG + "/fa_final", exist_ok=True)
    vs = []
    for i, (c, f, pop, b) in enumerate(sel):
        w_ = max(b[2] - b[0], b[3] - b[1])
        win = int(max(160, min(480, 4 * w_)))
        vs.append(crop_view(imgs[f], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, win, 360.0 / win, [tuple(b) + ((0, 0, 255),)],
                            "#%d f%d c%.2f w%d" % (i + 1, f, c, round(b[2] - b[0]))))
    for k in range(0, len(vs), 12):
        cv2.imwrite("%s/fa_final/%s_%d.jpg" % (IMG, name, k // 12), montage(vs[k:k + 12], 4, (360, 360)), [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == "__main__":
    for n in sys.argv[1:] or list(CFG):
        run(n)
        print("xong", n)
