"""Kiem gia thuyet cho phep quet tong hop. Chay: python -I sweep_variants.py --tw 20 --imgsz 1280 --n 300
Bien the (cung 300 anh, muc tieu dau tien, nguong 0.25, ghep IoU>=0.5):
 V0 giao thuc V1 (thu nho ca anh, Lanczos, dat len khung xam 114)
 V1 nhu V0 nhung nen = lap bien (cv2.BORDER_REPLICATE) thay vi xam
 V2 nhu V0 nhung thu nho bang INTER_AREA
 V3 chi giu mieng vuong 8*tw px quanh muc tieu (da thu nho, nen lap bien) dat len khung xam: mat ngu canh + vien cung"""
import argparse, os, csv, random, hashlib
import numpy as np, cv2, torch
torch.set_num_threads(6)
from PIL import Image
from ultralytics import YOLO
V = '/mnt/d/Personal/Drone-Tracking/vision'; D = V + '/data/dut-yolo'
ap = argparse.ArgumentParser(); ap.add_argument('--tw', type=float, default=20); ap.add_argument('--imgsz', type=int, default=1280)
ap.add_argument('--n', type=int, default=300); ap.add_argument('--out', required=True); a = ap.parse_args()
model = YOLO(V + '/weights/ft_v8n_best.pt')
def iou1(p, g):
    ix = max(0.0, min(p[2], g[2]) - max(p[0], g[0])); iy = max(0.0, min(p[3], g[3]) - max(p[1], g[1])); i = ix*iy
    u = (p[2]-p[0])*(p[3]-p[1]) + (g[2]-g[0])*(g[3]-g[1]) - i; return i/u if u > 0 else 0.0
def lab(stem, W, H):
    out = []
    for ln in open(f'{D}/labels/test/{stem}.txt').read().split('\n'):
        if ln.strip():
            _, cx, cy, w, h = map(float, ln.split()); out.append([(cx-w/2)*W, (cy-h/2)*H, (cx+w/2)*W, (cy+h/2)*H])
    return out
stems = sorted(f[:-4] for f in os.listdir(D + '/images/test'))
random.Random(3).shuffle(stems)
pop = []
for s in stems:
    W, H = Image.open(f'{D}/images/test/{s}.jpg').size; g = lab(s, W, H)
    if g and g[0][2]-g[0][0] >= 40: pop.append(s)
    if len(pop) >= a.n: break
def detect(arr_rgb, gt_box):
    r = model.predict(arr_rgb[:, :, ::-1].copy(), imgsz=a.imgsz, conf=0.25, iou=0.7, max_det=100, device='cpu', verbose=False)[0]
    xy = r.boxes.xyxy.cpu().numpy(); return any(iou1(p, gt_box) >= 0.5 for p in xy), len(xy)
rows = []; summ = {}
for stem in pop:
    im = Image.open(f'{D}/images/test/{stem}.jpg').convert('RGB'); W, H = im.size
    g = lab(stem, W, H)[0]; s = a.tw / (g[2]-g[0])
    rng = random.Random(int(hashlib.md5(stem.encode()).hexdigest()[:8], 16))
    gs = [v*s for v in g]
    ox = rng.randint(int(np.ceil(gs[2])) - 640, int(gs[0])); oy = rng.randint(int(np.ceil(gs[3])) - 640, int(gs[1]))
    tb = [gs[0]-ox, gs[1]-oy, gs[2]-ox, gs[3]-oy]
    nw, nh = max(1, round(W*s)), max(1, round(H*s))
    res = {}
    ims = im.resize((nw, nh), Image.LANCZOS)
    cv = Image.new('RGB', (640, 640), (114, 114, 114)); cv.paste(ims, (-ox, -oy))
    res['V0_gray_lanczos'] = detect(np.asarray(cv), tb)
    # V1: lap bien
    arr = np.asarray(ims); T = np.zeros((640, 640, 3), np.uint8)
    x0, y0 = -ox, -oy
    big = cv2.copyMakeBorder(arr, 700, 700, 700, 700, cv2.BORDER_REPLICATE)
    T = big[700 + oy: 700 + oy + 640, 700 + ox: 700 + ox + 640]
    res['V1_replicate_lanczos'] = detect(T, tb)
    # V2: INTER_AREA + xam
    ims2 = cv2.resize(np.asarray(im), (nw, nh), interpolation=cv2.INTER_AREA)
    cv2_ = np.full((640, 640, 3), 114, np.uint8)
    xa, ya = max(0, -ox), max(0, -oy); xb, yb = min(640, nw - ox), min(640, nh - oy)
    if xb > xa and yb > ya: cv2_[ya:yb, xa:xb] = ims2[ya+oy:yb+oy, xa+ox:xb+ox]
    res['V2_gray_area'] = detect(cv2_, tb)
    # V3: bo tru "thu nho": cung muc tieu tw nhung cat vung goc quanh muc tieu (khong thu nho ca anh), dat len khung xam:
    #     chi mo phong KHUNG XAM + MAT NGU CANH, khong thu nho: lay mieng (tw*8 px canh) quanh muc tieu o ti le da thu nho
    pw = int(tw8 := a.tw * 8); cx = (tb[0]+tb[2])/2; cy = (tb[1]+tb[3])/2
    X0 = int(max(0, cx - pw/2)); Y0 = int(max(0, cy - pw/2)); X1 = int(min(640, cx + pw/2)); Y1 = int(min(640, cy + pw/2))
    gr = np.full((640, 640, 3), 114, np.uint8); src = np.asarray(cv)
    gr[Y0:Y1, X0:X1] = src[Y0:Y1, X0:X1] if False else T[Y0:Y1, X0:X1]
    res['V3_patch8x_on_gray'] = detect(gr, tb)
    for k, (hit, nd) in res.items(): rows.append([stem, k, int(hit), nd, f'{a.tw:g}', a.imgsz])
with open(a.out, 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['stem', 'variant', 'hit', 'n_dets', 'tw', 'imgsz']); w.writerows(rows)
for k in sorted({r[1] for r in rows}):
    h = [r[2] for r in rows if r[1] == k]; print(a.tw, a.imgsz, k, 'recall', round(sum(h)/len(h), 4), 'n', len(h))