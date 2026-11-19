"""B1a: quy anh ve be rong 2304, tao vung cat 480, bien doi khung nhan, lat khung, gop phat hien."""
import hashlib
import math
import random
import xml.etree.ElementTree as ET

import cv2
import numpy as np

SCALE = 0.6
FRAME_W = 2304
FRAME_H = 1296
CROP = 480


def parse_voc(xml_path):
    root = ET.parse(xml_path).getroot()
    bb = root.find("object").find("bndbox")
    box = tuple(int(float(bb.find(k).text)) for k in ("xmin", "ymin", "xmax", "ymax"))
    sz = root.find("size")
    return {"box": box, "size": (int(sz.find("width").text), int(sz.find("height").text))}


def scale_box(box, scale=SCALE):
    return tuple(v * scale for v in box)


def resize_to_width(img, width=FRAME_W):
    h, w = img.shape[:2]
    return cv2.resize(img, (width, int(round(h * width / w))), interpolation=cv2.INTER_AREA)


def extract_crop(img, x0, y0, size=CROP):
    if x0 < 0 or y0 < 0 or x0 + size > img.shape[1] or y0 + size > img.shape[0]:
        raise ValueError("vung cat vuot anh: (%s, %s, %s)" % (x0, y0, size))
    return img[y0:y0 + size, x0:x0 + size]


def _range(lo_edge, hi_edge, limit, size):
    """Khoang x0 nguyen sao cho vung cat chua tron [lo_edge, hi_edge] va nam trong anh."""
    return math.ceil(max(0, hi_edge - size)), math.floor(min(lo_edge, limit - size))


def _clamp(box, frame_w, frame_h):
    return (min(max(box[0], 0), frame_w), min(max(box[1], 0), frame_h),
            min(max(box[2], 0), frame_w), min(max(box[3], 0), frame_h))


def frame_seed(base_seed, seg, frame):
    """Seed rieng cho tung khung, tat dinh giua cac tien trinh (khong dung hash())."""
    d = hashlib.sha256(("%s|%s|%s" % (base_seed, seg, frame)).encode("utf-8")).digest()
    return int.from_bytes(d[:8], "big")


def _centred(box, frame_w, frame_h, size):
    x0 = min(max(int(round((box[0] + box[2]) / 2 - size / 2)), 0), frame_w - size)
    y0 = min(max(int(round((box[1] + box[3]) / 2 - size / 2)), 0), frame_h - size)
    b = (min(max(box[0] - x0, 0), size), min(max(box[1] - y0, 0), size),
         min(max(box[2] - x0, 0), size), min(max(box[3] - y0, 0), size))
    return {"x0": x0, "y0": y0, "box": b, "truncated": True}


def _result(box, x0, y0):
    return {"x0": x0, "y0": y0, "box": (box[0] - x0, box[1] - y0, box[2] - x0, box[3] - y0),
            "truncated": False}


def positive_crop(box, seed, frame_w=FRAME_W, frame_h=FRAME_H, size=CROP):
    box = _clamp(box, frame_w, frame_h)
    xlo, xhi = _range(box[0], box[2], frame_w, size)
    ylo, yhi = _range(box[1], box[3], frame_h, size)
    if xlo > xhi or ylo > yhi:
        return _centred(box, frame_w, frame_h, size)
    rng = random.Random(seed)
    return _result(box, rng.randint(xlo, xhi), rng.randint(ylo, yhi))


def offcenter_crop(box, seed, max_gap=24, frame_w=FRAME_W, frame_h=FRAME_H, size=CROP):
    box = _clamp(box, frame_w, frame_h)
    xlo, xhi = _range(box[0], box[2], frame_w, size)
    ylo, yhi = _range(box[1], box[3], frame_h, size)
    if xlo > xhi or ylo > yhi:
        return _centred(box, frame_w, frame_h, size)
    rng = random.Random(seed)
    side = rng.choice("ltrb")
    g = rng.randint(0, max_gap)
    x0, y0 = rng.randint(xlo, xhi), rng.randint(ylo, yhi)
    if side == "l":
        x0 = math.ceil(box[0] - g)
    elif side == "r":
        x0 = math.floor(box[2] + g - size)
    elif side == "t":
        y0 = math.ceil(box[1] - g)
    else:
        y0 = math.floor(box[3] + g - size)
    return _result(box, min(max(x0, xlo), xhi), min(max(y0, ylo), yhi))


def background_crop(boxes, seed, margin=32, frame_w=FRAME_W, frame_h=FRAME_H, size=CROP):
    xs = np.arange(frame_w - size + 1)[None, :]
    ys = np.arange(frame_h - size + 1)[:, None]
    ok = np.ones((ys.shape[0], xs.shape[1]), bool)
    for x1, y1, x2, y2 in boxes:
        clear = (xs - margin >= x2) | (xs + size + margin <= x1) | \
                (ys - margin >= y2) | (ys + size + margin <= y1)
        ok &= clear
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return None
    k = int(idx[random.Random(seed).randrange(idx.size)])
    return {"x0": k % ok.shape[1], "y0": k // ok.shape[1]}


def _starts(limit, size, overlap):
    return list(range(0, limit - size, size - overlap)) + [limit - size]


def tile_frame(frame_w=FRAME_W, frame_h=FRAME_H, size=CROP, overlap=200):
    return [(x, y) for y in _starts(frame_h, size, overlap) for x in _starts(frame_w, size, overlap)]


def tiles_with_target(box, tiles, size=CROP):
    return [(x, y) for x, y in tiles
            if x <= box[0] and y <= box[1] and box[2] <= x + size and box[3] <= y + size]


def crop_to_frame(box, x0, y0):
    return (box[0] + x0, box[1] + y0, box[2] + x0, box[3] + y0)


def _iou(a, b):
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union


def merge_detections(dets, iou_thr):
    kept = []
    for d in sorted(dets, key=lambda d: -d[4]):
        if all(_iou(d, k) <= iou_thr for k in kept):
            kept.append(d)
    return kept


def to_yolo_label(box_in_crop, size=CROP, cls=0):
    x1, y1, x2, y2 = box_in_crop
    return "%d %.6f %.6f %.6f %.6f" % (cls, (x1 + x2) / 2 / size, (y1 + y2) / 2 / size,
                                       (x2 - x1) / size, (y2 - y1) / size)


def make_positive_sample(img_path, xml_path, seed):
    from PIL import Image
    ann = parse_voc(xml_path)
    img = resize_to_width(np.asarray(Image.open(img_path).convert("RGB")))
    c = positive_crop(scale_box(ann["box"], FRAME_W / ann["size"][0]), seed)
    return {"image": extract_crop(img, c["x0"], c["y0"]), "label": to_yolo_label(c["box"]),
            "box": c["box"], "x0": c["x0"], "y0": c["y0"], "truncated": c["truncated"]}
