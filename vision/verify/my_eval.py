"""Phep cham doc lap cua nguoi kiem (che do cat 640x640 o do phan giai goc, giong giao thuc V1 nhung ma ghep cap tu viet).
Chay: python -I my_eval.py --out results/verify/my_crop640 [--limit N]
Ghi <out>_img.csv (moi anh: ngt, tp/fp o 0.25 va 0.5) va <out>_gt.csv (moi GT: be rong goc, trung 0.25/0.5)."""
import argparse, os, csv, random, hashlib
import numpy as np, torch
torch.set_num_threads(6)
from PIL import Image
from ultralytics import YOLO
V = '/mnt/d/Personal/Drone-Tracking/vision'; D = V + '/data/dut-yolo'
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--limit', type=int, default=0)
a = ap.parse_args()
model = YOLO(V + '/weights/ft_v8n_best.pt')
stems = sorted(f[:-4] for f in os.listdir(D + '/images/test'))
if a.limit:
    random.Random(1).shuffle(stems); stems = sorted(stems[:a.limit])

def iou1(p, g):
    ix = max(0.0, min(p[2], g[2]) - max(p[0], g[0])); iy = max(0.0, min(p[3], g[3]) - max(p[1], g[1]))
    i = ix * iy; u = (p[2]-p[0])*(p[3]-p[1]) + (g[2]-g[0])*(g[3]-g[1]) - i
    return i / u if u > 0 else 0.0

img_rows = []; gt_rows = []
for stem in stems:
    im = Image.open(f'{D}/images/test/{stem}.jpg').convert('RGB'); W, H = im.size
    gts = []
    for ln in open(f'{D}/labels/test/{stem}.txt').read().split('\n'):
        if ln.strip():
            _, cx, cy, w, h = map(float, ln.split())
            gts.append([(cx-w/2)*W, (cy-h/2)*H, (cx+w/2)*W, (cy+h/2)*H])
    if min(W, H) < 640 or not gts: continue
    t = gts[0]
    if t[2]-t[0] > 640 or t[3]-t[1] > 640: continue
    lox = max(0, int(np.ceil(t[2])) - 640); hix = min(W-640, int(t[0])); loy = max(0, int(np.ceil(t[3])) - 640); hiy = min(H-640, int(t[1]))
    if lox > hix or loy > hiy: continue
    rng = random.Random(int(hashlib.md5(stem.encode()).hexdigest()[:8], 16))
    ox = rng.randint(lox, hix); oy = rng.randint(loy, hiy)
    crop = im.crop((ox, oy, ox+640, oy+640))
    full_in = []; partial = []
    for g in gts:
        b = [g[0]-ox, g[1]-oy, g[2]-ox, g[3]-oy]
        if b[0] >= 0 and b[1] >= 0 and b[2] <= 640 and b[3] <= 640: full_in.append(b)
        elif b[2] > 0 and b[3] > 0 and b[0] < 640 and b[1] < 640: partial.append([max(0,b[0]),max(0,b[1]),min(640,b[2]),min(640,b[3])])
    r = model.predict(np.asarray(crop)[:, :, ::-1], imgsz=640, conf=0.001, iou=0.7, max_det=100, device='cpu', verbose=False)[0]
    xy = r.boxes.xyxy.cpu().numpy(); cf = r.boxes.conf.cpu().numpy()
    row = [stem, len(full_in)]; hits = {0.25: [False]*len(full_in), 0.5: [False]*len(full_in)}
    for thr in (0.25, 0.5):
        keep = [i for i in np.argsort(-cf) if cf[i] >= thr]
        used = [False]*len(full_in); tp = fp = 0
        for i in keep:
            best = -1; bi = 0.0
            for k, g in enumerate(full_in):
                if used[k]: continue
                v = iou1(xy[i], g)
                if v > bi: bi, best = v, k
            if best >= 0 and bi >= 0.5:
                used[best] = True; tp += 1
            elif any(iou1(xy[i], p) >= 0.5 for p in partial): pass
            else: fp += 1
        hits[thr] = used; row += [tp, fp]
    img_rows.append(row)
    for k, g in enumerate(full_in):
        gt_rows.append([stem, k, f'{g[2]-g[0]:.2f}', int(hits[0.25][k]), int(hits[0.5][k])])
with open(a.out + '_img.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['stem', 'n_gt', 'tp25', 'fp25', 'tp50', 'fp50']); w.writerows(img_rows)
with open(a.out + '_gt.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['stem', 'k', 'w_native', 'hit25', 'hit50']); w.writerows(gt_rows)
print('n_img', len(img_rows), 'n_gt', len(gt_rows))