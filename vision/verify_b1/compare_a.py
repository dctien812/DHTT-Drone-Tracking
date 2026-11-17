"""Muc a: so CSV tu chay lai (results/verify_b1) voi CSV cua nguoi lam (results/b1) tren CUNG cac video. Chay: python -I compare_a.py"""
import csv, os
import numpy as np
H = '/mnt/d/Personal/Drone-Tracking/vision/results'
vids = [l.strip() for l in open('/mnt/d/Personal/Drone-Tracking/vision/verify_b1/samples_a.txt') if l.strip()]
def load(p):
    return {r['video']: {k: (v if k in ('video', 'tracker') else float(v)) for k, v in r.items()} for r in csv.DictReader(open(p))}
def agg(rs, air):
    fr = sum(r['frames'] for r in rs)
    if air: return dict(ap_fp_frames=sum(r['det_frames'] for r in rs), ap_frames=fr)
    return dict(n=len(rs), det_rate=100 * sum(r['det_frames'] for r in rs) / fr, one=100 * sum(r['one_target_rate'] * r['frames'] for r in rs) / fr,
                ids_mean=np.mean([r['n_ids'] for r in rs]), vid_1id=100 * np.mean([r['n_ids'] == 1 for r in rs]),
                sw_mean=np.mean([r['id_switches'] for r in rs]), gaps_mean=np.mean([r['n_gaps'] for r in rs]))
L = ['| cach | conf | chi so | da bao (cung video) | do lai | chenh |', '|---|---|---|---|---|---|']
maxd = 0
for mode in ('full', 'crop'):
    for c in ('0.25', '0.5'):
        n = f'trk_ft_{mode}_bytetrack_c{c}.csv'
        if not os.path.exists(f'{H}/verify_b1/{n}'): continue
        th = load(f'{H}/b1/{n}'); me = load(f'{H}/verify_b1/{n}')
        for air in (False, True):
            vs = [v for v in vids if v in me and v in th and v.startswith('V_AIRPLANE') == air]
            a, b = agg([th[v] for v in vs], air), agg([me[v] for v in vs], air)
            for k in a:
                L.append(f'| {mode} | {c} | {"may bay " if air else "drone "}{k} | {a[k]:.3f} | {b[k]:.3f} | {b[k]-a[k]:+.3f} |')
        for v in vids:
            if v in me and v in th:
                for k in ('det_frames', 'n_ids', 'id_switches', 'n_gaps', 'one_target_rate', 'max_gap_frames'):
                    d = abs(me[v][k] - th[v][k])
                    if d > 0: L.append(f'| {mode} | {c} | LECH {v} {k} | {th[v][k]} | {me[v][k]} | {me[v][k]-th[v][k]:+g} |')
                    maxd = max(maxd, d)
L.append(f'\nmax |chenh| tren tung video, 6 chi so: {maxd}')
open('/mnt/d/Personal/Drone-Tracking/vision/results/verify_b1/a_compare.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
