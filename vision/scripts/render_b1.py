"""B1: ve khung + ID + conf len video (tracker chay lai tu npz). Chay: python -I render_b1.py DET_DIR OUT_DIR conf video1,video2,..."""
import sys, os
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from track_videos import make_tracker, _R, VID
det, out, conf, names = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4].split(',')
os.makedirs(out, exist_ok=True)
for nm in names:
    z = np.load(f'{det}/{nm}.npz'); d = z['dets']; n, fps, W, H = z['meta']; n = int(n)
    p = f'{VID}/{nm[2:]}.mp4' if os.path.exists(f'{VID}/{nm[2:]}.mp4') else f'{VID}/{nm}.MOV'
    if not os.path.exists(p): p = f'{VID}/{nm}.mp4'
    if nm == 'VIDEO': p = f'{VID}/VIDEO.MOV'
    c = cv2.VideoCapture(p); tk = make_tracker('bytetrack', conf, fps)
    vw = cv2.VideoWriter(f'{out}/{nm}_tracked.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (int(W), int(H)))
    for k in range(n):
        ok, f = c.read()
        if not ok: break
        s = d[d[:, 0] == k][:, 1:] if len(d) else np.zeros((0, 5), np.float32)
        for b in s:  # phat hien chua thanh track: net mong xam
            if b[4] < conf: cv2.rectangle(f, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (160, 160, 160), 1)
        r = tk.update(_R(s), None)
        for row in r:
            x1, y1, x2, y2 = [int(v) for v in row[:4]]
            cv2.rectangle(f, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (0, 255, 0), 1)
            cv2.putText(f, f'#{int(row[4])} {row[5]:.2f}', (x1, max(y1 - 6, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        cv2.putText(f, f'{nm} f{k}', (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        vw.write(f)
    vw.release(); print(nm, 'ok')