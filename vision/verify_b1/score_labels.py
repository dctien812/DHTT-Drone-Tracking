"""Muc c: so nhan tay (labels_part*.csv) voi phat hien ft_v8n tren dung 120 khung PNG (ca khung 640, imgsz 640, conf>=0.1 roi loc 0.25/0.5).
Ghep cap: tam phat hien nam trong khung nhan noi rong 50% (moi canh x1.5 quanh tam) HOAC IoU>=0.3.
Chay: python -I score_labels.py"""
import csv, glob, math, os
import numpy as np
from ultralytics import YOLO
H = '/mnt/d/Personal/Drone-Tracking/vision'
F = H + '/verify_b1/frames'
lab = {}
for p in sorted(glob.glob(H + '/verify_b1/labels_part*.csv')):
    for r in csv.DictReader(open(p)):
        lab.setdefault((r['video'], int(r['frame'])), []).append(r)
assert len(lab) == 120, len(lab)
m = YOLO(H + '/weights/ft_v8n_best.pt')
def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'),) * 2
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0
def match(d, boxes):
    cx, cy = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
    for b in boxes:
        bx = [float(b['x1']), float(b['y1']), float(b['x2']), float(b['y2'])]
        w, h = (bx[2] - bx[0]) * 1.5, (bx[3] - bx[1]) * 1.5; mx, my = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        if abs(cx - mx) <= w / 2 and abs(cy - my) <= h / 2: return True
        if iou(d, bx) >= 0.3: return True
    return False
rows = []
for (v, f), rs in sorted(lab.items()):
    img = f'{F}/{v}_f{f:04d}.png'
    r = m.predict(img, imgsz=640, conf=0.1, classes=[0], device='cpu', verbose=False, max_det=20)[0].boxes
    dets = [(*x.tolist(), c) for x, c in zip(r.xyxy.cpu().numpy(), r.conf.cpu().numpy())]
    kind = rs[0]['label']; sure = min(int(x['sure']) for x in rs)
    rows.append((v, f, kind, sure, rs, dets))
out = ['# Cham nhan tay vs ft_v8n (ca khung 640x512, 1 khung/lan, khong tracker)', '', 'Nhan do chinh toi gan bang mat tren anh nen; sai so vai px, muc tieu 5-30 px. "chac"=sure 1.', '']
out += ['| tap | conf | n khung | recall (khung drone co >=1 det khop) | CI95 Wilson | precision det (det khop/tong det tren khung drone+none) | CI95 | khung drone co det khong khop |', '|---|---|---|---|---|---|---|---|']
csvr = []
for sub, flt in (('tat ca', lambda s: True), ('chac (sure=1)', lambda s: s == 1)):
    for c in (0.25, 0.5):
        dr = [x for x in rows if x[2] in ('drone', 'none') and flt(x[3])]
        pos = [x for x in dr if x[2] == 'drone']
        tp_fr = sum(any(match(d, x[4]) for d in x[5] if d[4] >= c) for x in pos)
        tot = tp = 0
        for x in dr:
            for d in x[5]:
                if d[4] >= c:
                    tot += 1; tp += match(d, x[4]) if x[2] == 'drone' else 0
        rl, rh = wilson(tp_fr, len(pos)); pl, ph = wilson(tp, tot)
        miss_fp = sum(1 for x in pos if any(d[4] >= c for d in x[5]) and not any(match(d, x[4]) for d in x[5] if d[4] >= c))
        out.append(f'| {sub} | {c} | {len(pos)} drone (+{len(dr)-len(pos)} none) | {tp_fr}/{len(pos)} = {100*tp_fr/len(pos):.1f}% | {100*rl:.1f}-{100*rh:.1f}% | {tp}/{tot} = {100*tp/max(tot,1):.1f}% | {100*pl:.1f}-{100*ph:.1f}% | {miss_fp} |')
out += ['', '| may bay | conf | khung may bay bi goi drone | CI95 |', '|---|---|---|---|']
ap = [x for x in rows if x[2] == 'airplane']
for c in (0.25, 0.5):
    k = sum(any(d[4] >= c for d in x[5]) for x in ap); lo, hi = wilson(k, len(ap))
    out.append(f'| {len(ap)} khung | {c} | {k}/{len(ap)} = {100*k/len(ap):.1f}% | {100*lo:.1f}-{100*hi:.1f}% |')
out += ['', f'So khung khong chac (sure=0): {sum(1 for x in rows if x[3]==0)}/120 (drone: {sum(1 for x in rows if x[3]==0 and x[2]!="airplane")})', '']
out += ['## Chi tiet khung drone bi bo sot hoac det sai (conf 0.25)', '| video | khung | chac | nhan (x1,y1,x2,y2) | det conf>=0.25 |', '|---|---|---|---|---|']
for v, f, kind, sure, rs, dets in rows:
    if kind == 'airplane': continue
    ds = [d for d in dets if d[4] >= 0.25]
    ok = any(match(d, rs) for d in ds) if kind == 'drone' else not ds
    if not ok:
        out.append(f"| {v} | {f} | {sure} | {[(r['x1'],r['y1'],r['x2'],r['y2']) for r in rs]} | {[tuple(round(x) for x in d[:4])+(round(d[4],2),) for d in ds]} |")
open(H + '/results/verify_b1/c_score.md', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
