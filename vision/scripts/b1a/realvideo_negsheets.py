"""Anh ghep khung nguyen (12 khung/anh, 4x3 o 270x480) de kiem xem khung 'khong co may bay' co dung la am khong."""
import os
import sys
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

a, b = int(sys.argv[1]), int(sys.argv[2])
ids = list(range(a, b, 15))
os.makedirs(IMG + "/neg", exist_ok=True)
fr = dict(iter_frames(ids))
for s in range(0, len(ids), 12):
    part = ids[s:s + 12]
    sh = montage([fr[i] for i in part], 4, (270, 480), part)
    cv2.imwrite("%s/neg/n%02d.jpg" % (IMG, s // 12), sh, [cv2.IMWRITE_JPEG_QUALITY, 88])
print(len(ids))
