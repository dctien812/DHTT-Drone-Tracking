"""(d) Thong ke nhan + quy doi tham khao sang dai co cua du an, va recall theo dai theo thang quy doi.
Gia dinh quy doi (KHONG do duoc, chi tham khao): dien thoai ong kinh chinh ~26 mm tuong duong (truc dai 36 mm: goc nhin truc dai 69,4 do),
tieu cu = 1920 / (2*tan(34,7 do)) = 1386 px tren truc dai 1920; camera du an 933 px. He so = 933/1386 = 0,673:
cung mot vat o cung goc nhin rong w_video px thi rong 0,673*w_video px tren camera du an (thang 2304).
Dau ra RES/stats_labels.csv, RES/stats_width.csv, RES/recall_converted.csv. Dung: realvideo_stats.py"""
import csv
import math
import os
import sys
from collections import Counter, defaultdict
import numpy as np
from ultralytics import YOLO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *
import eval_metrics as em
import realvideo_eval as ev

K = 933.0 / (1920 / (2 * math.tan(math.radians(34.7))))


def main():
    labs = ev.load_labels()
    with open(RES + "/stats_labels.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["tap", "doan", "vat", "co", "so_nhan", "so_khung_khac_nhau"])
        c = Counter()
        fr = defaultdict(set)
        for r in labs:
            k = (r["set"], r["seg"], r["obj"], r["flag"])
            c[k] += 1
            fr[k].add(r["frame"])
        for k in sorted(c):
            w.writerow(list(k) + [c[k], len(fr[k])])
        # tong so khung khac nhau
        allf = {(r["frame"]) for r in labs}
        w.writerow(["TONG", "", "", "khung_khac_nhau_ca_hai_tap", len(labs), len(allf)])
    # be rong khung bao theo pixel video, chi nhan 'chac'
    with open(RES + "/stats_width.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["tap", "doan", "vat", "n", "rong_min", "rong_p10", "rong_median", "rong_p90", "rong_max",
                    "cao_median", "median_quy_doi_du_an", "dai_du_an(<16|16-57|57-200|>200):so_nhan"])
        g = defaultdict(list)
        for r in labs:
            if r["flag"] == "chac":
                b = ev.box_of(r)
                g[(r["set"], r["seg"], r["obj"])].append((b[2] - b[0], b[3] - b[1]))
                g[(r["set"], "TAT_CA", r["obj"])].append((b[2] - b[0], b[3] - b[1]))
        for k in sorted(g):
            a = np.array(g[k])
            ws = a[:, 0]
            bands = Counter(em.size_band(x * K) or "<16" for x in ws)
            w.writerow(list(k) + [len(a)] + ["%.0f" % v for v in (ws.min(), np.percentile(ws, 10), np.median(ws), np.percentile(ws, 90), ws.max())] +
                       ["%.0f" % np.median(a[:, 1]), "%.0f" % (np.median(ws) * K),
                        " ".join("%s:%d" % (b, bands.get(b, 0)) for b in ("<16", "16-57", "57-200", ">200"))])
    # recall theo dai quy doi (bang bbox nhan va phat hien nhan K; IoU khong doi)
    chac = [r for r in labs if r["flag"] == "chac"]
    pairs = {}
    for r in chac:
        pairs.setdefault((int(r["frame"]), r["obj"]), r)
    rows = list(pairs.values())
    raw = ev.load_raw([RES + "/raw_pass1.csv", RES + "/raw_cont.csv"])
    model = YOLO(ROOT + "/vision/weights/yolov8n.pt")
    crop = ev.crop_results(model, rows)
    out = []
    for method in ("crop", "scan"):
        for thr in ev.THRS:
            fr = []
            for r in chac:
                k = (int(r["frame"]), r["obj"])
                if method == "crop":
                    ds = [(d[2], d[3], d[4], d[5], d[1]) for d in crop[k] if d[0] == 4 and d[1] >= thr]
                else:
                    ds = ev.scan_dets(raw, k[0], thr)
                sc = lambda b: tuple(v * K for v in b[:4]) + tuple(b[4:])
                fr.append({"gt": sc(ev.box_of(r)), "dets": [sc(d) for d in ds], "seg": r["seg"], "set": r["set"]})
            for setn in ("sparse", "cont"):
                rb = em.recall_by_band([f for f in fr if f["set"] == setn], 0.5, 0.0)
                for band in em.BANDS + ("all",):
                    v = rb[band]
                    out.append([method, thr, setn, band, v["n"], v["hit"], "" if v["recall"] is None else "%.4f" % v["recall"]])
    with open(RES + "/recall_converted.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cach", "nguong", "tap", "dai_du_an_quy_doi", "n", "trung", "recall"])
        w.writerows(out)
    print("K =", K)


if __name__ == "__main__":
    main()
