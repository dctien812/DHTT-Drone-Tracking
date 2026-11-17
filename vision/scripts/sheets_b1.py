"""B1: tao anh tong hop (mau khung giua cua moi video) de xem noi dung. Chi doc video."""
import sys, glob, os
import cv2, numpy as np
V = '/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/video'
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
ps = sorted(glob.glob(V + '/*.mp4') + glob.glob(V + '/*.MOV'))
tw, th, cols, per = 320, 256, 5, 20
for s in range(0, len(ps), per):
    tiles = []
    for p in ps[s:s + per]:
        c = cv2.VideoCapture(p); n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
        c.set(cv2.CAP_PROP_POS_FRAMES, n // 2); ok, f = c.read()
        if not ok: f = np.zeros((th, tw, 3), np.uint8)
        h, w = f.shape[:2]; k = min(tw / w, th / h); f = cv2.resize(f, (int(w * k), int(h * k)))
        t = np.zeros((th, tw, 3), np.uint8); t[:f.shape[0], :f.shape[1]] = f
        cv2.putText(t, os.path.basename(p)[2:-4], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        tiles.append(t)
    while len(tiles) % cols: tiles.append(np.zeros((th, tw, 3), np.uint8))
    img = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
    cv2.imwrite(f'{out}/sheet_{s // per:02d}.jpg', img)
print('ok')