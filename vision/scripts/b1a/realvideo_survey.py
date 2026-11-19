"""(a) Khao sat: 40 khung rai deu -> 5 anh ghep (8 khung/anh) trong .office/images/video1/survey."""
import os
import sys
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from realvideo_common import *

os.makedirs(IMG + "/survey", exist_ok=True)
n = 2269
idx = [int(round(i * (n - 1) / 39)) for i in range(40)]
fr = read_frames(idx)
for s in range(5):
    ids = idx[s * 8:(s + 1) * 8]
    sh = montage([fr[i] for i in ids], 4, (270, 480), ids)
    cv2.imwrite("%s/survey/s%d.jpg" % (IMG, s), sh, [cv2.IMWRITE_JPEG_QUALITY, 85])
print(idx)
