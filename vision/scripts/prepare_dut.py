"""Giai nen DUT Anti-UAV (chi doc anh/xml, khong chay gi trong goi) va doi nhan VOC -> YOLO (1 lop: drone).
Dau ra: data/dut-yolo/{images,labels}/{train,val,test}/ + stats.csv (kich thuoc anh, so box, bbox px goc).
Chay: python -I prepare_dut.py
"""
import zipfile, os, csv, collections
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = '/mnt/d/Personal/Drone-Tracking/vision/data'
SRC = ROOT + '/dut-anti-uav'
DST = ROOT + '/dut-yolo'
rows = []
names = collections.Counter()
for split in ('train', 'val', 'test'):
    os.makedirs(f'{DST}/images/{split}', exist_ok=True)
    os.makedirs(f'{DST}/labels/{split}', exist_ok=True)
    z = zipfile.ZipFile(f'{SRC}/{split}.zip')
    for n in z.namelist():
        if n.endswith('/'):
            continue
        base = os.path.basename(n)
        stem, ext = os.path.splitext(base)
        if n.startswith(f'{split}/img/') and ext.lower() == '.jpg':
            with open(f'{DST}/images/{split}/{stem}.jpg', 'wb') as f:
                f.write(z.read(n))
        elif n.startswith(f'{split}/xml/') and ext.lower() == '.xml':
            root = ET.fromstring(z.read(n))
            W = int(root.find('size/width').text); H = int(root.find('size/height').text)
            lines = []
            for o in root.findall('object'):
                names[o.find('name').text] += 1
                b = o.find('bndbox')
                x1, y1, x2, y2 = [float(b.find(k).text) for k in ('xmin', 'ymin', 'xmax', 'ymax')]
                lines.append(f'0 {(x1+x2)/2/W:.6f} {(y1+y2)/2/H:.6f} {(x2-x1)/W:.6f} {(y2-y1)/H:.6f}')
                rows.append((split, stem, W, H, x1, y1, x2, y2))
            with open(f'{DST}/labels/{split}/{stem}.txt', 'w') as f:
                f.write('\n'.join(lines) + ('\n' if lines else ''))
# kiem tra kich thuoc that cua anh va kenh mau
sizes = collections.Counter(); modes = collections.Counter(); bad = 0
for split in ('train', 'val', 'test'):
    d = f'{DST}/images/{split}'
    fs = sorted(os.listdir(d))
    for i, fn in enumerate(fs):
        if i % 50: continue
        im = Image.open(f'{d}/{fn}'); sizes[im.size] += 1; modes[im.mode] += 1
with open(f'{DST}/stats.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['split', 'stem', 'W', 'H', 'x1', 'y1', 'x2', 'y2']); w.writerows(rows)
print('class names', dict(names)); print('sampled sizes', dict(sizes)); print('modes', dict(modes))
for s in ('train', 'val', 'test'):
    print(s, len(os.listdir(f'{DST}/images/{s}')), 'imgs', len(os.listdir(f'{DST}/labels/{s}')), 'labels', sum(1 for r in rows if r[0] == s), 'boxes')
