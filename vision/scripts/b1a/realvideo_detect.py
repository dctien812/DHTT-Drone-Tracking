"""Phat hien tho yolov8n (moi lop, conf 0.01, imgsz 480) tren cac o lat 480 chong lan 200 cua khung 1080x1920.
Dung: realvideo_detect.py out.csv start stop step   (hoac: out.csv list a,b,c)
Ghi dong tho theo toa do khung: frame,cls,conf,x1,y1,x2,y2 (chua gop). Khong luu anh."""
import csv
import os
import sys
import time
import numpy as np
from ultralytics import YOLO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

WEIGHTS = ROOT + "/vision/weights/yolov8n.pt"


def detect(model, bgr, conf=0.01):
    ts = tiles()
    arrs = [np.ascontiguousarray(bgr[y:y + CROP, x:x + CROP]) for x, y in ts]
    res = model.predict(arrs, imgsz=480, conf=conf, device="cpu", verbose=False)
    rows = []
    for (x0, y0), r in zip(ts, res):
        for b, c, k in zip(r.boxes.xyxy.numpy(), r.boxes.conf.numpy(), r.boxes.cls.numpy()):
            rows.append((int(k), float(c), b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0))
    return rows


if __name__ == "__main__":
    out = sys.argv[1]
    if sys.argv[2] == "list":
        ids = [int(v) for v in sys.argv[3].split(",")]
    else:
        ids = list(range(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])))
    model = YOLO(WEIGHTS)
    t0 = time.time()
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "cls", "conf", "x1", "y1", "x2", "y2"])
        done = 0
        for f, bgr in iter_frames(ids):
            for k, c, x1, y1, x2, y2 in detect(model, bgr):
                w.writerow([f, k, "%.4f" % c, "%.1f" % x1, "%.1f" % y1, "%.1f" % x2, "%.1f" % y2])
            done += 1
            if done % 20 == 0:
                print("%d/%d %.0fs" % (done, len(ids), time.time() - t0), flush=True)
