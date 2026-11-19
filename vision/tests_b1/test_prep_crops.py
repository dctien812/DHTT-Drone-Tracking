"""Test pha do cho vision/scripts/b1a/prep_crops.py (vung cat 480 tu khung quy ve be rong 2304).

Chu ky da chot (toa do box = (x1, y1, x2, y2) pixel; khung 2304x1296):
  SCALE = 0.6 ; FRAME_W = 2304 ; FRAME_H = 1296 ; CROP = 480
  parse_voc(xml_path) -> {"box": (xmin, ymin, xmax, ymax), "size": (w, h)}   # thang goc 3840x2160
  scale_box(box, scale=SCALE) -> box nhan voi scale
  resize_to_width(img, width=2304) -> ndarray (round(h*width/w), width, C)
  extract_crop(img, x0, y0, size=480) -> ndarray (size, size, C) ; ValueError neu vuot anh
  positive_crop(box, seed, frame_w=2304, frame_h=1296, size=480)
        -> {"x0": int, "y0": int, "box": box trong vung cat, "truncated": bool}
  offcenter_crop(box, seed, max_gap=24, ...) -> cung dang; khung nam tron, cach mep gan nhat 0..max_gap px
  background_crop(boxes, seed, margin=32, frame_w=2304, frame_h=1296, size=480)
        -> {"x0": int, "y0": int} hoac None neu khong co cho; vung cat cach moi box >= margin px
  tile_frame(frame_w=2304, frame_h=1296, size=480, overlap=200) -> [(x0, y0), ...]  (mac dinh 8 cot x 4 hang = 32 o)
  tiles_with_target(box, tiles, size=480) -> [(x0, y0)] cac o chua TRON box
  crop_to_frame(box, x0, y0) -> box + (x0, y0, x0, y0)
  merge_detections(dets, iou_thr) -> NMS giua cac o; dets = [(x1, y1, x2, y2, conf)] (toa do khung);
        tra ve danh sach giu lai, xep conf giam dan
  to_yolo_label(box_in_crop, size=480, cls=0) -> "0 cx cy w h" (chuan hoa, 6 chu so thap phan)
  make_positive_sample(img_path, xml_path, seed) -> {"image", "label", "box", "x0", "y0", "truncated"}
"""
import random

import numpy as np
import pytest

W, H, C = 2304, 1296, 480
HAND_BOX = (2558, 956, 2646, 1009)          # nhan that lay tu 0_0_000001.xml cua D'/Horizontal
HAND_SCALED = (1534.8, 573.6, 1587.6, 605.4)


def contains(crop, box):
    x0, y0 = crop["x0"], crop["y0"]
    return x0 <= box[0] and y0 <= box[1] and box[2] <= x0 + C and box[3] <= y0 + C


def inside_image(crop):
    return 0 <= crop["x0"] <= W - C and 0 <= crop["y0"] <= H - C


def test_constants():
    import prep_crops as p
    assert p.SCALE == pytest.approx(0.6)
    assert (p.FRAME_W, p.FRAME_H, p.CROP) == (2304, 1296, 480)


def test_scale_box_hand_computed():
    from prep_crops import scale_box
    got = scale_box(HAND_BOX)
    assert got == pytest.approx(HAND_SCALED, abs=1e-6)
    assert got[2] - got[0] == pytest.approx(52.8)      # 88 * 0.6
    assert got[3] - got[1] == pytest.approx(31.8)      # 53 * 0.6


def test_resize_to_width_shape_and_content():
    from prep_crops import resize_to_width
    img = np.zeros((2160, 3840, 3), np.uint8)
    img[500:600, 1000:1100] = 255                      # o vuong trang 100x100
    out = resize_to_width(img, 2304)
    assert out.shape == (1296, 2304, 3)
    assert out[330, 630].min() >= 240                  # tam o trang sau scale: (1050*0.6, 550*0.6)
    assert out[100, 100].max() <= 10                   # nen den


