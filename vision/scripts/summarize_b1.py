"""B1: gop CSV theo video -> bang tong hop (results/b1/summary_b1.csv + B1_TABLES.md). Chay: python -I summarize_b1.py"""
import csv, glob, os, re
import numpy as np
R = '/mnt/d/Personal/Drone-Tracking/vision/results/b1'


def load(p):
    with open(p) as f:
        return [{k: (v if k in ('video', 'tracker') else float(v)) for k, v in r.items()} for r in csv.DictReader(f)]


def agg_drone(rs):
    fr = sum(r['frames'] for r in rs)
    wmax = max(r['max_gap_frames'] for r in rs)
    return dict(n_vid=len(rs), frames=int(fr),
                det_rate=sum(r['det_frames'] for r in rs) / fr,
                one_rate=sum(r['one_target_rate'] * r['frames'] for r in rs) / fr,
                ids_med=float(np.median([r['n_ids'] for r in rs])), ids_mean=float(np.mean([r['n_ids'] for r in rs])),
                vid_1id=float(np.mean([r['n_ids'] == 1 for r in rs])),
                sw_mean=float(np.mean([r['id_switches'] for r in rs])), gaps_mean=float(np.mean([r['n_gaps'] for r in rs])),
                maxgap_med_s=float(np.median([r['max_gap_s'] for r in rs])), maxgap_max_s=float(max(r['max_gap_s'] for r in rs)),
                w_med=float(np.median([r['w_median'] for r in rs if r['w_median'] > 0] or [0])),
                vid_zero=int(sum(r['det_frames'] == 0 for r in rs)))


rows = []
for p in sorted(glob.glob(R + '/trk_*.csv')):
    m = re.match(r'trk_(.+)_(full|crop)_(bytetrack|botsort)_c([\d.]+)\.csv', os.path.basename(p))
    tag, mode, trk, conf = m.groups()
    rs = load(p)
    dr = [r for r in rs if r['video'].startswith('V_DRONE')]
    ap = [r for r in rs if r['video'].startswith('V_AIRPLANE')]
    mv = [r for r in rs if r['video'] == 'VIDEO']
    d = agg_drone(dr); fr = sum(r['frames'] for r in ap)
    row = dict(tag=tag, mode=mode, tracker=trk, conf=conf, **{k: round(v, 4) for k, v in d.items()})
    row.update(ap_frames=int(fr), ap_fp_frames=int(sum(r['det_frames'] for r in ap)), ap_fp_per100=round(100 * sum(r['det_frames'] for r in ap) / fr, 2),
               ap_long_tracks=int(sum(r['long_tracks_0p5s'] for r in ap)), ap_ids=int(sum(r['n_ids'] for r in ap)))
    if mv: row.update(mov_det=mv[0]['det_rate'], mov_one=mv[0]['one_target_rate'], mov_ids=int(mv[0]['n_ids']), mov_sw=int(mv[0]['id_switches']))
    # toc do (video drone): trung vi cua trung vi moi video, p95 gop
    row.update(ms_det_med=round(float(np.median([r['ms_det_med'] for r in dr])), 1), ms_tot_med=round(float(np.median([r['ms_tot_med'] for r in dr])), 1),
               ms_tot_p95=round(float(np.median([r['ms_tot_p95'] for r in dr])), 1), fb_rate=round(float(np.mean([r['fb_rate'] for r in dr])), 3))
    rows.append(row)
with open(R + '/summary_b1.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 999)); w.writeheader(); w.writerows(rows)

L = ['| model | cach | tracker | conf | khung co det | dung 1 muc tieu | ID/video (TV) | video 1 ID | doi ID/video | dut/video | dut dai nhat TV/max (s) | be rong TV (px) | video 0 det |', '|' + '---|' * 13]
for r in rows:
    L.append(f"| {r['tag']} | {r['mode']} | {r['tracker']} | {r['conf']} | {r['det_rate']*100:.1f}% | {r['one_rate']*100:.1f}% | {r['ids_med']:.0f} ({r['ids_mean']:.1f} tb) | {r['vid_1id']*100:.0f}% | {r['sw_mean']:.1f} | {r['gaps_mean']:.1f} | {r['maxgap_med_s']:.2f}/{r['maxgap_max_s']:.2f} | {r['w_med']:.1f} | {r['vid_zero']} |")
L += ['', '| model | cach | tracker | conf | khung may bay co det | /100 khung | track gia >0.5s | tong ID gia | ms det TV | ms tong TV | ms tong p95 | ti le quay ve quet ca khung |', '|' + '---|' * 12]
for r in rows:
    L.append(f"| {r['tag']} | {r['mode']} | {r['tracker']} | {r['conf']} | {r['ap_fp_frames']}/{r['ap_frames']} | {r['ap_fp_per100']} | {r['ap_long_tracks']} | {r['ap_ids']} | {r['ms_det_med']} | {r['ms_tot_med']} | {r['ms_tot_p95']} | {r['fb_rate']} |")
b = []
for p in sorted(glob.glob(R + '/bench_bench8_*.csv')):
    rs = load(p); tag = re.search(r'bench8_(\w+)\.csv', p).group(1)
    b.append(f"| {tag} | {len(rs)} | {np.median([r['ms_det_med'] for r in rs]):.1f} | {np.median([r['ms_trk_med'] for r in rs]):.2f} | {np.median([r['ms_tot_med'] for r in rs]):.1f} | {np.median([r['ms_tot_p95'] for r in rs]):.1f} | {1000/np.median([r['ms_tot_med'] for r in rs]):.1f} |")
L += ['', '| model (1 tien trinh, 8 luong, 5 video) | video | ms det TV | ms track TV | ms tong TV | ms tong p95 | fps |', '|' + '---|' * 7] + b
open(R + '/B1_TABLES.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))