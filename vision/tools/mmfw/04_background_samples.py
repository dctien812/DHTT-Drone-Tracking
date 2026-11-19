"""MMFW-UAV: (f) phan loai nen THO quanh khung (>=300 anh Wide moi huong, mau seed 0) va (h) 12 anh mau thu nho co ve khung.
Chay: python -I vision/tools/mmfw/04_background_samples.py   (can boxes.csv tu 02)
Ket qua: results/mmfw_stats/background.csv, background_summary.csv, samples/*.jpg
UOC LUONG THO: nen = vong quanh khung (khung mo rong 1x moi phia tru khung), phan loai theo mau HSV trung binh + do lech chuan xam.
"""
import csv, os, json, random, collections, colorsys
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EX = os.path.join(ROOT, "data", "mmfw-uav", "extracted")
RES = os.path.join(ROOT, "results", "mmfw_stats")
SETS = {"D": "Fixed-wing-UAV-D", "D'": "Fixed-wing-UAV-D'", "E": "Fixed-wing-UAV-E", "E'": "Fixed-wing-UAV-E'"}
DIRS = ["Top_Down", "Horizontal", "Bottom_Up"]
PER_SET_DIR = 100  # 4 bo x 100 = 400 anh / huong


def big_box(js):
    bs = json.loads(js) if js else []
    return max(bs, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])) if bs else None


def load_small(p, div=4):
    im = Image.open(p)
    W, H = im.size
    im.draft("RGB", (W // div, H // div))
    return im.convert("RGB"), W, H


def classify(a):
    s, d, stem, box = a
    im, W, H = load_small(os.path.join(EX, SETS[s], d, "Wide_Imgs", stem + ".jpg"))
    sx, sy = im.size[0] / W, im.size[1] / H
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    X0, Y0, X1, Y1 = [int(v) for v in (max(0, x0 - bw) * sx, max(0, y0 - bh) * sy, min(W, x1 + bw) * sx + 1, min(H, y1 + bh) * sy + 1)]
    arr = np.asarray(im, np.float32) / 255
    mask = np.zeros(arr.shape[:2], bool)
    mask[Y0:Y1, X0:X1] = True
    mask[int(y0 * sy):int(y1 * sy) + 1, int(x0 * sx):int(x1 * sx) + 1] = False
    px = arr[mask]
    if len(px) < 20:
        return None
    m = px.mean(0)
    h, sat, v = colorsys.rgb_to_hsv(*m)
    gray = px.mean(1) * 255
    std = float(gray.std())
    hue = h * 360
    if v > 0.45 and std < 20 and (sat < 0.2 or 180 <= hue <= 260):
        c = "troi"
    elif 50 <= hue <= 170 and sat >= 0.15:
        c = "cay_co"
    elif sat < 0.2:
        c = "xam_be_tong_cong_trinh"
    else:
        c = "dat_khac"
    return [s, d, stem, round(hue), round(sat, 3), round(v, 3), round(std, 1), c]


def sample_img(a):
    d, s, stem, t, box, k = a
    p = os.path.join(EX, SETS[s], d, t + "_Imgs", stem + ".jpg")
    im, W, H = load_small(p, 2)
    im = im.resize((960, int(960 * H / W)))
    sc = 960 / W
    dr = ImageDraw.Draw(im)
    x0, y0, x1, y1 = [v * sc for v in box]
    dr.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], outline=(255, 0, 0), width=2)
    dr.text((6, 6), f"{s} {d} {t} {stem} {W}x{H} box={box[2]-box[0]}x{box[3]-box[1]}px", fill=(255, 255, 0))
    out = os.path.join(RES, "samples", f"{d}_{t}_{k}_{s.replace(chr(39), 'p')}_{stem}.jpg")
    im.save(out, quality=85)
    return out


if __name__ == "__main__":
    rng = random.Random(0)
    os.makedirs(os.path.join(RES, "samples"), exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(RES, "boxes.csv"), encoding="utf-8")))
    wide = collections.defaultdict(list)
    zoom = {}
    for r in rows:
        b = big_box(r["boxes"])
        if r["type"] == "Wide" and b and r["has_jpg"] == "True":
            wide[(r["set"], r["dir"])].append((r["stem"], b))
        if r["type"] == "Zoom" and b:
            zoom[(r["set"], r["dir"], r["stem"])] = b
    jobs = []
    for (s, d), lst in sorted(wide.items()):
        for stem, b in rng.sample(lst, PER_SET_DIR):
            jobs.append((s, d, stem, b))
    sj = []
    for d in DIRS:
        for k, s in enumerate(["D", "E'"]):
            cands = [(st, b) for st, b in wide[(s, d)] if (s, d, st) in zoom]
            st, b = rng.choice(cands)
            sj.append((d, s, st, "Wide", b, k))
            sj.append((d, s, st, "Zoom", zoom[(s, d, st)], k))
    with Pool(8) as p:
        res = [r for r in p.map(classify, jobs, chunksize=8) if r]
        outs = p.map(sample_img, sj)
    with open(os.path.join(RES, "background.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["set", "dir", "stem", "hue_deg", "sat", "val", "gray_std", "class"])
        w.writerows(res)
    cnt = collections.Counter((r[1], r[7]) for r in res)
    tot = collections.Counter(r[1] for r in res)
    with open(os.path.join(RES, "background_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dir", "n_sampled", "class", "count", "pct"])
        for d in DIRS:
            for c in ["troi", "cay_co", "xam_be_tong_cong_trinh", "dat_khac"]:
                w.writerow([d, tot[d], c, cnt[(d, c)], round(100 * cnt[(d, c)] / tot[d], 1)])
        for s in SETS:
            ss = [r for r in res if r[0] == s]
            for c in ["troi", "cay_co", "xam_be_tong_cong_trinh", "dat_khac"]:
                n = sum(1 for r in ss if r[7] == c)
                w.writerow(["set:" + s, len(ss), c, n, round(100 * n / len(ss), 1)])
    print("sampled", len(res), "samples", len(outs))
