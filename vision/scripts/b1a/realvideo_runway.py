"""De xuat khung bao may bay tren duong bang (may bay trang/cam tren nen toi): vung sang (xam > 185) hoac hong/cam (R-B > 45)
trong cua so quanh hat giong, hop voi cac phat hien tho cua yolov8n (lop may bay/chim/dieu/xe...) chong len vung do.
Hat giong: --seeds seeds.json {"1260":[cx,cy],...} (nguoi dat) hoac phat hien lop airplane conf >= 0,3 trong khung.
Chi la de xuat; nhan chot bang mat.
Dung: realvideo_runway.py out.csv seeds.json first last step [raw1.csv ...]"""
import csv
import json
import os
import sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

out, seeds_p, a, b, st = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
raws = sys.argv[6:] or [RES + "/raw_pass1.csv"]
seeds = {int(k): v for k, v in json.load(open(seeds_p)).items()}
dets = {}
for p in raws:
    for r in csv.DictReader(open(p)):
        dets.setdefault(int(r["frame"]), []).append((int(r["cls"]), float(r["conf"]), float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"])))


def iou(p, q):
    iw = min(p[2], q[2]) - max(p[0], q[0])
    ih = min(p[3], q[3]) - max(p[1], q[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    i = iw * ih
    return i / ((p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - i)


frames = list(range(a, b, st))
last = None
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
    for f, img in iter_frames(frames):
        if f not in seeds and os.environ.get("ONLY_SEEDS"):
            continue
        if f in seeds:
            cx, cy = seeds[f]
            src = "seed"
        else:
            c = [d for d in dets.get(f, []) if d[0] == 4 and d[1] >= 0.3]
            if c:
                d = max(c, key=lambda d: d[1])
                cx, cy, src = (d[2] + d[4]) / 2, (d[3] + d[5]) / 2, "auto%.2f" % d[1]
            elif last:
                cx, cy = last
                src = "prev"
            else:
                continue
        last = (cx, cy)
        x0, x1 = int(max(cx - 160, 0)), int(min(cx + 160, 1080))
        y0, y1 = int(max(cy - 45, 0)), int(min(cy + 45, 1920))
        roi = img[y0:y1, x0:x1].astype(np.int16)
        g = roi.mean(axis=2)
        m = ((g > 185) | (((roi[:, :, 2] - roi[:, :, 0]) > 45) & (roi[:, :, 2] > 120))).astype(np.uint8)
        m = cv2.dilate(m, np.ones((3, 3), np.uint8))
        n, lab, stt, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
        box = None
        comps = []
        for i in range(1, n):
            x, y, ww, hh, ar = stt[i]
            if ar >= 15:
                comps.append((x0 + x, y0 + y, x0 + x + ww, y0 + y + hh, int(ar)))
        near = [q for q in comps if q[0] - 25 < cx < q[2] + 25 and q[1] - 20 < cy < q[3] + 20]
        if near:
            main = max(near, key=lambda q: q[4])
            box = main[:4]
            for q in comps:
                if q[0] < main[2] + 8 and q[2] > main[0] - 8 and q[1] < main[3] + 8 and q[3] > main[1] - 8:
                    box = (min(box[0], q[0]), min(box[1], q[1]), max(box[2], q[2]), max(box[3], q[3]))
        if box is None:
            box = (cx - 30, cy - 12, cx + 30, cy + 12)
            src += "/noblob"
        else:
            bw = box[2] - box[0]
            for d in dets.get(f, []):
                if d[0] in (4, 14, 33, 13, 7, 8, 5, 6) and d[1] >= 0.1 and iou(box, d[2:]) > 0.25 and (d[4] - d[2]) <= 1.4 * bw:
                    box = (min(box[0], d[2]), min(box[1], d[3]), max(box[2], d[4]), max(box[3], d[5]))
        if box[2] - box[0] > 160:
            # khoi sang nuot ca vach son: dung hop cac phat hien lop may bay (rong <= 150) o gan hat giong
            cand = [d for d in dets.get(f, []) if d[0] in (4, 14, 33) and d[1] >= 0.2 and (d[4] - d[2]) <= 150
                    and abs((d[2] + d[4]) / 2 - cx) < 120 and abs((d[3] + d[5]) / 2 - cy) < 60]
            if cand:
                top = max(cand, key=lambda d: d[1])
                grp = [d for d in cand if iou(top[2:], d[2:]) > 0.15]
                box = (min(d[2] for d in grp), min(d[3] for d in grp), max(d[4] for d in grp), max(d[5] for d in grp))
                src += "/modelunion"
        w.writerow([f, "%.0f" % box[0], "%.0f" % box[1], "%.0f" % box[2], "%.0f" % box[3], src])



