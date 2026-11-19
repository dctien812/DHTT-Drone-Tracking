"""De xuat nhan cho phan may bay ro tu chuoi phat hien tho cua yolov8n (moi lop tru 'person', conf >= 0,03):
tu hat giong (frame,cx,cy) chon phat hien co conf cao nhat trong ban kinh R quanh vi tri truoc; khong co thi dung lai vi tri truoc
(co 'miss'). Chi la de xuat; nhan chot bang mat sau khi xem anh ghep.
Dung: realvideo_chain.py out.csv first last step cx cy [raw1.csv raw2.csv ...]"""
import csv
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

out, a, b, st, cx, cy = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
raws = sys.argv[7:] or [RES + "/raw_pass1.csv"]
dets = {}
for p in raws:
    for r in csv.DictReader(open(p)):
        c = int(r["cls"])
        if c not in (4, 14, 33, 7, 8) or float(r["conf"]) < 0.05:
            continue
        dets.setdefault(int(r["frame"]), []).append((float(r["conf"]), c, float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"])))
R = 500.0
prev = (cx, cy)
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
    for f in range(a, b, st):
        c = [d for d in dets.get(f, []) if abs((d[2] + d[4]) / 2 - prev[0]) < R and abs((d[3] + d[5]) / 2 - prev[1]) < R]
        if c:
            d = max(c, key=lambda d: d[0])
            prev = ((d[2] + d[4]) / 2, (d[3] + d[5]) / 2)
            w.writerow([f, "%.1f" % d[2], "%.1f" % d[3], "%.1f" % d[4], "%.1f" % d[5], "m%.2f/c%d" % (d[0], d[1])])
        else:
            w.writerow([f, "%.1f" % (prev[0] - 20), "%.1f" % (prev[1] - 10), "%.1f" % (prev[0] + 20), "%.1f" % (prev[1] + 10), "miss"])