def test_parse_voc_reads_box_and_size(tmp_path):
    from prep_crops import parse_voc
    xml = tmp_path / "0_0_000001.xml"
    xml.write_text("""<annotation>
 <object><name>Fixed_Wing_UAV</name><bndbox><xmax>2646</xmax><xmin>2558</xmin><ymax>1009</ymax><ymin>956</ymin></bndbox></object>
 <size><depth>3</depth><height>2160</height><width>3840</width></size></annotation>""")
    got = parse_voc(str(xml))
    assert tuple(got["box"]) == (2558, 956, 2646, 1009)
    assert tuple(got["size"]) == (3840, 2160)


def test_extract_crop_pixels_and_bounds():
    from prep_crops import extract_crop
    img = np.arange(1296 * 2304, dtype=np.int64).reshape(1296, 2304) % 251
    img = np.stack([img] * 3, axis=-1).astype(np.uint8)
    c = extract_crop(img, 100, 50)
    assert c.shape == (480, 480, 3)
    assert (c == img[50:530, 100:580]).all()
    with pytest.raises(ValueError):
        extract_crop(img, 2000, 0)
    with pytest.raises(ValueError):
        extract_crop(img, -1, 0)


@pytest.mark.parametrize("box", [
    HAND_SCALED, (0, 0, 50, 50), (2250, 1250, 2304, 1296), (0, 600, 40, 640),
    (1000, 0, 1030, 20), (1100, 1200, 1480, 1296), (700, 300, 1180, 780)])      # cuoi: dung 480x480
def test_positive_crop_contains_whole_box_and_stays_in_image(box):
    from prep_crops import positive_crop
    for seed in range(200):
        c = positive_crop(box, seed)
        assert contains(c, box), (seed, c)
        assert inside_image(c)
        assert c["truncated"] is False
        assert isinstance(c["x0"], int) and isinstance(c["y0"], int)
        assert c["box"] == pytest.approx((box[0] - c["x0"], box[1] - c["y0"],
                                          box[2] - c["x0"], box[3] - c["y0"]))


def test_positive_crop_position_is_random_but_seeded():
    from prep_crops import positive_crop
    a = [positive_crop(HAND_SCALED, s) for s in range(100)]
    assert a == [positive_crop(HAND_SCALED, s) for s in range(100)]      # tat dinh theo seed
    assert len({c["x0"] for c in a}) >= 20
    lefts = [c["box"][0] for c in a]
    tops = [c["box"][1] for c in a]
    assert max(lefts) - min(lefts) > 200               # khung khong luon o giua
    assert max(tops) - min(tops) > 200
    centred = sum(abs((c["box"][0] + c["box"][2]) / 2 - 240) < 1 for c in a)
    assert centred < 10


def test_positive_crop_position_covers_whole_range_up_to_edges():
    from prep_crops import positive_crop
    a = [positive_crop(HAND_SCALED, s) for s in range(500)]
    lefts = [c["box"][0] for c in a]
    tops = [c["box"][1] for c in a]
    assert min(lefts) < 20 and max(lefts) > 407        # toi da kha dung: 427,2
    assert min(tops) < 20 and max(tops) > 407          # toi da kha dung: 448,2


def test_positive_crop_corner_boxes_force_origin():
    from prep_crops import positive_crop
    c = positive_crop((0, 0, 50, 50), 3)
    assert (c["x0"], c["y0"]) == (0, 0)
    c = positive_crop((2250, 1250, 2304, 1296), 3)
    assert (c["x0"], c["y0"]) == (W - C, H - C)


def test_positive_crop_larger_than_480_is_centred_clipped_and_flagged():
    from prep_crops import positive_crop
    c = positive_crop((1000, 400, 1700, 700), 5)       # 700 x 300 > 480 theo chieu ngang
    assert c["truncated"] is True
    assert (c["x0"], c["y0"]) == (1110, 310)           # tam khung (1350, 550) - 240
    assert c["box"] == pytest.approx((0, 90, 480, 390))   # cat vao vung cat
    assert inside_image(c)
    # ket qua khong phu thuoc seed (khong co cho ngau nhien khi khung khong vua)
    assert positive_crop((1000, 400, 1700, 700), 99) == c


