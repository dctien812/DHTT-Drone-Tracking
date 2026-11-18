"""Hieu chuan camera bang ban co (OpenCV), luu ma tran camera + he so meo ra JSON.

    python tools/calibrate_camera.py --images anh_banco/ --cols 9 --rows 6 --square-mm 25 --out camera.json

--cols/--rows la so GOC TRONG cua ban co (o vuong - 1). Chup 15-25 anh ban co phang, nhieu goc nghieng/khoang cach,
phu ca vung ria khung, cung do phan giai se chay labview. Camera Module 3 Wide co meo ong kinh dang ke.
Khong gui lenh toi thiet bi nao; chi doc anh va ghi mot file JSON.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

EXTS = ("*.jpg", "*.jpeg", "*.png", "*.bmp")


def find_corners(gray: np.ndarray, pattern: tuple):
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    ok, corners = cv2.findChessboardCorners(gray, pattern, flags)
    if not ok:
        return None
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    return cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), crit)


def calibrate(images: list, cols: int, rows: int, square_mm: float) -> dict:
    """images: danh sach ndarray (BGR hoac xam), cung kich thuoc. Nem ValueError neu qua it anh dung duoc."""
    pattern = (cols, rows)
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_mm
    obj_pts, img_pts, size = [], [], None
    for img in images:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        if size is None:
            size = (gray.shape[1], gray.shape[0])
        elif size != (gray.shape[1], gray.shape[0]):
            continue   # khac do phan giai: bo qua
        c = find_corners(gray, pattern)
        if c is not None:
            obj_pts.append(obj)
            img_pts.append(c)
    if len(img_pts) < 5:
        raise ValueError(f"Chi {len(img_pts)}/{len(images)} anh tim thay ban co {cols}x{rows} goc trong (can >= 5, nen 15+)")
    rms, k, dist, _, _ = cv2.calibrateCamera(obj_pts, img_pts, size, None, None)
    return {"width": size[0], "height": size[1], "camera_matrix": k.tolist(),
            "dist_coeffs": dist.reshape(-1).tolist(), "rms_reprojection_px": float(rms),
            "board": {"cols": cols, "rows": rows, "square_mm": square_mm},
            "images_used": len(img_pts), "images_total": len(images)}


def labview_flags(result: dict) -> str:
    k = result["camera_matrix"]
    return (f"--cam-width {result['width']} --cam-height {result['height']} "
            f"--fx {k[0][0]:.1f} --fy {k[1][1]:.1f} --cx {k[0][2]:.1f} --cy {k[1][2]:.1f}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--images", required=True, help="thu muc chua anh ban co")
    p.add_argument("--cols", type=int, default=9, help="so goc trong theo chieu ngang")
    p.add_argument("--rows", type=int, default=6, help="so goc trong theo chieu doc")
    p.add_argument("--square-mm", type=float, default=25.0)
    p.add_argument("--out", default="camera_calibration.json")
    a = p.parse_args(argv)
    paths = sorted(f for e in EXTS for f in glob.glob(os.path.join(a.images, e)))
    imgs = [im for im in (cv2.imread(f) for f in paths) if im is not None]
    if not imgs:
        print(f"LOI: khong co anh trong {a.images}", file=sys.stderr)
        return 2
    try:
        res = calibrate(imgs, a.cols, a.rows, a.square_mm)
    except ValueError as e:
        print(f"LOI: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"Da ghi {a.out}: {res['images_used']}/{res['images_total']} anh, RMS {res['rms_reprojection_px']:.3f} px")
    print("Tham so cho labview (khung CHUA thu nho; neu --max-width < rong thi nhan he so fx,fy,cx,cy theo ti le):")
    print("  " + labview_flags(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
