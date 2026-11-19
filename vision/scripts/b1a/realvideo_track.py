"""Du doan khung bao bang tracker MIL (OpenCV) tu cac neo do nguoi dat. Chi la DE XUAT; nhan chot sau khi xem bang mat.
Dung: realvideo_track.py anchors.json out.csv
anchors.json: {"obj": "A", "anchors": {"600": [x1,y1,x2,y2], ...}, "stop": {"600": 1260}}
 - Tai moi neo, tracker khoi tao lai tai khung do; chay toi neo ke tiep hoac khung 'stop' (neo cuoi) .
Ghi: frame,x1,y1,x2,y2,ok (tracker.update tra ve)."""
import csv
import json
import os
import sys
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

spec = json.load(open(sys.argv[1]))
anchors = {int(k): v for k, v in spec["anchors"].items()}
stops = {int(k): v for k, v in spec.get("stop", {}).items()}
keys = sorted(anchors)
ranges = []
for i, k in enumerate(keys):
    end = keys[i + 1] if i + 1 < len(keys) else stops.get(k, k + 1)
    end = min(end, stops.get(k, end))
    ranges.append((k, end))
need = set()
for a, e in ranges:
    need.update(range(a, e + 1))
tr = None
cur_end = -1
rows = []
for f, img in iter_frames(sorted(need)):
    for a, e in ranges:
        if f == a:
            b = anchors[a]
            tr = cv2.TrackerMIL_create()
            tr.init(img, (int(b[0]), int(b[1]), int(b[2] - b[0]), int(b[3] - b[1])))
            cur_end = e
            rows.append((f, b[0], b[1], b[2], b[3], 1))
            break
    else:
        if tr is not None and f <= cur_end:
            ok, r = tr.update(img)
            rows.append((f, r[0], r[1], r[0] + r[2], r[1] + r[3], int(ok)))
with open(sys.argv[2], "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["frame", "x1", "y1", "x2", "y2", "ok"])
    for r in rows:
        w.writerow(["%d" % r[0]] + ["%.1f" % v for v in r[1:5]] + [r[5]])
print(len(rows))
