"""Phat hien tho model final (lop 0 = may bay) tren cac o lat 480 chong lan 200 cua khung video, CPU.
Co the phong khung len he so s truoc khi lat (s=2304/1080: dung thang huan luyen 'khung co ve rong 2304'); toa do ghi ve pixel video goc.
Dung: realvideo_final_detect.py out.csv scale   (khung = hop cac khung trong labels.csv). Ghi frame,cls,conf,x1,y1,x2,y2 (conf>=0,01)."""
import csv
import os
import sys
import time
import numpy as np
import cv2
from ultralytics import YOLO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

WEIGHTS = ROOT + "/vision/results/b1a/train/runs/b1a_final_s0/weights/best.pt"

if __name__ == "__main__":
    out, s = sys.argv[1], float(sys.argv[2])
    frames = sorted({int(r["frame"]) for r in csv.DictReader(open(IMG + "/labels.csv"))})
    model = YOLO(WEIGHTS)
    W, H = int(round(1080 * s)), int(round(1920 * s))
    ts = tiles(W, H)
    t0 = time.time()
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "cls", "conf", "x1", "y1", "x2", "y2"])
        for n, (f, img) in enumerate(iter_frames(frames)):
            if s != 1.0:
                img = cv2.resize(img, (W, H), interpolation=cv2.INTER_CUBIC)
            arrs = [np.ascontiguousarray(img[y:y + CROP, x:x + CROP]) for x, y in ts]
            res = model.predict(arrs, imgsz=480, conf=0.01, device="cpu", verbose=False)
            for (x0, y0), r in zip(ts, res):
                for b, c, k in zip(r.boxes.xyxy.numpy(), r.boxes.conf.numpy(), r.boxes.cls.numpy()):
                    w.writerow([f, int(k), "%.4f" % c] + ["%.1f" % ((v + o) / s) for v, o in zip(b, (x0, y0, x0, y0))])
            if n % 40 == 0:
                print("%d/%d %.0fs" % (n, len(frames), time.time() - t0), flush=True)
