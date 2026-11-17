"""B1 a: danh muc video (do phan giai, so khung, fps) + thong tin model. Chi doc."""
import sys, csv, glob, os
import cv2
V = '/mnt/d/Personal/DHTT-TRACKING-TEST/AI-6/video'
out = sys.argv[1]
rows = []
for p in sorted(glob.glob(V + '/*.mp4') + glob.glob(V + '/*.MOV')):
    c = cv2.VideoCapture(p)
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT)); fps = c.get(cv2.CAP_PROP_FPS)
    w = int(c.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
    k = 0
    while True:
        ok, _ = c.read()
        if not ok: break
        k += 1
    rows.append(dict(video=os.path.basename(p), width=w, height=h, frames_meta=n, frames_read=k, fps=round(fps, 3), sec=round(k / fps, 2) if fps else 0))
    c.release()
with open(out, 'w', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
print(len(rows), 'videos', sum(r['frames_read'] for r in rows), 'frames')