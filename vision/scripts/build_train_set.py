"""Tao tap huan luyen tinh chinh tu split train/val cua DUT (KHONG dung test).
 - crop: cat 640x640 o do phan giai goc quanh 1 muc tieu, lech tam ngau nhien (giong cach dung that).
 - full: anh nguyen thu nho ve canh dai 640 (giu ti le).
 - neg : crop 640x640 khong chua muc tieu nao (giam bao dong gia).
Dau ra: data/dut-train/{images,labels}/{train,val} + dut-train.yaml. Chay: python -I build_train_set.py
"""
import os, random, shutil
from PIL import Image

ROOT = '/mnt/d/Personal/Drone-Tracking/vision/data'
SRC = ROOT + '/dut-yolo'
DST = ROOT + '/dut-train'
PLAN = {'train': dict(crop=1400, full=700, neg=150, seed=11), 'val': dict(crop=150, full=100, neg=30, seed=12)}


def labels(split, stem, W, H):
    out = []
    for ln in open(f'{SRC}/labels/{split}/{stem}.txt').read().split('\n'):
        if ln.strip():
            _, cx, cy, w, h = map(float, ln.split())
            out.append(((cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H))
    return out


def write(split, name, im, boxes):
    im.save(f'{DST}/images/{split}/{name}.jpg', quality=95)
    w, h = im.size
    with open(f'{DST}/labels/{split}/{name}.txt', 'w') as f:
        for x1, y1, x2, y2 in boxes:
            f.write(f'0 {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}\n')


if os.path.isdir(DST):
    shutil.rmtree(DST)
for split, p in PLAN.items():
    os.makedirs(f'{DST}/images/{split}'); os.makedirs(f'{DST}/labels/{split}')
    rng = random.Random(p['seed'])
    stems = sorted(f[:-4] for f in os.listdir(f'{SRC}/images/{split}'))
    rng.shuffle(stems)
    nc = nf = nn = 0
    for stem in stems:
        if nc >= p['crop'] and nf >= p['full'] and nn >= p['neg']:
            break
        im = Image.open(f'{SRC}/images/{split}/{stem}.jpg').convert('RGB'); W, H = im.size
        gt = labels(split, stem, W, H)
        if not gt:
            continue
        if nc < p['crop'] and min(W, H) >= 640:
            t = gt[0]
            lo_x = max(0, int(t[2]) + 1 - 640); hi_x = min(W - 640, int(t[0]))
            lo_y = max(0, int(t[3]) + 1 - 640); hi_y = min(H - 640, int(t[1]))
            if lo_x <= hi_x and lo_y <= hi_y:
                ox = rng.randint(lo_x, hi_x); oy = rng.randint(lo_y, hi_y)
                bx = [(a - ox, b - oy, c - ox, d - oy) for a, b, c, d in gt]
                bx = [b for b in bx if b[0] >= 0 and b[1] >= 0 and b[2] <= 640 and b[3] <= 640]
                write(split, f'c{nc:05d}_{stem}', im.crop((ox, oy, ox + 640, oy + 640)), bx)
                nc += 1
                continue
        if nn < p['neg'] and min(W, H) >= 640:
            for _ in range(10):
                ox = rng.randint(0, W - 640); oy = rng.randint(0, H - 640)
                if all(b[2] < ox or b[0] > ox + 640 or b[3] < oy or b[1] > oy + 640 for b in gt):
                    write(split, f'n{nn:05d}_{stem}', im.crop((ox, oy, ox + 640, oy + 640)), [])
                    nn += 1
                    break
            continue
        if nf < p['full']:
            s = 640 / max(W, H)
            write(split, f'f{nf:05d}_{stem}', im.resize((round(W * s), round(H * s)), Image.LANCZOS),
                  [tuple(v * s for v in b) for b in gt])
            nf += 1
    print(split, 'crop', nc, 'full', nf, 'neg', nn)
with open(f'{ROOT}/dut-train.yaml', 'w') as f:
    f.write(f'path: {DST}\ntrain: images/train\nval: images/val\nnames:\n  0: drone\n')