def test_offcenter_crop_box_inside_and_near_an_edge():
    from prep_crops import offcenter_crop
    sides = set()
    for seed in range(200):
        c = offcenter_crop(HAND_SCALED, seed, max_gap=24)
        assert contains(c, HAND_SCALED) and inside_image(c)
        b = c["box"]
        gaps = {"l": b[0], "t": b[1], "r": C - b[2], "b": C - b[3]}
        side, g = min(gaps.items(), key=lambda kv: kv[1])
        assert 0 <= g <= 24 + 1e-6, (seed, gaps)
        sides.add(side)
    assert sides == {"l", "t", "r", "b"}               # du bon mep
    assert offcenter_crop(HAND_SCALED, 7) == offcenter_crop(HAND_SCALED, 7)


def test_background_crop_has_margin_and_zero_iou():
    from prep_crops import background_crop
    box = HAND_SCALED
    xs = set()
    for seed in range(300):
        c = background_crop([box], seed, margin=32)
        assert c is not None
        assert inside_image({"x0": c["x0"], "y0": c["y0"]})
        x0, y0 = c["x0"], c["y0"]
        # vung cat mo rong 32 px khong cat khung
        assert (x0 - 32 >= box[2] or x0 + C + 32 <= box[0] or
                y0 - 32 >= box[3] or y0 + C + 32 <= box[1]), (seed, c)
        xs.add(x0)
    assert len(xs) >= 20
    assert background_crop([box], 11) == background_crop([box], 11)


def test_background_crop_margin_parameter_is_respected():
    from prep_crops import background_crop
    box = (1100, 600, 1200, 700)
    for seed in range(200):
        c = background_crop([box], seed, margin=100)
        x0, y0 = c["x0"], c["y0"]
        assert (x0 - 100 >= box[2] or x0 + C + 100 <= box[0] or
                y0 - 100 >= box[3] or y0 + C + 100 <= box[1])


@pytest.mark.parametrize("box", [(0, 0, 50, 50), (2254, 1246, 2304, 1296), (0, 1246, 50, 1296)])
def test_offcenter_crop_for_boxes_in_image_corners(box):
    from prep_crops import offcenter_crop
    for seed in range(100):
        c = offcenter_crop(box, seed)
        assert contains(c, box) and inside_image(c)
        b = c["box"]
        assert min(b[0], b[1], C - b[2], C - b[3]) <= 24 + 1e-6


def test_offcenter_crop_for_box_larger_than_crop_is_flagged():
    from prep_crops import offcenter_crop
    c = offcenter_crop((1000, 400, 1700, 700), 3)
    assert c["truncated"] is True and inside_image(c)


def test_background_crop_exact_boundary_cases():
    from prep_crops import background_crop
    # hop 0..1792 rong: vung cat phai bat dau >= 1792 + 32 = 1824 = W - 480 -> dung 1 cho
    for seed in range(20):
        c = background_crop([(0, 0, 1792, 1296)], seed)
        assert c is not None and c["x0"] == 1824
    # them 1 px: khong con cho nao
    assert background_crop([(0, 0, 1793, 1296)], 0) is None


