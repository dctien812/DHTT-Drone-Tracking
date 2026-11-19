"""MMFW-UAV: (b) decode day du mau ngau nhien >=500 anh/zip; (f) lien tuc cua chuoi (sai khac anh lien ke); (g) dong bo Wide/Zoom bang nang luong chuyen dong.
Chay: python -I vision/tools/mmfw/03_images_check.py   (can 02_labels_stats.py chay truoc -> boxes.csv)
Ket qua: results/mmfw_stats/{decode_check.csv,sync_lag.csv}
MAU, khong phai toan bo (seed co dinh 0).
"""
import csv, os, random, re, collections, warnings
from multiprocessing import Pool
import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EX = os.path.join(ROOT, "data", "mmfw-uav", "extracted")
RES = os.path.join(ROOT, "results", "mmfw_stats")
SETS = {"D": "Fixed-wing-UAV-D", "D'": "Fixed-wing-UAV-D'", "E": "Fixed-wing-UAV-E", "E'": "Fixed-wing-UAV-E'"}
DIRS = ["Top_Down", "Horizontal", "Bottom_Up"]
TYPES = ["Wide", "Zoom", "Infrared"]
PER_COMBO = 60  # 9 to hop huong x loai x 60 = 540 anh / zip


def jp(s, d, t, stem):
    return os.path.join(EX, SETS[s], d, t + "_Imgs", stem + ".jpg")


def decode(a):
    p = a
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with Image.open(p) as im:
                im.load()
                arr = np.asarray(im)
                return (p, "OK", im.size[0], im.size[1], im.mode, int(arr.std() > 0))
    except Exception as e:
        return (p, "FAIL:" + repr(e)[:80], 0, 0, "", 0)


def thumb(p):
    with Image.open(p) as im:
        im.draft("L", (im.size[0] // 8, im.size[1] // 8))
        return np.asarray(im.convert("L").resize((64, 36)), np.float32)


def sync(a):
    s, d = a
    stems = sorted(f[:-4] for f in os.listdir(os.path.join(EX, SETS[s], d, "Wide_Imgs")) if f.endswith(".jpg") and not f.startswith("._"))
    pat = re.compile(r"^(\d+_\d+)_(\d+)$")
    runs, cur = [], []
    for st in stems:
        m = pat.match(st)
        if cur and pat.match(cur[-1]).group(1) == m.group(1) and int(m.group(2)) - int(pat.match(cur[-1]).group(2)) == 1:
            cur.append(st)
        else:
            if cur: runs.append(cur)
            cur = [st]
    runs.append(cur)
    run = max(runs, key=len)
    mid = max(0, len(run) // 2 - 150)
    run = run[mid:mid + 300]
    tw = [thumb(jp(s, d, "Wide", x)) for x in run]
    tz = [thumb(jp(s, d, "Zoom", x)) for x in run]
    ew = np.array([np.abs(tw[i] - tw[i - 1]).mean() for i in range(1, len(tw))])
    ez = np.array([np.abs(tz[i] - tz[i - 1]).mean() for i in range(1, len(tz))])
    out = {}
    for lag in range(-3, 4):
        if lag >= 0:
            x, y = ew[lag:], ez[:len(ez) - lag]
        else:
            x, y = ew[:lag], ez[-lag:]
        out[lag] = float(np.corrcoef(x, y)[0, 1])
    best = max(out, key=out.get)
    far = [np.abs(tw[i] - tw[i + 50]).mean() for i in range(0, len(tw) - 50, 10)]
    return [s, d, len(runs), len(run), run[0], run[-1], round(float(np.median(ew)), 3), round(float(np.median(far)), 3) if far else ""] + \
           [round(out[l], 3) for l in range(-3, 4)] + [best]


if __name__ == "__main__":
    rng = random.Random(0)
    jobs = []
    for s in SETS:
        for d in DIRS:
            for t in TYPES:
                fs = sorted(f for f in os.listdir(os.path.join(EX, SETS[s], d, t + "_Imgs")) if f.endswith(".jpg"))
                for f in rng.sample(fs, PER_COMBO):
                    jobs.append(os.path.join(EX, SETS[s], d, t + "_Imgs", f))
    with Pool(8) as p:
        rs = p.map(decode, jobs, chunksize=8)
        with open(os.path.join(RES, "decode_check.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["path", "status", "w", "h", "mode", "nonconstant"])
            w.writerows(rs)
        cnt = collections.Counter()
        for r in rs:
            z = [k for k, v in SETS.items() if os.sep + v + os.sep in r[0]][0]
            cnt[(z, r[1][:4])] += 1
        print("decode:", dict(cnt))
        srs = p.map(sync, [(s, d) for s in SETS for d in DIRS])
    with open(os.path.join(RES, "sync_lag.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["set", "dir", "runs_consecutive", "frames_used", "first", "last", "median_adjacent_absdiff_wide", "median_absdiff_50apart_wide"] +
                   [f"corr_lag{l}" for l in range(-3, 4)] + ["best_lag"])
        w.writerows(srs)
    print("done 03")
