"""Dem khung "drone" gia tren video khong co drone (cung bo nhan dien/tham so voi may chu).
Dung: python fp_check.py <video> [giay=30]   (doc tung khung theo thu tu, khong bo khung)"""
import sys
import time

import cv2

from labview.config import DEFAULT_WEIGHTS
from labview.detector import YoloTracker

path, secs = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
cap = cv2.VideoCapture(path)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
n_max = int(secs * fps)
det = YoloTracker(DEFAULT_WEIGHTS, 640, 0.25, "bytetrack.yaml", "cpu", 4)
frames = with_det = boxes = 0
ids, confs = set(), []
t0 = time.monotonic()
while frames < n_max:
    ok, img = cap.read()
    if not ok:
        break
    if img.shape[1] > 960:
        img = cv2.resize(img, (960, round(img.shape[0] * 960 / img.shape[1])), interpolation=cv2.INTER_AREA)
    tr = det.track(img)
    frames += 1
    if tr:
        with_det += 1
        boxes += len(tr)
        ids.update(t.id for t in tr)
        confs += [t.conf for t in tr]
print(f"video={path.rsplit('/', 1)[-1]} fps={fps:.1f} khung_da_xu_ly={frames} ({frames / fps:.1f} s video) "
      f"khung_co_drone_gia={with_det} tong_khung_bao={boxes} so_ID_khac_nhau={len(ids)} "
      f"conf_max={max(confs) if confs else 0:.2f} thoi_gian_chay={time.monotonic() - t0:.0f}s")
