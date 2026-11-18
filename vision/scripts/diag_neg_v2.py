"""V2 chan doan: ti le anh am trong tap val ft2 (khong dung de huan luyen) bi model goi la drone (>=0.25), theo loai anh am, cho ft (cu) va ft2 (moi).
Chay: python -I diag_neg_v2.py -> results/v2/diag_neg.csv"""
import csv, collections
from ultralytics import YOLO
V = '/mnt/d/Personal/Drone-Tracking/vision'
man = [r for r in csv.DictReader(open(V + '/data/v2/manifest.csv')) if r['set'] == 'ft2/val' and r['n_box'] == '0']
rows = []
for tag, w in (('ft', V + '/weights/ft_v8n_best.pt'), ('ft2', V + '/weights/ft2_v8n_best.pt')):
    m = YOLO(w); cnt = collections.Counter(); fp = collections.Counter()
    files = [f"{V}/data/v2/ft2/val/images/{r['name']}.jpg" for r in man]
    for i in range(0, len(files), 16):
        for r0, res in zip(man[i:i + 16], m.predict(files[i:i + 16], imgsz=640, conf=0.25, device='cpu', verbose=False)):
            cnt[r0['kind']] += 1; fp[r0['kind']] += int(len(res.boxes) > 0)
    for k in sorted(cnt):
        rows.append(dict(model=tag, kind=k, n=cnt[k], called_drone_025=fp[k], rate=round(fp[k] / cnt[k], 3)))
with open(V + '/results/v2/diag_neg.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows:
    print(r)
