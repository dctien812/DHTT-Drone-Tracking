"""Do vat toi tren nen troi sang (de xuat nhan khi may bay bay), theo doi nhieu may bay.
Nen = dong (closing) 31x31 cua anh xam; vat = nen - anh > 35 (day du do phan giai); dan no 9x9 chi de gom manh;
bbox lay tu diem anh goc. Cac manh cach nhau <= 14 px gop thanh mot nhom. Moi vat duoc bam theo bang nhom gan nhat
(trong ban kinh R) voi vi tri truoc, moi nhom chi gan cho mot vat. Chi la de xuat; nhan chot bang mat.
Dung: realvideo_sky.py out_prefix first last step R "name:frame:cx:cy" ["name2:frame:cx:cy" ...]
Ghi out_prefix_<name>.csv: frame,x1,y1,x2,y2,flag (sky<so diem> hoac miss) tu khung bat dau cua vat."""
import csv
import os
import sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

K1 = cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31))
K2 = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))


def groups(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, K1)
    m0 = ((bg.astype(np.int16) - g.astype(np.int16)) > 35).astype(np.uint8)
    m = cv2.dilate(m0, K2)
    n, lab, stt, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    bl = []
    for i in range(1, n):
        x, y, w, h, ar = stt[i]
        if ar < 20 or w > 260 or h > 260:
            continue
        sub = m0[y:y + h, x:x + w] & (lab[y:y + h, x:x + w] == i)
        ys, xs = np.nonzero(sub)
        if xs.size < 6:
            continue
        bl.append([x + xs.min(), y + ys.min(), x + xs.max() + 1, y + ys.max() + 1, int(xs.size)])
    merged = True
    while merged:
        merged = False
        for i in range(len(bl)):
            for j in range(i + 1, len(bl)):
                a, b = bl[i], bl[j]
                if a[0] < b[2] + 14 and a[2] > b[0] - 14 and a[1] < b[3] + 14 and a[3] > b[1] - 14:
                    bl[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]), a[4] + b[4]]
                    del bl[j]
                    merged = True
                    break
            if merged:
                break
    return bl


if __name__ == "__main__":
    pre, a, b, st, R = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
    objs = []
    for s in sys.argv[6:]:
        n, f0, cx, cy = s.split(":")
        objs.append({"name": n, "f0": int(f0), "prev": (float(cx), float(cy)), "rows": []})
    for f, img in iter_frames(range(a, b, st)):
        bl = groups(img)
        used = set()
        for o in objs:
            if f < o["f0"]:
                continue
            best = None
            for k, q in enumerate(bl):
                if k in used:
                    continue
                c = ((q[0] + q[2]) / 2, (q[1] + q[3]) / 2)
                d = np.hypot(c[0] - o["prev"][0], c[1] - o["prev"][1])
                if d < R and (best is None or d < best[0]):
                    best = (d, k, c)
            if best:
                used.add(best[1])
                q = bl[best[1]]
                o["prev"] = best[2]
                o["rows"].append((f, q[0], q[1], q[2], q[3], "sky%d" % q[4]))
            else:
                p = o["prev"]
                o["rows"].append((f, p[0] - 15, p[1] - 8, p[0] + 15, p[1] + 8, "miss"))
    for o in objs:
        with open("%s_%s.csv" % (pre, o["name"]), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "x1", "y1", "x2", "y2", "flag"])
            for r in o["rows"]:
                w.writerow([r[0]] + ["%.0f" % v for v in r[1:5]] + [r[5]])
