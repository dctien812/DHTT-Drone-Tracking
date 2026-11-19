"""Lap file nhan cuoi (IMG/labels.csv = .office/images/video1/labels.csv, bi git bo qua) cho video that tu: (1) hop hieu chinh tay doc tren anh phong to (MANUAL),
(2) de xuat tu realvideo_runway/realvideo_sky/realvideo_top luu o RES/proposals (da duyet bang mat, xem md).
Cot: frame,obj,x1,y1,x2,y2,flag,seg,set
 flag: chac | khong_chac (loai khoi mau so) | am (khung khong co may bay) | loai (khung bi loai: may bay bi che/khong ro)
 obj: M1 = may bay o gan nguoi roi cat canh (bay 1); M2 = may bay o xa tren dat roi bay thu hai (nhan dang M1/M2 khong du chung cu)
 set: sparse (moi 15 khung tu 1260, moi 30 khung o 0-1245) | cont (doan lien tuc 1800-2099, moi khung)
Dung: realvideo_labels.py   (khong doi so)"""
import csv
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

P = RES + "/proposals/"


def seg_of(f):
    if f < 1256:
        return "dat_xa"
    if f < 1720:
        return "duong_bang"
    if f < 1796:
        return "cat_canh"
    if f < 1891:
        return "bay_gan"
    return "bay_xa"


# hieu chinh tay: (frame,obj) -> (x1,y1,x2,y2,flag). Doc tren anh phong to x3-x4 co luoi toa do.
MANUAL = {
    (0, "M1"): (384, 959, 655, 1015, "chac"), (15, "M1"): (364, 979, 619, 1030, "chac"),
    (30, "M1"): (301, 1007, 548, 1054, "khong_chac"), (45, "M1"): (310, 1037, 440, 1075, "khong_chac"),
    (60, "M1"): (150, 1065, 275, 1100, "khong_chac"), (60, "M2"): (815, 990, 885, 1012, "khong_chac"),
    (90, "M2"): (622, 1005, 702, 1029, "khong_chac"), (120, "M2"): (560, 1007, 640, 1031, "khong_chac"),
    (150, "M2"): (591, 1014, 671, 1038, "khong_chac"), (180, "M2"): (822, 1043, 902, 1067, "khong_chac"),
    (390, "M2"): (802, 1082, 874, 1095, "chac"), (420, "M2"): (717, 1082, 786, 1096, "chac"),
    (450, "M2"): (685, 1086, 752, 1099, "chac"), (480, "M2"): (641, 1090, 704, 1102, "chac"),
    (510, "M2"): (609, 1077, 666, 1089, "chac"), (540, "M2"): (619, 1066, 669, 1078, "chac"),
    (570, "M2"): (757, 1072, 800, 1082, "chac"), (600, "M2"): (939, 1062, 985, 1076, "chac"),
    (630, "M2"): (994, 1041, 1041, 1055, "chac"), (660, "M2"): (942, 1044, 987, 1058, "chac"),
    (690, "M2"): (853, 1069, 898, 1083, "chac"), (720, "M2"): (820, 1077, 865, 1090, "chac"),
    (750, "M2"): (894, 1069, 941, 1082, "chac"), (780, "M2"): (996, 1069, 1043, 1082, "chac"),
    (810, "M2"): (990, 1091, 1036, 1104, "chac"), (840, "M2"): (851, 1109, 893, 1121, "chac"),
    (870, "M2"): (706, 1124, 741, 1136, "chac"), (900, "M2"): (624, 1142, 683, 1157, "chac"),
    (930, "M2"): (636, 1149, 699, 1165, "chac"), (960, "M2"): (663, 1149, 723, 1163, "chac"),
    (990, "M2"): (647, 1140, 702, 1155, "chac"), (1020, "M2"): (639, 1136, 697, 1150, "chac"),
    (1050, "M2"): (664, 1137, 722, 1152, "chac"), (1080, "M2"): (702, 1136, 758, 1151, "chac"),
    (1110, "M2"): (728, 1137, 785, 1150, "chac"), (1140, "M2"): (724, 1131, 779, 1145, "chac"),
    (1170, "M2"): (705, 1117, 760, 1131, "chac"), (1200, "M2"): (702, 1108, 758, 1123, "chac"),
    (1230, "M2"): (783, 1105, 839, 1119, "chac"),
    (1200, "M1"): (212, 1123, 286, 1139, "chac"), (1230, "M1"): (271, 1118, 356, 1134, "chac"),
}
EXCLUDED = [210, 240, 270, 300, 330, 360]   # may bay bi nguoi che/giu hoac cat o mep: khong dung
NEGATIVE = [1725]                            # chi thay mat dat, khong co may bay trong khung


