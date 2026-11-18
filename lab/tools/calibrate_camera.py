"""Hieu chuan camera bang ban co (OpenCV), luu ma tran camera + he so meo ra JSON.

    python tools/calibrate_camera.py --images anh_banco/ --cols 9 --rows 6 --square-mm 25 --out camera.json

--cols/--rows la so GOC TRONG cua ban co (o vuong - 1). Chup 15-25 anh ban co phang, nhieu goc nghieng/khoang cach,
phu ca vung ria khung, cung do phan giai se chay labview. Camera Module 3 Wide co meo ong kinh dang ke.
Khong gui lenh toi thiet bi nao; chi doc anh va ghi mot file JSON.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shlex
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


def calibrate(images: list, cols: int, rows: int, square_mm: float, names: list = None) -> dict:
    """images: danh sach ndarray (BGR hoac xam), nen cung kich thuoc: lan co thi lay co DA SO, anh co khac bi bao va bo
    (hoa thi nem ValueError). Anh khong thay ban co bi bao tren stderr (kem ten trong `names`). Nem ValueError neu qua it anh dung duoc."""
    pattern = (cols, rows)
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_mm
    names = names or [f"anh #{i}" for i in range(len(images))]
    sizes = collections.Counter((im.shape[1], im.shape[0]) for im in images)
    common = sizes.most_common()
    if len(common) > 1 and common[0][1] == common[1][1]:   # hoa: khong doan
        raise ValueError("Anh lan do phan giai, khong co co da so (" + ", ".join(f"{w}x{h}: {n} anh" for (w, h), n in common)
                         + "): chi de anh cung do phan giai voi che do se chay labview")
    obj_pts, img_pts, size = [], [], (common[0][0] if common else None)   # co theo da so
    for img, name in zip(images, names):
        if (img.shape[1], img.shape[0]) != size:
            print(f"BO QUA {name}: co {img.shape[1]}x{img.shape[0]} khac da so {size[0]}x{size[1]}", file=sys.stderr)
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        c = find_corners(gray, pattern)
        if c is None:
            print(f"BO QUA {name}: khong tim thay ban co {cols}x{rows} goc trong", file=sys.stderr)
            continue
        obj_pts.append(obj)
        img_pts.append(c)
    if len(img_pts) < 5:
        raise ValueError(f"Chi {len(img_pts)}/{len(images)} anh tim thay ban co {cols}x{rows} goc trong (can >= 5, nen 15+)")
    rms, k, dist, _, _ = cv2.calibrateCamera(obj_pts, img_pts, size, None, None)
    return {"width": size[0], "height": size[1], "camera_matrix": k.tolist(),
            "dist_coeffs": dist.reshape(-1).tolist(), "rms_reprojection_px": float(rms),
            "board": {"cols": cols, "rows": rows, "square_mm": square_mm},
            "images_used": len(img_pts), "images_total": len(images)}


def labview_flags(result: dict, calib_path: str = "camera.json") -> str:
    """labview doc fx,fy,cx,cy tu file va tu quy doi theo ti le thu nho (--max-width): khong chep tay he so."""
    return f"--calib {shlex.quote(calib_path)} --cam-width {result['width']} --cam-height {result['height']}"


def list_images(folder: str) -> list:
    """Duoi anh khop khong phan biet hoa thuong (.JPG, .Png...), sap xep, khong trung."""
    exts = tuple(e[1:] for e in EXTS)
    return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                  if n.lower().endswith(exts) and os.path.isfile(os.path.join(folder, n)))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--images", required=True, help="thu muc chua anh ban co")
    p.add_argument("--cols", type=int, default=9, help="so goc trong theo chieu ngang")
    p.add_argument("--rows", type=int, default=6, help="so goc trong theo chieu doc")
    p.add_argument("--square-mm", type=float, default=25.0)
    p.add_argument("--out", default="camera_calibration.json")
    a = p.parse_args(argv)
    if not os.path.isdir(a.images):
        print(f"LOI: khong co thu muc {a.images}", file=sys.stderr)
        return 2
    imgs, names = [], []
    for f in list_images(a.images):
        im = cv2.imread(f)
        if im is None:
            print(f"BO QUA {os.path.basename(f)}: khong doc duoc file anh", file=sys.stderr)
            continue
        imgs.append(im)
        names.append(os.path.basename(f))
    if not imgs:
        print(f"LOI: khong co anh trong {a.images}", file=sys.stderr)
        return 2
    try:
        res = calibrate(imgs, a.cols, a.rows, a.square_mm, names)
    except ValueError as e:
        print(f"LOI: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"Da ghi {a.out}: {res['images_used']}/{res['images_total']} anh, RMS {res['rms_reprojection_px']:.3f} px")
    print("Chay labview voi (labview tu quy doi fx,fy,cx,cy theo ti le thu nho; he so meo CHUA duoc dung):")
    print("  " + labview_flags(res, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
