"""Muc d: trich 5 khung tu video ket qua cua nguoi lam (d_frames/). Kem 2 phep thu am tinh (negative control) cho compare_a va score_labels.
Chay: python -I extract_d_and_controls.py"""
import os, csv, cv2, subprocess, sys
H = '/mnt/d/Personal/Drone-Tracking/vision'
O = H + '/verify_b1/d_frames'
os.makedirs(O, exist_ok=True)
R = H + '/runs/b1_videos/best_ft_crop'
for v, k in (('V_DRONE_075', 60), ('V_DRONE_075', 250), ('V_DRONE_021', 150), ('V_DRONE_100', 90), ('V_DRONE_106', 200)):
    c = cv2.VideoCapture(f'{R}/{v}_tracked.mp4'); c.set(cv2.CAP_PROP_POS_FRAMES, k); ok, f = c.read()
    print(v, k, ok, None if not ok else f.shape)
    if ok: cv2.imwrite(f'{O}/{v}_k{k}.png', f)
# control 1: so CSV c0.5 (cua toi) voi CSV c0.25 (cua ho) -> phai lech
import numpy as np
def load(p): return {r['video']: r for r in csv.DictReader(open(p))}
a = load(H + '/results/b1/trk_ft_full_bytetrack_c0.25.csv'); b = load(H + '/results/verify_b1/trk_ft_full_bytetrack_c0.5.csv')
d = [v for v in b if v in a and a[v]['det_frames'] != b[v]['det_frames']]
print('CONTROL1 so video lech khi so sai conf:', len(d), '/', len(b))
# control 2: dich nhan 150 px -> recall phai tut
src = open(H + '/verify_b1/score_labels.py').read()
src = src.replace("lab.setdefault((r['video'], int(r['frame'])), []).append(r)", "r['x1'] = float(r['x1']) + 150; r['x2'] = float(r['x2']) + 150; lab.setdefault((r['video'], int(r['frame'])), []).append(r)")
src = src.replace("c_score.md", "control_shifted_labels.md")
exec(compile(src, 'ctrl', 'exec'))
