"""Muc b: kiem cheo dem ID bang ma rieng. Tu chay model.track (ultralytics, bytetrack.yaml mac dinh, conf 0.1 de cap low-score; track_high 0.25),
cach 'cat ca khung', 10 video; tu tinh so ID khac nhau, so lan doi ID (track conf cao nhat moi khung), so quang dut. So voi CSV cua nguoi lam (full, bytetrack, c0.25).
Chay: python -I crosscheck_b.py"""
import csv, os, sys
import numpy as np, torch, cv2
torch.set_num_threads(4); cv2.setNumThreads(1)
from ultralytics import YOLO
H = '/mnt/d/Personal/Drone-Tracking/vision'
V = '/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/video'
vids = [l.strip() for l in open(H + '/verify_b1/samples_a.txt') if l.strip()]
pick = [v for v in vids if 'DRONE' in v][:8] + [v for v in vids if 'AIRPLANE' in v][:2]
th = {r['video']: r for r in csv.DictReader(open(H + '/results/b1/trk_ft_full_bytetrack_c0.25.csv'))}
m = YOLO(H + '/weights/ft_v8n_best.pt')
L = ['| video | ID (ho) | ID (toi) | doi ID (ho) | doi ID (toi) | dut (ho) | dut (toi) |', '|---|---|---|---|---|---|---|']
for v in pick:
    ids_all = set(); prim = []; has = []
    for r in m.track(f'{V}/{v}.mp4', stream=True, tracker='bytetrack.yaml', conf=0.1, classes=[0], imgsz=640, device='cpu', verbose=False, max_det=20, persist=False):
        b = r.boxes
        if b is None or b.id is None or len(b) == 0:
            prim.append(None); has.append(False); continue
        ids = b.id.cpu().numpy().astype(int); cf = b.conf.cpu().numpy()
        ids_all.update(ids.tolist()); prim.append(int(ids[cf.argmax()])); has.append(True)
    p = [x for x in prim if x is not None]
    sw = sum(1 for i in range(1, len(p)) if p[i] != p[i - 1])
    idx = np.flatnonzero(has); gp = int((np.diff(idx) > 1).sum()) if len(idx) > 1 else 0
    t = th[v]
    L.append(f"| {v} | {t['n_ids']} | {len(ids_all)} | {t['id_switches']} | {sw} | {t['n_gaps']} | {gp} |")
    print(L[-1], flush=True)
open(H + '/results/verify_b1/b_crosscheck.md', 'w').write('\n'.join(L) + '\n')
