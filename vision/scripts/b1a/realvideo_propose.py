"""De xuat khung bao khi may bay gan nhu dung yen tren mat dat con camera tay rung/xoay:
dich chuyen camera giua cac khung duoc uoc luong bang tuong quan pha (cv2.phaseCorrelate) tren dai anh 700-1500 (thu nho 0,25),
cong don; khung bao tai khung f = khung bao cua neo gan nhat + (S[f]-S[neo]). Chi la de xuat, nhan chot bang mat.
Dung: realvideo_propose.py anchors.json out.csv [first last]   (anchors.json: {"anchors": {"600":[x1,y1,x2,y2],..}})
Dich chuyen duoc luu o RES/shift_cache.csv (khong chua anh)."""
import csv
import json
import os
import sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

CACHE = RES + "/shift_cache.csv"
LAST = 1270


def shifts():
    if os.path.exists(CACHE):
        rows = list(csv.reader(open(CACHE)))[1:]
        return np.array([[float(r[1]), float(r[2])] for r in rows])
    S = [(0.0, 0.0)]
    prev = None
    win = None
    for f, img in iter_frames(range(LAST + 1)):
        g = cv2.cvtColor(img[700:1500], cv2.COLOR_BGR2GRAY)
        g = np.float32(cv2.resize(g, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA))
        if win is None:
            win = cv2.createHanningWindow((g.shape[1], g.shape[0]), cv2.CV_32F)
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev, g, win)
            S.append((S[-1][0] + 4 * dx, S[-1][1] + 4 * dy))
        prev = g
    with open(CACHE, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "sx", "sy"])
        for i, (a, b) in enumerate(S):
            w.writerow([i, "%.2f" % a, "%.2f" % b])
    return np.array(S)


if __name__ == "__main__":
    anchors = {int(k): v for k, v in json.load(open(sys.argv[1]))["anchors"].items()}
    first = int(sys.argv[3]) if len(sys.argv) > 3 else min(anchors)
    last = int(sys.argv[4]) if len(sys.argv) > 4 else LAST
    S = shifts()
    keys = sorted(anchors)
    with open(sys.argv[2], "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
        for f in range(first, last + 1):
            a = min(keys, key=lambda k: abs(k - f))
            b = anchors[a]
            dx, dy = S[f] - S[a]
            w.writerow([f, "%.1f" % (b[0] + dx), "%.1f" % (b[1] + dy), "%.1f" % (b[2] + dx), "%.1f" % (b[3] + dy), "prop"])
