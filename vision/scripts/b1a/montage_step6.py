"""B1a buoc 6(e): 24 anh ghep co ve khung nhan + 2 anh ghep 20 vung nen kiem thu (dung de xem bang mat).
Chay (WSL): cd /mnt/d/Personal/Drone-Tracking/vision && ~/venv-vision/bin/python scripts/b1a/montage_step6.py
"""
import csv
import os
import random

import cv2
import numpy as np

VISION = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DATA = os.path.join(VISION, "data", "b1a")
OUT = os.path.join(VISION, "results", "b1a", "step6", "montage")
os.makedirs(OUT, exist_ok=True)


def rows(split):
    with open(os.path.join(DATA, "index", split + ".csv")) as f:
        return [r for r in csv.DictReader(f) if r["path"]]


def tile(path, label_path, size, text):
    im = cv2.imread(path)
    im = cv2.resize(im, (size, size), interpolation=cv2.INTER_AREA)
    if label_path and os.path.exists(label_path):
        for ln in open(label_path).read().split("\n"):
            v = ln.split()
            if len(v) == 5:
                cx, cy, w, h = (float(x) * size for x in v[1:])
                cv2.rectangle(im, (int(cx - w / 2) - 2, int(cy - h / 2) - 2), (int(cx + w / 2) + 2, int(cy + h / 2) + 2), (0, 0, 255), 1)
    cv2.putText(im, text, (3, size - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    return im


def grid(tiles, cols):
    rws = [np.hstack(tiles[i:i + cols] + [np.zeros_like(tiles[0])] * (cols - len(tiles[i:i + cols])))
           for i in range(0, len(tiles), cols)]
    return np.vstack(rws)


def make(name, items, size=320, cols=4):
    t = [tile(p, lp, size, tx) for p, lp, tx in items]
    cv2.imwrite(os.path.join(OUT, name + ".jpg"), grid(t, cols), [cv2.IMWRITE_JPEG_QUALITY, 90])


def items_for(split, kind, pick):
    out = []
    for r in pick:
        p = os.path.join(DATA, "yolo", "images", r["path"])
        lp = os.path.join(DATA, "yolo", "labels", split, os.path.splitext(os.path.basename(r["path"]))[0] + ".txt")
        out.append((p, lp, "%s %s w=%.0f" % (r["segment"], r["frame"][-6:], float(r["box_w"]))))
    return out


rng = random.Random(7)
n = 0
for split, kind in (("train", "pos"), ("train", "bg"), ("val", "pos"), ("val", "bg"),
                    ("test", "pos"), ("test", "off"), ("test", "bg")):
    R = [r for r in rows(split) if r["kind"] == kind]
    for d in ("Top_Down", "Horizontal", "Bottom_Up"):
        Q = [r for r in R if r["segment"].endswith("/" + d)]
        make("%s_%s_%s" % (split, kind, d), items_for(split, kind, rng.sample(Q, 12)))
        n += 1
bird = sorted(os.listdir(os.path.join(DATA, "yolo", "images", "train")))
bird = [b for b in bird if b.startswith("bird_")]
make("bird_train", [(os.path.join(DATA, "yolo", "images", "train", b), None, b[:20]) for b in rng.sample(bird, 12)])
fa = sorted(os.listdir(os.path.join(DATA, "birds_fa")))
make("bird_fa150", [(os.path.join(DATA, "birds_fa", b), None, b[:20]) for b in rng.sample(fa, 12)])
# khong co khung truncated nao -> thay bang 12 khung kiem thu nho nhat (kho nhat)
T = sorted((r for r in rows("test") if r["kind"] == "pos"), key=lambda r: float(r["box_w"]))
make("test_pos_smallest", items_for("test", "pos", T[:12]))
bgs = [r for r in rows("test") if r["kind"] == "bg"]
print("so anh ghep:", len(os.listdir(OUT)))
# 20 vung nen kiem thu, anh lon, de tim may bay lot vao nen
pick = rng.sample(bgs, 20)
for i in (0, 1):
    t = [tile(os.path.join(DATA, "yolo", "images", r["path"]), None, 384, "%s %s" % (r["segment"], r["frame"][-6:]))
         for r in pick[i * 10:(i + 1) * 10]]
    cv2.imwrite(os.path.join(OUT, "check20bg_%d.jpg" % i), grid(t, 5), [cv2.IMWRITE_JPEG_QUALITY, 92])
with open(os.path.join(OUT, "check20bg.txt"), "w") as f:
    for i, r in enumerate(pick):
        f.write("%d\t%s\n" % (i, r["path"]))