def load(path):
    return {int(r["frame"]): (float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"]), r["flag"])
            for r in csv.DictReader(open(path))}


def anomalies(o, lo=1800, hi=2269, k=7):
    """Khung co bbox dot ngot nho/lon hon trung vi +-k khung (canh may bay dung canh mong, manh vun) -> khong chac."""
    fs = [f for f in range(lo, hi) if f in o]
    bad = set()
    for f in fs:
        w = [o[g][2] - o[g][0] for g in range(f - k, f + k + 1) if g in o]
        h = [o[g][3] - o[g][1] for g in range(f - k, f + k + 1) if g in o]
        mw, mh = sorted(w)[len(w) // 2], sorted(h)[len(h) // 2]
        cw, ch = o[f][2] - o[f][0], o[f][3] - o[f][1]
        if cw < 0.65 * mw or ch < 0.65 * mh or cw > 1.5 * mw or ch > 1.5 * mh:
            bad.add(f)
    return bad


def edge(o):
    """Khung bao cham mep khung hinh (may bay bi cat) -> khong chac."""
    return {f for f, b in o.items() if b[2] >= 1078 or b[0] <= 2 or b[1] <= 2 or b[3] >= 1918}


def main():
    run, top1, top2 = load(P + "runway_1260_1710.csv"), load(P + "top_1260_1800.csv"), load(P + "top_1800_2269.csv")
    o1, o2 = load(P + "sky_o1.csv"), load(P + "sky_o2.csv")
    a1 = anomalies(o1) | edge(o1) | {f for f, b in o1.items() if b[4] == "miss"}
    a2 = anomalies(o2) | edge(o2) | {f for f, b in o2.items() if b[4] == "miss"}
    rows = []

    def add(f, obj, b, flag, st):
        rows.append([f, obj, "%.0f" % b[0] if b else "", "%.0f" % b[1] if b else "", "%.0f" % b[2] if b else "",
                     "%.0f" % b[3] if b else "", flag, seg_of(f), st])

    sparse = [0, 15, 30, 45, 60] + list(range(90, 1231, 30)) + list(range(1260, 2266, 15))
    for f in sparse:
        if f in EXCLUDED:
            add(f, "M1", None, "loai", "sparse")
        elif f in NEGATIVE:
            add(f, "-", None, "am", "sparse")
        elif (f, "M1") in MANUAL or (f, "M2") in MANUAL:
            for obj in ("M1", "M2"):
                if (f, obj) in MANUAL:
                    m = MANUAL[(f, obj)]
                    add(f, obj, m[:4], m[4], "sparse")
        elif 1260 <= f <= 1710:
            add(f, "M1", run[f][:4], "khong_chac" if f == 1335 else "chac", "sparse")   # 1335: may bay cat o mep phai khung
        elif f in (1740, 1755, 1770):
            add(f, "M1", top1[f][:4], "khong_chac", "sparse")
        elif f == 1785:
            add(f, "M1", top1[f][:4], "chac", "sparse")
            add(f, "M2", (915, 910, 1079, 1014), "khong_chac", "sparse")   # may bay thu hai cat o mep phai (tim thay qua bao dong gia #1)
        elif 1800 <= f <= 2265:
            # khung 2145: ca hai vat chi con vet mo (lay net) -> khong chac; vi tri M1 lay tu bam theo (flag miss)
            add(f, "M1", o1[f][:4], "khong_chac" if (f in a1 or f == 2145) else "chac", "sparse")
            add(f, "M2", o2[f][:4], "khong_chac" if (f in a2 or f == 2145) else "chac", "sparse")
        else:
            raise SystemExit("khung chua gan nhan: %d" % f)
    for f in range(1800, 2100):
        add(f, "M1", o1[f][:4], "khong_chac" if f in a1 else "chac", "cont")
        add(f, "M2", o2[f][:4], "khong_chac" if f in a2 else "chac", "cont")
    with open(IMG + "/labels.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "obj", "x1", "y1", "x2", "y2", "flag", "seg", "set"])
        w.writerows(rows)
    print(len(rows))


if __name__ == "__main__":
    main()



