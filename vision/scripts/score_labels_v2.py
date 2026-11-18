"""V2: cham 120 khung nhan tay (verify_b1/labels_part*.csv, verify_b1/frames/*.png) cho mot model bat ky. Cach ghep/cham = score_labels.py (khong doi):
ca khung 640x512, imgsz 640, conf>=0.1 roi loc 0.25/0.5; ghep neu tam det trong khung nhan noi 50% hoac IoU>=0.3.
Chay: python -I score_labels_v2.py TAG WEIGHTS  -> results/v2/hand120_<TAG>.csv (+ in ra man hinh)"""
import csv, glob, sys
from ultralytics import YOLO
H = '/mnt/d/Personal/Drone-Tracking/vision'
F = H + '/verify_b1/frames'
tag, weights = sys.argv[1], sys.argv[2]
lab = {}
for p in sorted(glob.glob(H + '/verify_b1/labels_part*.csv')):
    for r in csv.DictReader(open(p)):
        lab.setdefault((r['video'], int(r['frame'])), []).append(r)
assert len(lab) == 120, len(lab)
m = YOLO(weights)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0


def match(d, boxes):
    cx, cy = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
    for b in boxes:
        bx = [float(b['x1']), float(b['y1']), float(b['x2']), float(b['y2'])]
        w, h = (bx[2] - bx[0]) * 1.5, (bx[3] - bx[1]) * 1.5; mx, my = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        if abs(cx - mx) <= w / 2 and abs(cy - my) <= h / 2:
            return True
        if iou(d, bx) >= 0.3:
            return True
    return False


rows = []
for (v, f), rs in sorted(lab.items()):
    r = m.predict(f'{F}/{v}_f{f:04d}.png', imgsz=640, conf=0.1, classes=[0], device='cpu', verbose=False, max_det=20)[0].boxes
    dets = [(*x.tolist(), c) for x, c in zip(r.xyxy.cpu().numpy(), r.conf.cpu().numpy())]
    rows.append((v, f, rs[0]['label'], min(int(x['sure']) for x in rs), rs, dets))
out = []
for c in (0.25, 0.5):
    dr = [x for x in rows if x[2] in ('drone', 'none')]; pos = [x for x in dr if x[2] == 'drone']
    tp_fr = sum(any(match(d, x[4]) for d in x[5] if d[4] >= c) for x in pos)
    tot = tp = 0
    for x in dr:
        for d in x[5]:
            if d[4] >= c:
                tot += 1; tp += match(d, x[4]) if x[2] == 'drone' else 0
    ap = [x for x in rows if x[2] == 'airplane']; k = sum(any(d[4] >= c for d in x[5]) for x in ap)
    sure = [x for x in pos if x[3] == 1]; ts = sum(any(match(d, x[4]) for d in x[5] if d[4] >= c) for x in sure)
    out.append(dict(tag=tag, conf=c, drone_frames=len(pos), drone_caught=tp_fr, dets_total=tot, dets_matched=tp, precision=round(tp / max(tot, 1), 4),
                    airplane_frames=len(ap), airplane_called_drone=k, sure_drone_frames=len(sure), sure_caught=ts))
with open(f'{H}/results/v2/hand120_{tag}.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
for o in out:
    print(o)
