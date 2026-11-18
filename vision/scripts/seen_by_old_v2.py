"""V2: anh DUT trong test sach nao model cu (ft_v8n) da thay luc huan luyen (dut-train: ten cNNNNN_<stem>, fNNNNN_<stem>, nNNNNN_<stem> theo split train/val goc)?
Tach recall cua ft va ft2 tren DUT test sach thanh 'cu chua thay' / 'cu da thay'. Chay: python -I seen_by_old_v2.py -> results/v2/seen_by_old.csv"""
import csv, os, collections
import numpy as np
V = '/mnt/d/Personal/Drone-Tracking/vision'
seen = set()
for sp in ('train', 'val'):
    for f in os.listdir(f'{V}/data/dut-train/images/{sp}'):
        seen.add((sp, f[:-4].split('_', 1)[1]))
test = [(r['orig_split'], r['stem']) for r in csv.DictReader(open(V + '/data/v2/split_dut.csv')) if r['split'] == 'test']
name2seen = {f'dut_test_{i:05d}': (e in seen) for i, e in enumerate(test)}
print('anh DUT test sach', len(test), 'trong do cu da thay', sum(name2seen.values()))
out = []
for tag in ('ft', 'ft2'):
    rows = [r for r in csv.DictReader(open(f'{V}/results/v2/raw_clean_{tag}.csv')) if r['source'] == 'dut']
    for c in (0.25, 0.5):
        for grp, flag in (('cu_chua_thay', False), ('cu_da_thay', True)):
            for lo, hi, bn in ((20, 40, '20-40'), (40, 1e9, '>40'), (0, 1e9, 'tat ca')):
                s = [r for r in rows if name2seen[r['name']] == flag and lo <= float(r['w_gt_px']) < hi]
                out.append(dict(model=tag, conf=c, nhom=grp, width_bin=bn, n=len(s), recall=round(sum(float(r['conf_matched']) >= c for r in s) / max(len(s), 1), 4)))
with open(V + '/results/v2/seen_by_old.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
for r in out:
    print(r)
