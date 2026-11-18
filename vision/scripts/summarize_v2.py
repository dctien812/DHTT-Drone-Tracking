"""V2: gop CSV theo video (results/v2/trk_<tag>_full_bytetrack_c<conf>.csv, tao boi track_videos.py track) -> results/v2/video_summary.csv + .md
Dung cung cach gop nhu summarize_b1.py (agg_drone): khung co phat hien >= conf, ti le video giu 1 ID, so ID TB/video; may bay: khung co 'drone' / tong khung.
Chay: python -I summarize_v2.py"""
import csv, glob, os, re
import numpy as np
R = '/mnt/d/Personal/Drone-Tracking/vision/results/v2'
rows = []
for p in sorted(glob.glob(R + '/trk_*_full_bytetrack_c*.csv')):
    tag, conf = re.match(r'trk_(.+)_full_bytetrack_c([\d.]+)\.csv', os.path.basename(p)).groups()
    rs = [{k: (v if k in ('video', 'tracker') else float(v)) for k, v in r.items()} for r in csv.DictReader(open(p))]
    dr = [r for r in rs if r['video'].startswith('V_DRONE')]; ap = [r for r in rs if r['video'].startswith('V_AIRPLANE')]
    fr = sum(r['frames'] for r in dr); afr = sum(r['frames'] for r in ap)
    rows.append(dict(model=tag, conf=conf, n_drone_videos=len(dr), drone_frames=int(fr), det_frame_rate=round(sum(r['det_frames'] for r in dr) / fr, 4),
                     videos_1id=round(float(np.mean([r['n_ids'] == 1 for r in dr])), 4), ids_mean=round(float(np.mean([r['n_ids'] for r in dr])), 2),
                     videos_zero_det=int(sum(r['det_frames'] == 0 for r in dr)),
                     airplane_frames=int(afr), airplane_frames_with_drone=int(sum(r['det_frames'] for r in ap)),
                     airplane_rate=round(sum(r['det_frames'] for r in ap) / afr, 4)))
with open(R + '/video_summary.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
L = ['| model | conf | khung drone co det | video giu 1 ID | ID TB/video | video 0 det | khung may bay co "drone" |', '|---|---|---|---|---|---|---|']
for r in rows:
    L.append(f"| {r['model']} | {r['conf']} | {100*r['det_frame_rate']:.1f}% | {100*r['videos_1id']:.1f}% | {r['ids_mean']:.2f} | {r['videos_zero_det']} | {r['airplane_frames_with_drone']}/{r['airplane_frames']} = {100*r['airplane_rate']:.1f}% |")
open(R + '/video_summary.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
