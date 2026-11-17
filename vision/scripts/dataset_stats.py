"""Thong ke tap DUT: so anh/box theo split, phan bo be rong muc tieu (px goc va px sau khi dua ve imgsz 640/1280)."""
import csv, collections
import numpy as np
ROOT = '/mnt/d/Personal/Drone-Tracking/vision'
rows = list(csv.DictReader(open(ROOT + '/data/dut-yolo/stats.csv')))
BINS = [(0, 10, '<10'), (10, 20, '10-20'), (20, 40, '20-40'), (40, 1e9, '>40')]
out = [['split', 'basis', 'n_box'] + [b[2] for b in BINS] + ['p10', 'p50', 'p90', 'img_sizes_top']]
for split in ('train', 'val', 'test'):
    R = [r for r in rows if r['split'] == split]
    sz = collections.Counter((int(r['W']), int(r['H'])) for r in R)
    top = ';'.join(f'{w}x{h}:{n}' for (w, h), n in sz.most_common(3))
    for basis, f in (('native', lambda r: 1.0), ('imgsz640', lambda r: 640 / max(int(r['W']), int(r['H']))),
                     ('imgsz1280', lambda r: 1280 / max(int(r['W']), int(r['H'])))):
        w = np.array([(float(r['x2']) - float(r['x1'])) * f(r) for r in R])
        cnt = [int(((w >= a) & (w < b)).sum()) for a, b, _ in BINS]
        out.append([split, basis, len(w)] + cnt + [f'{np.percentile(w, q):.1f}' for q in (10, 50, 90)] + [top])
with open(ROOT + '/results/dataset_stats.csv', 'w', newline='') as f:
    csv.writer(f).writerows(out)
for r in out:
    print(r)
