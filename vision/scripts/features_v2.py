"""V2 buoc 1: dac trung xam 32x32 (cung cach verify/leak_features.py) cho DUT (3 split) va Det-Fly + thong ke Det-Fly.
Doc anh/nhan nhu du lieu (khong chay gi trong goi du lieu). Ghi data/v2/feat_dut.npz, feat_detfly.npz, results/v2/detfly_stats.csv
Chay: python -I features_v2.py
"""
import os, csv, collections
import xml.etree.ElementTree as ET
from multiprocessing import Pool
import cv2, numpy as np

V = '/mnt/d/Personal/Drone-Tracking/vision'
OUT = V + '/data/v2'
os.makedirs(OUT, exist_ok=True); os.makedirs(V + '/results/v2', exist_ok=True)
cv2.setNumThreads(1)


def feat(p):
    g = cv2.imread(p, cv2.IMREAD_REDUCED_GRAYSCALE_4)
    if g is None:
        return None
    return cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).ravel().astype(np.float32)


def dut():
    items = []
    for sp in ('train', 'val', 'test'):
        for f in sorted(os.listdir(f'{V}/data/dut-yolo/images/{sp}')):
            items.append((sp, f[:-4], f'{V}/data/dut-yolo/images/{sp}/{f}'))
    with Pool(8) as P:
        F = P.map(feat, [i[2] for i in items], chunksize=32)
    assert all(x is not None for x in F)
    np.savez(f'{OUT}/feat_dut.npz', split=np.array([i[0] for i in items]), stem=np.array([i[1] for i in items]), F=np.stack(F))
    print('dut', len(items), flush=True)


def parse(p):
    r = ET.parse(p).getroot()
    W = int(r.find('size/width').text); H = int(r.find('size/height').text)
    bs = []
    for o in r.findall('object'):
        b = o.find('bndbox')
        bs.append((o.find('name').text, *[float(b.find(k).text) for k in ('xmin', 'ymin', 'xmax', 'ymax')]))
    return W, H, bs


def detfly():
    D = V + '/data/det-fly'
    xs = []
    for sc in sorted(os.listdir(D + '/Annotations')):
        for f in sorted(os.listdir(f'{D}/Annotations/{sc}')):
            xs.append((sc, f[:-4]))
    have = {(sc, f[:-4]) for sc in os.listdir(D + '/JPEGImages') for f in os.listdir(f'{D}/JPEGImages/{sc}')}
    xml_set = set(xs)
    print('xml', len(xs), 'jpg', len(have), 'xml co jpg', len(xml_set & have), 'xml khong jpg', len(xml_set - have), 'jpg khong xml', len(have - xml_set))
    items = [x for x in xs if x in have]
    with Pool(8) as P:
        F = P.map(feat, [f'{D}/JPEGImages/{a}/{b}.jpg' for a, b in items], chunksize=16)
    ok = [i for i, x in enumerate(F) if x is not None]
    print('doc duoc', len(ok), '/', len(items))
    items = [items[i] for i in ok]; F = [F[i] for i in ok]
    np.savez(f'{OUT}/feat_detfly.npz', scene=np.array([i[0] for i in items]), stem=np.array([i[1] for i in items]), F=np.stack(F))
    names = collections.Counter(); sizes = collections.Counter(); nobj = collections.Counter(); rows = []
    for sc, st in items:
        W, H, bs = parse(f'{D}/Annotations/{sc}/{st}.xml')
        sizes[(W, H)] += 1; nobj[len(bs)] += 1
        for n, x1, y1, x2, y2 in bs:
            names[n] += 1
        rows.append((sc, st, W, H, len(bs), *(bs[0][1:] if bs else ('', '', '', ''))))
    with open(V + '/results/v2/detfly_stats.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['scene_dir', 'stem', 'W', 'H', 'n_obj', 'x1', 'y1', 'x2', 'y2']); w.writerows(rows)
    print('class names', dict(names)); print('sizes', dict(sizes)); print('n_obj per image', dict(nobj))
    ws = np.array([r[7] - r[5] for r in rows if r[4]]);
    for sc in sorted({r[0] for r in rows}):
        w_ = np.array([r[7] - r[5] for r in rows if r[0] == sc and r[4]])
        print(sc, len(w_), 'w px pctl 5/25/50/75/95', np.percentile(w_, [5, 25, 50, 75, 95]).round(0))
    print('bins <10,10-20,20-40,>40:', [int(((ws >= a) & (ws < b)).sum()) for a, b in ((0, 10), (10, 20), (20, 40), (40, 1e9))])


if __name__ == '__main__':
    dut(); detfly()
