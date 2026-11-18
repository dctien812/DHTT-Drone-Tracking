"""V2: gop bang so sanh ft (cu) va ft2 (moi) -> results/v2/compare.md. Chay: python -I compare_v2.py"""
import csv
R = '/mnt/d/Personal/Drone-Tracking/vision/results/v2'
rd = lambda p: list(csv.DictReader(open(p)))
c = {t: rd(f'{R}/clean_{t}.csv') for t in ('ft', 'ft2')}
h = {t: rd(f'{R}/hand120_{t}.csv') for t in ('ft', 'ft2')}
v = rd(f'{R}/video_summary.csv')
f = lambda x: f'{float(x):.3f}' if x != '' else '-'
L = ['## Tap test sach (1 anh 640 / mau; ngoac: so mau moi nhom be rong; be rong = px trong anh dua vao model)']
for sub in ('all', 'dut', 'detfly'):
    L += ['', f'### {sub}', '| model | conf | P | R | bao dong gia/100 anh | R <10 | R 10-20 | R 20-40 | R >40 | sai so be rong trung vi px (%) | p90 px (%) |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for t in ('ft', 'ft2'):
        for r in c[t]:
            if r['subset'] == sub:
                L.append(f"| {t} | {r['conf']} | {f(r['precision'])} | {f(r['recall'])} | {r['fp_per_100img']} | " + ' | '.join(f"{f(r['rec_' + b])} (n={r['n_' + b]})" for b in ('<10', '10-20', '20-40', '>40')) +
                         f" | {r['w_err_med_px']} ({r['w_err_med_pct']}%) | {r['w_err_p90_px']} ({r['w_err_p90_pct']}%) |")
L += ['', '## 120 khung nhan tay (99 drone, 20 may bay, 1 khong co)', '| model | conf | khung drone bat duoc | precision | may bay bi goi drone | khung "chac" bat duoc |', '|---|---|---|---|---|---|']
for t in ('ft', 'ft2'):
    for r in h[t]:
        L.append(f"| {t} | {r['conf']} | {r['drone_caught']}/{r['drone_frames']} | {r['precision']} ({r['dets_matched']}/{r['dets_total']}) | {r['airplane_called_drone']}/{r['airplane_frames']} | {r['sure_caught']}/{r['sure_drone_frames']} |")
L += ['', '## 119 video (cả khung, ByteTrack mac dinh; 114 video drone + 4 may bay)', '| model | conf | khung drone co det | video giu 1 ID | ID TB/video | video 0 det | khung may bay co "drone" |', '|---|---|---|---|---|---|---|']
for r in v:
    L.append(f"| {r['model']} | {r['conf']} | {100*float(r['det_frame_rate']):.1f}% | {100*float(r['videos_1id']):.1f}% | {r['ids_mean']} | {r['videos_zero_det']} | {r['airplane_frames_with_drone']}/{r['airplane_frames']} = {100*float(r['airplane_rate']):.1f}% |")
open(f'{R}/compare.md', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
