"""Trich 120 khung theo samples_c.csv ra PNG goc (frames/<video>_f<k>.png). Doc tuan tu de chi so khung dung. Chay: python -I extract_frames.py"""
import csv, os, cv2
from collections import defaultdict
H = '/mnt/d/Personal/Drone-Tracking/vision'
V = '/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/video'
O = H + '/verify_b1/frames'
os.makedirs(O, exist_ok=True)
want = defaultdict(set)
for r in csv.DictReader(open(H + '/verify_b1/samples_c.csv')): want[r['video']].add(int(r['frame']))
for v, fs in sorted(want.items()):
    c = cv2.VideoCapture(f'{V}/{v}.mp4'); k = 0
    while k <= max(fs):
        ok, f = c.read()
        if not ok: break
        if k in fs: cv2.imwrite(f'{O}/{v}_f{k:04d}.png', f)
        k += 1
print(len(os.listdir(O)), 'png')
