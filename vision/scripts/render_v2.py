"""V2: ve khung bao model moi (conf>=0.25) len anh de xem bang mat. Luu runs/v2_vis/{drone_small,airplane}.jpg (luoi anh cat phong 3x quanh vung chu y;
xanh la=GT/nhan tay, do=phat hien kem conf). Chay: python -I render_v2.py WEIGHTS"""
import sys, csv, glob, os
import numpy as np, cv2
from ultralytics import YOLO
V = '/mnt/d/Personal/Drone-Tracking/vision'
m = YOLO(sys.argv[1]); os.makedirs(V + '/runs/v2_vis', exist_ok=True)


def draw(path, gts, title, center):
    im = cv2.imread(path); H, W = im.shape[:2]
    r = m.predict(path, imgsz=640, conf=0.25, classes=[0], device='cpu', verbose=False)[0].boxes
    dets = list(zip(r.xyxy.cpu().numpy(), r.conf.cpu().numpy()))
    cx, cy = center; x0 = int(min(max(cx - 80, 0), W - 160)); y0 = int(min(max(cy - 80, 0), H - 160))
    cr = im[y0:y0 + 160, x0:x0 + 160].copy(); cr = cv2.resize(cr, (480, 480), interpolation=cv2.INTER_NEAREST)
    for g in gts:
        cv2.rectangle(cr, (int((g[0] - x0) * 3), int((g[1] - y0) * 3)), (int((g[2] - x0) * 3), int((g[3] - y0) * 3)), (0, 255, 0), 1)
    for b, c in dets:
        cv2.rectangle(cr, (int((b[0] - x0) * 3), int((b[1] - y0) * 3)), (int((b[2] - x0) * 3), int((b[3] - y0) * 3)), (0, 0, 255), 1)
        cv2.putText(cr, f'{c:.2f}', (int((b[0] - x0) * 3), max(12, int((b[1] - y0) * 3) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    cv2.putText(cr, title, (4, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
    return cr, len(dets)


T = V + '/data/v2/test_clean'
raw = list(csv.DictReader(open(V + '/results/v2/raw_clean_ft2.csv')))
small = [r for r in raw if r['source'] == 'detfly' and 10 <= float(r['w_gt_px']) < 20][:2] + [r for r in raw if r['source'] == 'dut' and 20 <= float(r['w_gt_px']) < 40][:1]
tiles = []; info = []
for r in small:
    n = r['name']; l = list(map(float, open(f'{T}/labels/{n}.txt').read().split()[1:]))
    g = [(l[0] - l[2] / 2) * 640, (l[1] - l[3] / 2) * 640, (l[0] + l[2] / 2) * 640, (l[1] + l[3] / 2) * 640]
    t, nd = draw(f'{T}/images/{n}.jpg', [g], f"{n} w={float(r['w_gt_px']):.0f}px", ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)); tiles.append(t); info.append((n, nd))
cv2.imwrite(V + '/runs/v2_vis/drone_small.jpg', np.hstack(tiles)); print('drone_small', info)
tiles = []; info = []
lab = list(csv.DictReader(open(V + '/verify_b1/labels_part1_airplane.csv')))
for r in [lab[0], lab[8], lab[16]]:
    g = [float(r[k]) for k in ('x1', 'y1', 'x2', 'y2')]
    t, nd = draw(f"{V}/verify_b1/frames/{r['video']}_f{int(r['frame']):04d}.png", [g], f"{r['video']} f{r['frame']} (may bay)", ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)); tiles.append(t); info.append((r['video'], r['frame'], nd))
cv2.imwrite(V + '/runs/v2_vis/airplane.jpg', np.hstack(tiles)); print('airplane', info)
lab = list(csv.DictReader(open(V + '/verify_b1/labels_part2_drone.csv')))
tiles = []; info = []
for r in lab[::len(lab) // 3][:3]:
    g = [float(r[k]) for k in ('x1', 'y1', 'x2', 'y2')]
    t, nd = draw(f"{V}/verify_b1/frames/{r['video']}_f{int(r['frame']):04d}.png", [g], f"{r['video']} f{r['frame']} (drone, nhan tay)", ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)); tiles.append(t); info.append((r['video'], r['frame'], nd))
cv2.imwrite(V + '/runs/v2_vis/drone_hand.jpg', np.hstack(tiles)); print('drone_hand', info)
