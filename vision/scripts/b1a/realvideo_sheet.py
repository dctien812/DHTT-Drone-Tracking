"""Anh ghep kiem nhan: 12 vung cat phong to (4x3, o 360 px) quanh khung bao, co ve khung va thuoc toa do khung (pixel video).
Dung: realvideo_sheet.py out_prefix start stop step csv1[:mau] [csv2[:mau] ...]
 csv co cot frame,x1,y1,x2,y2 (hoac nhan: frame,x1,y1,x2,y2,flag,seg,...). Cua so lay tam theo csv1; khung khong co dong -> bo qua."""
import csv
import os
import sys
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

COLORS = {"g": (0, 255, 0), "o": (0, 165, 255), "b": (255, 0, 0), "r": (0, 0, 255), "y": (0, 255, 255)}


def load(path):
    out = {}
    for r in csv.DictReader(open(path)):
        if r["x1"] in ("", None):
            continue
        out.setdefault(int(r["frame"]), []).append((float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"]),
                                                      r.get("flag", "")))
    return out


def sheet(out_prefix, frames, srcs, minwin=120):
    data = []
    for s in srcs:
        p, _, c = s.partition(":")
        data.append((load(p), COLORS.get(c or "g", (0, 255, 0))))
    frames = [f for f in frames if f in data[0][0]]
    views = []
    n = 0
    imgs = dict(iter_frames(frames))
    for f in frames:
        b = data[0][0][f][0]
        w = max(b[2] - b[0], b[3] - b[1])
        win = int(max(minwin, min(480, 3 * w)))
        boxes = [(q[0], q[1], q[2], q[3], col) for d, col in data for q in d.get(f, [])]
        flag = data[0][0][f][0][4]
        views.append(crop_view(imgs[f], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, win, 360.0 / win, boxes,
                               "%d w%d %s" % (f, round(b[2] - b[0]), flag)))
    paths = []
    for k in range(0, len(views), 12):
        p = "%s_%02d.jpg" % (out_prefix, k // 12)
        cv2.imwrite(p, montage(views[k:k + 12], 4, (360, 360)), [cv2.IMWRITE_JPEG_QUALITY, 90])
        paths.append(p)
    return paths


if __name__ == "__main__":
    pre, a, b, st = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    print(sheet(pre, list(range(a, b, st)), sys.argv[5:]))
