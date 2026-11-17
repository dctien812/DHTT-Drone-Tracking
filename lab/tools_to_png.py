"""Doi anh chup JPEG (tu /snapshot.jpg) thanh PNG nho: python tools_to_png.py in.jpg out.png [rong_toi_da]"""
import sys

import cv2

img = cv2.imread(sys.argv[1])
if img is None:
    sys.exit("khong doc duoc anh")
mw = int(sys.argv[3]) if len(sys.argv) > 3 else 640
if img.shape[1] > mw:
    img = cv2.resize(img, (mw, round(img.shape[0] * mw / img.shape[1])), interpolation=cv2.INTER_AREA)
cv2.imwrite(sys.argv[2], img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
