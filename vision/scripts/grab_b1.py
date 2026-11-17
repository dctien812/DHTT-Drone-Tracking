"""B1: lay 3 khung (25/50/75%) cua moi video ket qua ghep thanh 1 anh de tu kiem. python -I grab_b1.py VIDEO_DIR OUT_DIR"""
import sys, glob, os
import cv2, numpy as np
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
for p in sorted(glob.glob(src + '/*_tracked.mp4')):
    c = cv2.VideoCapture(p); n = int(c.get(cv2.CAP_PROP_FRAME_COUNT)); t = []
    for q in (0.25, 0.5, 0.75):
        c.set(cv2.CAP_PROP_POS_FRAMES, int(n * q)); ok, f = c.read(); t.append(f)
    cv2.imwrite(f'{out}/{os.path.basename(p)[:-4]}.jpg', np.hstack(t))