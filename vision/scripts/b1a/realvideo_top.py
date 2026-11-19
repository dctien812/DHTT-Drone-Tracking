"""De xuat: voi moi khung, phat hien tho conf cao nhat cua cac lop khac 'person' (conf >= 0,03) lam de xuat 1 (csv out),
va luu top-3 vao out_top3.csv de xem. Chi la de xuat, nhan chot bang mat.
Dung: realvideo_top.py out.csv first last step [raw1.csv ...]"""
import csv
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

out, a, b, st = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
raws = sys.argv[5:] or [RES + "/raw_pass1.csv"]
dets = {}
for p in raws:
    for r in csv.DictReader(open(p)):
        c = int(r["cls"])
        if c == 0 or float(r["conf"]) < 0.03:
            continue
        dets.setdefault(int(r["frame"]), []).append((float(r["conf"]), c, float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"])))
with open(out, "w", newline="") as fh, open(out.replace(".csv", "_top3.csv"), "w", newline="") as f3:
    w = csv.writer(fh)
    w3 = csv.writer(f3)
    w.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
    w3.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
    for f in range(a, b, st):
        c = sorted(dets.get(f, []), key=lambda d: -d[0])
        for i, d in enumerate(c[:3]):
            row = [f, "%.1f" % d[2], "%.1f" % d[3], "%.1f" % d[4], "%.1f" % d[5], "m%.2f/c%d" % (d[0], d[1])]
            (w if i == 0 else w3).writerow(row)
