"""De xuat khung bao bang so khop mau (cv2.matchTemplate, TM_CCOEFF_NORMED, mau BGR) voi cac mau cat tu neo do nguoi dat,
tim tren dai y 850-1400 cua cac khung cho truoc. Moi khung: lay mau co diem cao nhat. Chi la de xuat, nhan chot bang mat.
Dung: realvideo_tmatch.py anchors.json out.csv start stop step
anchors.json: {"anchors": {"600":[x1,y1,x2,y2], ...}}  Ghi: frame,x1,y1,x2,y2,flag(score:neo)"""
import csv
import json
import os
import sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

anchors = {int(k): v for k, v in json.load(open(sys.argv[1]))["anchors"].items()}
a, b, st = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
frames = list(range(a, b, st))
tmpl = {}
for f, img in iter_frames(list(anchors)):
    x1, y1, x2, y2 = [int(round(v)) for v in anchors[f]]
    tmpl[f] = img[y1:y2, x1:x2].copy()
Y0, Y1 = 850, 1400
with open(sys.argv[2], "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
    for f, img in iter_frames(frames):
        band = img[Y0:Y1]
        best = None
        for k, t in tmpl.items():
            r = cv2.matchTemplate(band, t, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(r)
            if best is None or mx > best[0]:
                best = (mx, loc, k, t.shape)
        mx, (lx, ly), k, (th, tw, _) = best
        w.writerow([f, lx, ly + Y0, lx + tw, ly + Y0 + th, "%.2f:%d" % (mx, k)])
