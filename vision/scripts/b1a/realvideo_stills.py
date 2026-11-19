"""(f) Hai anh tinh: yolov8n.pt goc, (1) ca anh thu nho imgsz 640, (2) o lat 480 chong lan 200 tren anh goc roi gop (IoU 0,5).
Ghi RES/stills.csv (moi phat hien lop airplane/bird/kite, conf >= 0,10) va ve anh ket qua vao IMG/stills (bi git bo qua).
Dung: realvideo_stills.py"""
import csv
import os
import sys
import cv2
import numpy as np
from ultralytics import YOLO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *
import prep_crops as pc

FILES = ["may-bay-muc-tieu-san-bay-2026-11-19.png", "may-bay-muc-tieu-2026-11-19.png"]
model = YOLO(ROOT + "/vision/weights/yolov8n.pt")
os.makedirs(IMG + "/stills", exist_ok=True)
rows = []
for fn in FILES:
    im = cv2.imread(ROOT + "/.office/images/" + fn, cv2.IMREAD_COLOR)
    if im.shape[2] == 4:
        im = im[:, :, :3]
    h, w = im.shape[:2]
    print(fn, "kich thuoc", w, h)
    # (1) ca anh thu nho
    r = model.predict([im], imgsz=640, conf=0.10, device="cpu", verbose=False)[0]
    full = [(int(k), float(c), *b) for b, c, k in zip(r.boxes.xyxy.numpy(), r.boxes.conf.numpy(), r.boxes.cls.numpy())]
    # (2) o lat
    ts = [(x, y) for y in starts(h, CROP, 200) for x in starts(w, CROP, 200)] if min(w, h) >= CROP else []
    ds = []
    if ts:
        arrs = [np.ascontiguousarray(im[y:y + CROP, x:x + CROP]) for x, y in ts]
        rr = model.predict(arrs, imgsz=480, conf=0.10, device="cpu", verbose=False)
        for (x0, y0), q in zip(ts, rr):
            for b, c, k in zip(q.boxes.xyxy.numpy(), q.boxes.conf.numpy(), q.boxes.cls.numpy()):
                ds.append((int(k), float(c), b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0))
    tile = []
    for k in {d[0] for d in ds}:
        sub = [(d[2], d[3], d[4], d[5], d[1]) for d in ds if d[0] == k]
        tile += [(k, m[4], m[0], m[1], m[2], m[3]) for m in pc.merge_detections(sub, 0.5)]
    for name, dets in (("thu_nho_640", full), ("o_lat_480", tile)):
        for d in sorted(dets, key=lambda d: -d[1]):
            if d[0] in (4, 14, 33):
                rows.append([fn, name, "airplane" if d[0] == 4 else "bird" if d[0] == 14 else "kite", "%.3f" % d[1]] +
                            ["%.0f" % v for v in d[2:]])
        vis = im.copy()
        for d in dets:
            if d[0] in (4, 14, 33) and d[1] >= 0.10:
                col = (0, 255, 0) if d[0] == 4 else (0, 165, 255)
                cv2.rectangle(vis, (int(d[2]), int(d[3])), (int(d[4]), int(d[5])), col, 3)
                cv2.putText(vis, "%s %.2f" % ({4: "air", 14: "bird", 33: "kite"}[d[0]], d[1]), (int(d[2]), max(int(d[3]) - 6, 14)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2)
        cv2.imwrite("%s/stills/%s_%s.jpg" % (IMG, os.path.splitext(fn)[0][:20], name), vis, [cv2.IMWRITE_JPEG_QUALITY, 88])
with open(RES + "/stills.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["anh", "cach", "lop", "conf", "x1", "y1", "x2", "y2"])
    w.writerows(rows)
print(len(rows), "phat hien")
