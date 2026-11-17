"""Chon mau ngau nhien (co seed) cho kiem B1. Chay: python -I select_samples.py
SEED_A=20261117 -> 20 video drone cho tai lap (muc a, b); SEED_C=7001 -> 50 video drone x 2 khung cho gan nhan tay (muc c).
Ghi: samples_a.txt (ten video), samples_c.csv (video,frame)."""
import csv, random, os
H = '/mnt/d/Personal/Drone-Tracking/vision'
O = H + '/verify_b1'
rows = list(csv.DictReader(open(H + '/results/b1/catalog.csv')))
drone = sorted(r['video'][:-4] for r in rows if r['video'].startswith('V_DRONE'))
air = sorted(r['video'][:-4] for r in rows if r['video'].startswith('V_AIRPLANE'))
nfr = {r['video'][:-4]: int(r['frames_read']) for r in rows}
a = sorted(random.Random(20261117).sample(drone, 20))
open(O + '/samples_a.txt', 'w').write('\n'.join(a + air) + '\n')
rc = random.Random(7001)
c = sorted(rc.sample(drone, 50))
out = []
for v in c:
    for f in sorted(rc.sample(range(nfr[v]), 2)): out.append((v, f))
for v in air:
    for f in sorted(rc.sample(range(nfr[v]), 5)): out.append((v, f))
with open(O + '/samples_c.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['video', 'frame']); w.writerows(out)
print(len(a), 'a;', len(out), 'c')
