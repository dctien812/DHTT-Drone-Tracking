"""De xuat khung bao cho may bay nho tren dat: cat cua so 200x200 quanh hat giong (nguoi dat), phong to x3, chay yolov8n (conf 0,03, imgsz 640),
lay phat hien lop 4/14/33/5/6/7/8 gan tam nhat theo conf*gan; chuyen ve toa do khung. Chi la de xuat; nhan chot bang mat.
Dung: realvideo_zoomdet.py out.csv seeds.json"""
import csv
import json
import os
import sys
import cv2
import numpy as np
from ultralytics import YOLO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

seeds = {int(k): v for k, v in json.load(open(sys.argv[2])).items()}
model = YOLO(ROOT + "/vision/weights/yolov8n.pt")
Z = 3
with open(sys.argv[1], "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
    for f, img in iter_frames(sorted(seeds)):
        cx, cy = seeds[f]
        x0 = int(min(max(cx - 100, 0), 1080 - 200))
        y0 = int(min(max(cy - 100, 0), 1920 - 200))
        crop = cv2.resize(img[y0:y0 + 200, x0:x0 + 200], None, fx=Z, fy=Z, interpolation=cv2.INTER_CUBIC)
        r = model.predict([crop], imgsz=640, conf=0.03, device="cpu", verbose=False)[0]
        best = None
        for b, c, k in zip(r.boxes.xyxy.numpy(), r.boxes.conf.numpy(), r.boxes.cls.numpy()):
            if int(k) not in (4, 14, 33, 5, 6, 7, 8):
                continue
            bx = (x0 + b[0] / Z, y0 + b[1] / Z, x0 + b[2] / Z, y0 + b[3] / Z)
            d = np.hypot((bx[0] + bx[2]) / 2 - cx, (bx[1] + bx[3]) / 2 - cy)
            if d > 50:
                continue
            sc = float(c) * (1 - d / 60)
            if best is None or sc > best[0]:
                best = (sc, bx, int(k), float(c))
        if best:
            bx = best[1]
            w.writerow([f, "%.0f" % bx[0], "%.0f" % bx[1], "%.0f" % bx[2], "%.0f" % bx[3], "z%.2f/c%d" % (best[3], best[2])])
        else:
            w.writerow([f, "%.0f" % (cx - 30), "%.0f" % (cy - 10), "%.0f" % (cx + 30), "%.0f" % (cy + 10), "nodet"])
