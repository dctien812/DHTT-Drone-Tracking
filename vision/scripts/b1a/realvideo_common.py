"""Tien ich chung cho video that (B1a A6). Khung 1080x1920 doc. Moi anh nam trong .office/images/video1 (bi git bo qua)."""
import os
import cv2
import numpy as np

ROOT = "/mnt/d/Personal/Drone-Tracking"
VIDEO = ROOT + "/.office/images/CB16E8B8-F7A8-4DF7-AA80-94568E3200D3.MP4"
IMG = ROOT + "/.office/images/video1"
RES = ROOT + "/vision/results/b1a/realvideo1"
FPS = 30.0
CROP = 480


def read_frames(indices):
    """Doc cac khung theo chi so (tang dan); tra ve dict idx -> BGR."""
    want = sorted(set(indices))
    cap = cv2.VideoCapture(VIDEO)
    out = {}
    i = 0
    j = 0
    while j < len(want):
        ok = cap.grab()
        if not ok:
            break
        if i == want[j]:
            ok, f = cap.retrieve()
            out[i] = f
            j += 1
        i += 1
    cap.release()
    return out


def iter_frames(indices):
    """Sinh (idx, BGR) mot lan duyet video, khong giu nhieu khung."""
    want = sorted(set(indices))
    cap = cv2.VideoCapture(VIDEO)
    i = 0
    j = 0
    while j < len(want) and cap.grab():
        if i == want[j]:
            ok, f = cap.retrieve()
            yield i, f
            j += 1
        i += 1
    cap.release()


def starts(limit, size, overlap):
    """Diem bat dau o lat: ham rieng vi prep_crops.tile_frame dung hang 2304x1296 mac dinh (cung cong thuc _starts)."""
    return list(range(0, limit - size, size - overlap)) + [limit - size]


def tiles(w=1080, h=1920, size=CROP, overlap=200):
    return [(x, y) for y in starts(h, size, overlap) for x in starts(w, size, overlap)]


def crop_view(img, cx, cy, win=160, scale=2.0, boxes=(), text="", ticks=True):
    """Cat cua so win x win quanh (cx,cy) (kep vao khung), phong to, ve cac khung bao (x1,y1,x2,y2,mau BGR)."""
    h, w = img.shape[:2]
    x0 = int(min(max(cx - win / 2, 0), w - win))
    y0 = int(min(max(cy - win / 2, 0), h - win))
    v = cv2.resize(img[y0:y0 + win, x0:x0 + win], None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    for b in boxes:
        col = b[4] if len(b) > 4 else (0, 255, 0)
        cv2.rectangle(v, (int((b[0] - x0) * scale), int((b[1] - y0) * scale)),
                      (int((b[2] - x0) * scale), int((b[3] - y0) * scale)), col, 1)
    if ticks:
        step = 10 if win <= 80 else 20 if win <= 160 else 40 if win <= 320 else 80
        for gx in range((x0 // step + 1) * step, x0 + win, step):
            px = int((gx - x0) * scale)
            cv2.line(v, (px, 0), (px, 6), (255, 0, 255), 1)
            if (gx // step) % 2 == 0:
                cv2.putText(v, str(gx), (px - 12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 255), 1)
        for gy in range((y0 // step + 1) * step, y0 + win, step):
            py = int((gy - y0) * scale)
            cv2.line(v, (0, py), (6, py), (255, 0, 255), 1)
            if (gy // step) % 2 == 0:
                cv2.putText(v, str(gy), (8, py + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 255), 1)
    cv2.putText(v, text, (3, v.shape[0] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    return v


def montage(imgs, cols, cell, labels=None):
    """imgs: list BGR; moi o resize ve cell (w,h)."""
    rows = (len(imgs) + cols - 1) // cols
    sheet = np.zeros((rows * cell[1], cols * cell[0], 3), np.uint8)
    for k, im in enumerate(imgs):
        r, c = divmod(k, cols)
        t = cv2.resize(im, cell, interpolation=cv2.INTER_AREA)
        if labels:
            cv2.putText(t, str(labels[k]), (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        sheet[r * cell[1]:(r + 1) * cell[1], c * cell[0]:(c + 1) * cell[0]] = t
    return sheet