def test_background_crop_none_when_no_room():
    from prep_crops import background_crop
    assert background_crop([(0, 0, W, H)], 1) is None
    assert background_crop([(0, 0, W, H // 2), (0, H // 2, W, H)], 1) is None


def test_tile_frame_default_layout():
    from prep_crops import tile_frame
    tiles = tile_frame()
    assert len(tiles) == 32 == len(set(tiles))
    assert sorted({x for x, _ in tiles}) == [0, 280, 560, 840, 1120, 1400, 1680, 1824]
    assert sorted({y for _, y in tiles}) == [0, 280, 560, 816]
    assert all(0 <= x <= W - C and 0 <= y <= H - C for x, y in tiles)
    cover = np.zeros((H, W), bool)
    for x, y in tiles:
        cover[y:y + C, x:x + C] = True
    assert cover.all()                                 # phu kin khung
    xs = sorted({x for x, _ in tiles})
    assert all((a + C) - b >= 200 for a, b in zip(xs, xs[1:]))   # chong lan >= 200 px
    ys = sorted({y for _, y in tiles})
    assert all((a + C) - b >= 200 for a, b in zip(ys, ys[1:]))


def test_tile_frame_without_overlap():
    from prep_crops import tile_frame
    tiles = tile_frame(overlap=0)
    assert sorted({x for x, _ in tiles}) == [0, 480, 960, 1440, 1824]
    assert sorted({y for _, y in tiles}) == [0, 480, 816]
    assert len(tiles) == 15


def test_tiles_with_target_hand_computed():
    from prep_crops import tile_frame, tiles_with_target
    tiles = tile_frame()
    # x0 in [1107.6, 1534.8] -> 1120, 1400 ; y0 in [125.4, 573.6] -> 280, 560
    assert sorted(tiles_with_target(HAND_SCALED, tiles)) == [(1120, 280), (1120, 560), (1400, 280), (1400, 560)]
    # khung rong 202 > 200 nam qua duong noi x=279..481: khong o nao chua tron
    assert tiles_with_target((279, 100, 481, 150), tiles) == []
    # khung nho trong vung chong lan chua trong >= 2 o
    assert len(tiles_with_target((300, 100, 340, 140), tiles)) >= 2


def test_every_target_up_to_200px_is_inside_some_tile_sweep_by_1px():
    """Quet xac dinh: moi be rong 1..200 (buoc 1 px) o cac vi tri nguy hiem nhat quanh duong noi.
    O la tich cac cot x cac hang y nen quet tung truc rieng la du."""
    from prep_crops import tile_frame, tiles_with_target
    tiles = tile_frame()
    xs = sorted({x for x, _ in tiles})
    ys = sorted({y for _, y in tiles})
    for dim, starts, limit in ((0, xs, W), (1, ys, H)):
        for w in range(1, 201):
            pos = set(range(0, limit - w + 1, 37)) | {limit - w}
            for s in starts:
                for d in (-1, 0, 1, C - w - 1, C - w, C - w + 1):
                    pos.add(min(max(s + d, 0), limit - w))
            for p in pos:
                box = (p, 0, p + w, 1) if dim == 0 else (0, p, 1, p + w)
                assert tiles_with_target(box, tiles), (dim, p, w)


def test_every_target_up_to_200px_random_2d():
    from prep_crops import tile_frame, tiles_with_target
    tiles = tile_frame()
    rng = random.Random(0)
    for _ in range(400):
        w, h = rng.uniform(1, 200), rng.uniform(1, 200)
        x1, y1 = rng.uniform(0, W - w), rng.uniform(0, H - h)
        assert tiles_with_target((x1, y1, x1 + w, y1 + h), tiles), (x1, y1, w, h)


def test_crop_to_frame_adds_offset():
    from prep_crops import crop_to_frame
    assert crop_to_frame((100, 200, 160, 240), 1000, 300) == pytest.approx((1100, 500, 1160, 540))
    assert crop_to_frame((0, 0, 10, 10), 0, 0) == pytest.approx((0, 0, 10, 10))


def test_merge_detections_nms_across_tiles_hand_computed():
    from prep_crops import merge_detections
    a = (0, 0, 100, 100, 0.9)
    b = (50, 0, 150, 100, 0.8)         # IoU(a, b) = 5000/15000 = 1/3
    c = (0, 0, 100, 100, 0.7)          # IoU(a, c) = 1
    d = (1000, 500, 1050, 540, 0.6)
    got = merge_detections([c, d, b, a], iou_thr=0.5)
    assert got == [a, b, d]            # giu cao nhat, xep theo conf giam dan
    assert merge_detections([c, d, b, a], iou_thr=0.2) == [a, d]     # b bi loai khi nguong 0,2
    assert merge_detections([], iou_thr=0.5) == []
    assert merge_detections([a], iou_thr=0.5) == [a]


def test_to_yolo_label_values():
    from prep_crops import to_yolo_label
    parts = to_yolo_label((100, 200, 160, 240)).split()
    assert parts[0] == "0"
    vals = [float(v) for v in parts[1:]]
    assert vals == pytest.approx([130 / 480, 220 / 480, 60 / 480, 40 / 480], abs=1e-6)
    assert all(0 <= v <= 1 for v in vals)
    full = [float(v) for v in to_yolo_label((0, 0, 480, 480), cls=2).split()]
    assert full == pytest.approx([2, 0.5, 0.5, 1.0, 1.0])


def test_make_positive_sample_end_to_end(tmp_path):
    from PIL import Image
    from prep_crops import make_positive_sample
    img = np.full((2160, 3840, 3), 60, np.uint8)
    img[956:1009, 2558:2646] = 255                     # may bay gia = o trang dung theo nhan
    p = tmp_path / "0_0_000001.jpg"
    Image.fromarray(img).save(p, quality=98)
    xml = tmp_path / "0_0_000001.xml"
    xml.write_text("""<annotation><object><name>Fixed_Wing_UAV</name><bndbox><xmax>2646</xmax><xmin>2558</xmin>
<ymax>1009</ymax><ymin>956</ymin></bndbox></object><size><depth>3</depth><height>2160</height><width>3840</width></size></annotation>""")
    s = make_positive_sample(str(p), str(xml), seed=4)
    assert s["image"].shape == (480, 480, 3)
    assert s["truncated"] is False
    x1, y1, x2, y2 = s["box"]
    assert x1 + 1 <= x2 and (x2 - x1) == pytest.approx(52.8, abs=1e-6)
    assert (y2 - y1) == pytest.approx(31.8, abs=1e-6)
    inner = s["image"][int(y1) + 3:int(y2) - 3, int(x1) + 3:int(x2) - 3]
    assert inner.min() >= 235                          # vung nhan that su chua o trang
    ring = s["image"].copy()
    ring[max(0, int(y1) - 6):int(y2) + 6, max(0, int(x1) - 6):int(x2) + 6] = 60
    assert ring.max() <= 70                            # ngoai nhan chi con nen
    v = [float(t) for t in s["label"].split()[1:]]
    assert v == pytest.approx([(x1 + x2) / 2 / 480, (y1 + y2) / 2 / 480, (x2 - x1) / 480, (y2 - y1) / 480], abs=1e-5)


# ---------------- vong 3: khung sat 480, khung vuot mep, frame_seed ----------------
def _feasible(box, frame_w=W, frame_h=H, size=C):
    import math
    xlo, xhi = math.ceil(max(0, box[2] - size)), math.floor(min(box[0], frame_w - size))
    ylo, yhi = math.ceil(max(0, box[3] - size)), math.floor(min(box[1], frame_h - size))
    return xlo <= xhi and ylo <= yhi


def _clamp_box(box):
    return (min(max(box[0], 0), W), min(max(box[1], 0), H), min(max(box[2], 0), W), min(max(box[3], 0), H))


NEAR_480 = [
    (100.6, 300, 580.3, 340),            # vi du cua 08: rong 479,7
    (100.5, 300, 580.5, 340),            # rong 480,0 bat dau o 100,5
    (100.25, 300, 579.25, 340),          # rong 479,0
    (100.25, 300, 579.75, 340),          # rong 479,5
    (100.75, 300, 580.75, 340),          # rong 480,0
    (3.3, 300, 483.7, 340),              # rong 480,4
    (300, 100.6, 340, 580.3),            # cung cac ca theo chieu doc
    (300, 100.5, 340, 580.5),
    (300, 3.3, 340, 483.7),
    (-5, 100, 45, 150),                  # vuot mep trai 5 px
    (2259, 1200, 2309, 1250),            # vuot mep phai/duoi 5 px
    (-5, -5, 475, 400),                  # vuot mep + rong 480
]


@pytest.mark.parametrize("box", NEAR_480)
@pytest.mark.parametrize("fn", ["positive_crop", "offcenter_crop"])
def test_crops_never_raise_near_480_or_outside_image(fn, box):
    import prep_crops
    f = getattr(prep_crops, fn)
    cb = _clamp_box(box)
    for seed in range(60):
        c = f(box, seed)                                   # khong bao gio nem loi
        assert inside_image(c)
        b = c["box"]
        assert all(0 <= v <= C for v in b)
        if c["truncated"]:
            assert not _feasible(cb)                       # chi cat khi that su khong co vi tri nguyen
        else:
            assert _feasible(cb)
            assert contains(c, cb)
            assert b == pytest.approx((cb[0] - c["x0"], cb[1] - c["y0"], cb[2] - c["x0"], cb[3] - c["y0"]))


def test_crop_08_examples_are_truncated_and_centred():
    from prep_crops import positive_crop
    c = positive_crop((100.6, 300, 580.3, 340), 1)
    assert c["truncated"] is True
    assert c["x0"] == 100                                  # tam x = 340,45 -> round(100,45)
    # khung bat dau 100,5 rong 480,0: khong co x0 nguyen chua tron
    assert positive_crop((100.5, 300, 580.5, 340), 1)["truncated"] is True
    # rong 479,0 bat dau 100,25: x0 = 100 chua tron -> khong cat
    assert positive_crop((100.25, 300, 579.25, 340), 1)["truncated"] is False


def test_box_beyond_image_edge_is_clamped_first_without_truncation():
    from prep_crops import positive_crop
    c = positive_crop((-5, 100, 45, 150), 2)
    assert c["x0"] == 0 and c["truncated"] is False
    assert c["box"] == pytest.approx((0, 100 - c["y0"], 45, 150 - c["y0"]))


def test_frame_seed_deterministic_distinct_and_int():
    from prep_crops import frame_seed
    s = frame_seed(7, "D/Top_Down", "0_0_000001")
    assert isinstance(s, int)
    assert s == frame_seed(7, "D/Top_Down", "0_0_000001")
    assert frame_seed(7, "D/Top_Down", "0_0_000002") != s
    assert frame_seed(7, "D'/Top_Down", "0_0_000001") != s
    assert frame_seed(8, "D/Top_Down", "0_0_000001") != s
    seeds = {frame_seed(0, "D/Top_Down", "0_0_%06d" % i) for i in range(1, 301)}
    assert len(seeds) == 300


def test_frame_seed_does_not_depend_on_python_hash_randomization():
    import os
    import subprocess
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    b1a = os.path.abspath(os.path.join(here, "..", "scripts", "b1a"))
    code = "import sys; sys.path.insert(0, %r); from prep_crops import frame_seed; print(frame_seed(3, \"E'/Top_Down\", '0_0_000009'))" % b1a
    outs = set()
    for hs in ("1", "2", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        outs.add(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                                check=True).stdout.strip())
    assert len(outs) == 1


def test_frame_seed_gives_spread_positions_over_300_consecutive_frames():
    from prep_crops import frame_seed, positive_crop
    a = [positive_crop(HAND_SCALED, frame_seed(0, "D/Top_Down", "0_0_%06d" % i)) for i in range(1, 301)]
    lefts = [c["box"][0] for c in a]
    tops = [c["box"][1] for c in a]
    assert min(lefts) < 40 and max(lefts) > 387
    assert min(tops) < 40 and max(tops) > 407 - 20
    assert len({c["x0"] for c in a}) >= 100


def test_make_positive_sample_returns_rgb_channel_order(tmp_path):
    from PIL import Image
    from prep_crops import make_positive_sample
    img = np.full((2160, 3840, 3), 0, np.uint8)
    img[956:1009, 2558:2646] = (255, 0, 0)             # do thuan theo RGB
    p = tmp_path / "0_0_000001.jpg"
    Image.fromarray(img).save(p, quality=98)
    xml = tmp_path / "0_0_000001.xml"
    xml.write_text("""<annotation><object><name>Fixed_Wing_UAV</name><bndbox><xmax>2646</xmax><xmin>2558</xmin>
<ymax>1009</ymax><ymin>956</ymin></bndbox></object><size><depth>3</depth><height>2160</height><width>3840</width></size></annotation>""")
    s = make_positive_sample(str(p), str(xml), seed=1)
    x1, y1, x2, y2 = s["box"]
    inner = s["image"][int(y1) + 3:int(y2) - 3, int(x1) + 3:int(x2) - 3]
    assert inner[..., 0].min() >= 235 and inner[..., 2].max() <= 30      # kenh 0 = R
