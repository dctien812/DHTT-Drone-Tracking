"""Anh ghep kiem nhan cuoi: moi vung cat phong to quanh mot nhan (frame,obj) trong labels.csv, ve khung (xanh la = chac, cam = khong chac,
xanh duong = vat khac cung khung), 12 vung/anh -> .office/images/video1/verify/<ten>_NN.jpg.
Dung: realvideo_verify.py ten set [moi_n_khung]   (set = sparse|cont; cont chi lay khung chia het cho moi_n_khung)"""
import csv
import os
import sys
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

name, st = sys.argv[1], sys.argv[2]
every = int(sys.argv[3]) if len(sys.argv) > 3 else 1
rows = [r for r in csv.DictReader(open(IMG + "/labels.csv")) if r["set"] == st and r["x1"] != ""]
rows = [r for r in rows if int(r["frame"]) % every == 0]
byf = {}
for r in rows:
    byf.setdefault(int(r["frame"]), []).append(r)
imgs = dict(iter_frames(sorted(byf)))
os.makedirs(IMG + "/verify", exist_ok=True)
views = []
for r in rows:
    f = int(r["frame"])
    b = [float(r[k]) for k in ("x1", "y1", "x2", "y2")]
    boxes = []
    for q in byf[f]:
        bb = [float(q[k]) for k in ("x1", "y1", "x2", "y2")]
        col = (0, 255, 0) if q is r and q["flag"] == "chac" else (0, 165, 255) if q is r else (255, 0, 0)
        boxes.append(tuple(bb) + (col,))
    w = max(b[2] - b[0], b[3] - b[1])
    win = int(max(120, min(480, 3 * w)))
    views.append(crop_view(imgs[f], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, win, 360.0 / win, boxes,
                           "%d %s %s w%d" % (f, r["obj"], r["flag"], round(b[2] - b[0]))))
for k in range(0, len(views), 12):
    cv2.imwrite("%s/verify/%s_%02d.jpg" % (IMG, name, k // 12), montage(views[k:k + 12], 4, (360, 360)),
                [cv2.IMWRITE_JPEG_QUALITY, 90])
print(len(views), "cells", (len(views) + 11) // 12, "sheets")
