"""Test pha do cho vision/scripts/b1a/eval_metrics.py (cong thuc cham A1-A3).

Chu ky da chot (box = (x1, y1, x2, y2) o thang 2304; moi khung co dung 1 nhan):
  BANDS: "16-57" : 16 <= w < 57 ; "57-200" : 57 <= w <= 200 ; ">200" : w > 200 ; w < 16 -> None
  size_band(w) -> "16-57" | "57-200" | ">200" | None
  iou(a, b) -> float
  frame = {"seg": "E/Top_Down", "gt": box, "dets": [(x1, y1, x2, y2, conf), ...]}
  recall_by_band(frames, iou_thr=0.5, conf_thr=0.0) -> {band: {"n", "hit", "recall"(None neu n=0)}, "all": {...}}
        khung "trung" khi co >= 1 phat hien conf >= conf_thr va IoU >= iou_thr; "all" gom ca khung w < 16
  recall_with_spread(frames, band=None, iou_thr=0.5, conf_thr=0.0, n_boot=1000, seed=0, group_of=None,
                     min_groups=5)
        -> {"recall", "lo", "hi", "n_groups", "computable", "per_group"}
        recall = GOP THEO KHUNG (tong trung / tong khung trong dai); per_group = {nhom: recall} chi nhom co khung
        trong dai; khoang lo/hi = phan vi 2,5 / 97,5 cua bootstrap lay lai THEO NHOM (mac dinh nhom = seg);
        n_groups = so nhom CO DU LIEU trong dai dang xet; n_groups < min_groups -> computable False, lo = hi = None
  background_kind(direction) -> "sky" (Bottom_Up) | "ground" (Top_Down) | "mixed" (Horizontal); khac -> ValueError
  loss_runs(detected, fps) -> [do dai (giay) cua tung cum False lien tiep]
  loss_summary(detected, fps, short_s=0.25, long_s=3.0)
        -> {"n_short", "n_long", "longest_s", "per_minute", "duration_s"}   # so cum >= nguong ; per_minute = n_short / phut
  loss_summary_multi(list_of_detected, fps, ...) -> nhu tren, cum khong noi qua ranh gioi chuoi
  false_alarm_stats(crops, conf_thr, fps, crops_per_frame) -> {kind | "all": {"n_crops", "crops_with_fa",
                                                    "n_dets", "per_100", "per_second"}}   # fps, crops_per_frame BAT BUOC
        crop = {"kind": "sky" | "ground" | "mixed", "confs": [conf cua cac phat hien tren vung nen]}
        per_100 = 100 * crops_with_fa / n_crops (chi so chinh)
        per_second = crops_with_fa / n_crops * crops_per_frame * fps
"""
import pytest

GT = (100.0, 100.0, 200.0, 150.0)       # rong 100 -> dai 57-200


def box_w(w, x=100.0, y=100.0, h=20.0):
    return (x, y, x + w, y + h)


def fr(seg, gt=GT, dets=None):
    return {"seg": seg, "gt": gt, "dets": list(dets or [])}


# ---------------- A1 ----------------
@pytest.mark.parametrize("w,band", [
    (0.0, None), (15.99, None), (16.0, "16-57"), (56.99, "16-57"),
    (57.0, "57-200"), (100.0, "57-200"), (200.0, "57-200"), (200.01, ">200"), (1000.0, ">200")])
def test_size_band_edges(w, band):
    from eval_metrics import size_band
    assert size_band(w) == band


def test_iou_values():
    from eval_metrics import iou
    assert iou((0, 0, 100, 100), (0, 0, 100, 100)) == pytest.approx(1.0)
    assert iou((0, 0, 100, 100), (200, 200, 300, 300)) == 0.0
    assert iou((0, 0, 100, 100), (50, 0, 150, 100)) == pytest.approx(5000 / 15000)
    assert iou((0, 0, 100, 100), (0, 0, 50, 100)) == pytest.approx(0.5)


def test_recall_assigns_frames_to_bands_by_gt_width():
    from eval_metrics import recall_by_band
    frames = []
    for w in (16, 56, 57, 200, 201, 10):
        g = box_w(w)
        frames.append(fr("E/Top_Down", g, [g + (0.9,)]))
    r = recall_by_band(frames)
    assert r["16-57"]["n"] == 2 and r["57-200"]["n"] == 2 and r[">200"]["n"] == 1
    assert r["all"]["n"] == 6                          # khung w=10 chi nam o "all"
    assert r["16-57"]["recall"] == r["57-200"]["recall"] == r[">200"]["recall"] == 1.0


def test_recall_empty_band_is_none_not_zero():
    from eval_metrics import recall_by_band
    r = recall_by_band([fr("E/Top_Down", GT, [GT + (0.9,)])])
    assert r[">200"] == {"n": 0, "hit": 0, "recall": None}


def test_recall_iou_threshold_is_inclusive_at_0_5():
    from eval_metrics import recall_by_band
    g = (0.0, 0.0, 100.0, 100.0)
    just_ok = (0.0, 0.0, 50.0, 100.0, 0.9)             # IoU = 0,5 dung
    too_low = (0.0, 0.0, 49.0, 100.0, 0.9)             # IoU = 0,49
    r = recall_by_band([fr("s", g, [just_ok]), fr("s", g, [too_low])])
    assert r["57-200"]["hit"] == 1 and r["57-200"]["n"] == 2
    assert r["57-200"]["recall"] == pytest.approx(0.5)


def test_recall_duplicate_detections_count_once():
    from eval_metrics import recall_by_band
    d = [GT + (0.9,), GT + (0.8,), (101.0, 100.0, 201.0, 150.0, 0.7)]
    r = recall_by_band([fr("s", GT, d)])
    assert r["57-200"] == {"n": 1, "hit": 1, "recall": 1.0}
    assert r["all"]["hit"] == 1


def test_recall_confidence_threshold_applied_inclusively():
    from eval_metrics import recall_by_band
    low = [GT + (0.2,)]
    assert recall_by_band([fr("s", GT, low)], conf_thr=0.25)["all"]["hit"] == 0
    assert recall_by_band([fr("s", GT, low)], conf_thr=0.2)["all"]["hit"] == 1
    assert recall_by_band([fr("s", GT, low)], conf_thr=0.0)["all"]["hit"] == 1
    # phat hien tin cay thap bi bo, phat hien tin cay cao van ghi diem
    both = [GT + (0.2,), GT + (0.6,)]
    assert recall_by_band([fr("s", GT, both)], conf_thr=0.25)["all"]["hit"] == 1


def test_recall_wrong_location_is_a_miss():
    from eval_metrics import recall_by_band
    far = (500.0, 500.0, 600.0, 550.0, 0.99)
    assert recall_by_band([fr("s", GT, [far])])["all"]["recall"] == 0.0
    assert recall_by_band([fr("s", GT, [])])["all"]["recall"] == 0.0


def _six_segments(hits_per_seg, frames_per_seg=100):
    frames = []
    for i, h in enumerate(hits_per_seg):
        for k in range(frames_per_seg):
            ok = k < h
            frames.append(fr("E/seg%d" % i, GT, [GT + (0.9,)] if ok else []))
    return frames


def test_bootstrap_is_by_segment_not_by_frame():
    from eval_metrics import recall_with_spread
    frames = _six_segments([100, 100, 100, 0, 0, 0])   # 600 khung, 3 doan het, 3 doan mat
    r = recall_with_spread(frames, band="57-200", seed=1)
    assert r["recall"] == pytest.approx(0.5)
    assert r["computable"] is True and r["n_groups"] == 6
    # theo khung, khoang se hep ~ +-0,04; theo doan phai rong
    assert r["lo"] <= 0.34 and r["hi"] >= 0.66
    assert r["lo"] <= r["recall"] <= r["hi"]


def test_bootstrap_is_deterministic_with_seed():
    from eval_metrics import recall_with_spread
    frames = _six_segments([100, 90, 80, 70, 60, 50])
    a = recall_with_spread(frames, seed=7, n_boot=500)
    b = recall_with_spread(frames, seed=7, n_boot=500)
    assert a == b


def test_bootstrap_equal_segments_gives_degenerate_interval():
    from eval_metrics import recall_with_spread
    r = recall_with_spread(_six_segments([80] * 6), seed=0)
    assert r["recall"] == pytest.approx(0.8)
    assert r["lo"] == pytest.approx(0.8) and r["hi"] == pytest.approx(0.8)


def test_bootstrap_single_segment_is_not_computable():
    from eval_metrics import recall_with_spread
    frames = _six_segments([70])
    r = recall_with_spread(frames, seed=0)
    assert r["computable"] is False
    assert r["n_groups"] == 1
    assert r["lo"] is None and r["hi"] is None
    assert r["recall"] == pytest.approx(0.7)           # van tra diem so, khong tra khoang gia


def test_bootstrap_group_mapping_merges_segments_and_min_groups_applies():
    from eval_metrics import recall_with_spread
    frames = _six_segments([100, 100, 100, 0, 0, 0])
    two = {"E/seg0": "g1", "E/seg1": "g1", "E/seg2": "g1", "E/seg3": "g2", "E/seg4": "g2", "E/seg5": "g2"}
    r = recall_with_spread(frames, group_of=two, seed=0)
    assert r["n_groups"] == 2 and r["computable"] is False       # 2 < min_groups mac dinh 5
    assert r["lo"] is None and r["hi"] is None
    r2 = recall_with_spread(frames, group_of=two, seed=0, min_groups=2)
    assert r2["computable"] is True and r2["lo"] is not None
    one = {k: "g" for k in two}
    r1 = recall_with_spread(frames, group_of=one, seed=0, min_groups=1)
    assert r1["n_groups"] == 1 and r1["computable"] is True      # min_groups la tham so


def test_bootstrap_default_min_groups_is_5():
    from eval_metrics import recall_with_spread
    four = _six_segments([100, 80, 60, 40])
    five = _six_segments([100, 80, 60, 40, 20])
    assert recall_with_spread(four, seed=0)["computable"] is False
    assert recall_with_spread(five, seed=0)["computable"] is True


def test_point_estimate_is_pooled_by_frame_not_mean_of_groups():
    from eval_metrics import recall_with_spread
    frames = []
    for k in range(100):                               # nhom 0: 100 khung, trung het
        frames.append(fr("E/seg0", GT, [GT + (0.9,)]))
    for i in range(1, 6):                              # 5 nhom: 180 khung, khong trung
        frames += [fr("E/seg%d" % i, GT, []) for _ in range(180)]
    r = recall_with_spread(frames, seed=0)
    assert r["recall"] == pytest.approx(100 / 1000)    # trung binh nhom se la 1/6
    assert r["per_group"]["E/seg0"] == pytest.approx(1.0)
    assert r["per_group"]["E/seg3"] == pytest.approx(0.0)
    assert set(r["per_group"]) == {"E/seg%d" % i for i in range(6)}


def test_band_with_data_in_one_group_only_is_not_computable():
    from eval_metrics import recall_with_spread
    small = box_w(30.0)
    frames = _six_segments([100] * 6)                  # 6 nhom, dai 57-200
    frames += [fr("E/seg0", small, [small + (0.9,)]) for _ in range(50)]   # dai 16-57 chi o 1 nhom
    r = recall_with_spread(frames, band="16-57", seed=0)
    assert r["n_groups"] == 1 and r["computable"] is False and r["lo"] is None
    assert r["recall"] == pytest.approx(1.0)
    assert list(r["per_group"]) == ["E/seg0"]
    assert recall_with_spread(frames, band="57-200", seed=0)["computable"] is True


def test_bootstrap_band_filter_only_uses_that_band():
    from eval_metrics import recall_with_spread
    small = box_w(30.0)
    frames = _six_segments([100, 100]) + [fr("E/seg0", small, []), fr("E/seg1", small, [])]
    assert recall_with_spread(frames, band="57-200", seed=0)["recall"] == pytest.approx(1.0)
    assert recall_with_spread(frames, band="16-57", seed=0)["recall"] == pytest.approx(0.0)


# ---------------- A2 ----------------
def seq(*runs):
    out = []
    for val, n in runs:
        out += [val] * n
    return out


def test_loss_runs_in_seconds_including_edges():
    from eval_metrics import loss_runs
    s = seq((False, 5), (True, 10), (False, 2), (True, 3), (False, 12))
    assert loss_runs(s, fps=10) == pytest.approx([0.5, 0.2, 1.2])
    assert loss_runs([True] * 5, fps=10) == []
    assert loss_runs([False] * 25, fps=10) == pytest.approx([2.5])


def test_loss_summary_counts_thresholds_inclusively():
    from eval_metrics import loss_summary
    s = seq((False, 5), (True, 10), (False, 2), (True, 10), (False, 30), (True, 531), (False, 12))
    assert len(s) == 600
    r = loss_summary(s, fps=10)                       # 60 giay
    assert r["duration_s"] == pytest.approx(60.0)
    assert r["n_short"] == 3                          # 0,5 s ; 3,0 s ; 1,2 s (0,2 s khong du)
    assert r["n_long"] == 1                           # dung 3,0 s tinh la >= 3 s
    assert r["longest_s"] == pytest.approx(3.0)
    assert r["per_minute"] == pytest.approx(3.0)


def test_loss_summary_exactly_quarter_second_counts_and_just_below_does_not():
    from eval_metrics import loss_summary
    assert loss_summary(seq((True, 5), (False, 5), (True, 5)), fps=20)["n_short"] == 1    # 5/20 = 0,25 s
    assert loss_summary(seq((True, 5), (False, 4), (True, 5)), fps=20)["n_short"] == 0    # 0,20 s
    assert loss_summary(seq((True, 5), (False, 59), (True, 5)), fps=20)["n_long"] == 0    # 2,95 s
    assert loss_summary(seq((True, 5), (False, 60), (True, 5)), fps=20)["n_long"] == 1    # 3,00 s


def test_loss_summary_depends_on_frame_rate():
    from eval_metrics import loss_summary
    s = seq((True, 10), (False, 9), (True, 10))
    assert loss_summary(s, fps=30)["n_short"] == 1    # 0,3 s
    assert loss_summary(s, fps=60)["n_short"] == 0    # 0,15 s


def test_loss_summary_edge_cases_all_detected_and_all_lost():
    from eval_metrics import loss_summary
    ok = loss_summary([True] * 300, fps=30)
    assert (ok["n_short"], ok["n_long"], ok["longest_s"], ok["per_minute"]) == (0, 0, 0.0, 0.0)
    bad = loss_summary([False] * 300, fps=30)         # 10 s mat het
    assert bad["n_short"] == 1 and bad["n_long"] == 1
    assert bad["longest_s"] == pytest.approx(10.0)
    assert bad["per_minute"] == pytest.approx(6.0)


def test_loss_summary_rejects_bad_input():
    from eval_metrics import loss_summary
    with pytest.raises(ValueError):
        loss_summary([True, False], fps=0)
    with pytest.raises(ValueError):
        loss_summary([], fps=30)


def test_loss_summary_multi_does_not_join_runs_across_sequences():
    from eval_metrics import loss_summary_multi
    a = seq((True, 50), (False, 20))                  # 2,0 s o cuoi
    b = seq((False, 20), (True, 50))                  # 2,0 s o dau
    r = loss_summary_multi([a, b], fps=10)
    assert r["n_long"] == 0                           # neu noi nham se thanh 4,0 s
    assert r["longest_s"] == pytest.approx(2.0)
    assert r["n_short"] == 2
    assert r["duration_s"] == pytest.approx(14.0)
    assert r["per_minute"] == pytest.approx(2 / (14.0 / 60.0))


# ---------------- A3 ----------------
def crops(kind, n, with_fa):
    """with_fa: list so phat hien (conf) cho tung vung co bao dong; con lai khong co."""
    out = [{"kind": kind, "confs": list(c)} for c in with_fa]
    out += [{"kind": kind, "confs": []} for _ in range(n - len(with_fa))]
    return out


def test_false_alarm_per_100_and_per_second_split_by_kind():
    from eval_metrics import false_alarm_stats
    data = crops("ground", 200, [[0.9], [0.8, 0.6], [0.3]]) + crops("sky", 100, []) + crops("mixed", 50, [[0.5]])
    r = false_alarm_stats(data, conf_thr=0.25, fps=30, crops_per_frame=1)
    g = r["ground"]
    assert g["n_crops"] == 200 and g["crops_with_fa"] == 3 and g["n_dets"] == 4
    assert g["per_100"] == pytest.approx(1.5)
    assert g["per_second"] == pytest.approx(3 / 200 * 30)
    s = r["sky"]
    assert s["n_crops"] == 100 and s["crops_with_fa"] == 0 and s["per_100"] == 0.0 and s["per_second"] == 0.0
    assert r["mixed"]["per_100"] == pytest.approx(2.0)
    a = r["all"]
    assert a["n_crops"] == 350 and a["crops_with_fa"] == 4
    assert a["per_100"] == pytest.approx(100 * 4 / 350)


def test_false_alarm_confidence_threshold_is_applied():
    from eval_metrics import false_alarm_stats
    data = crops("ground", 100, [[0.2], [0.25], [0.9, 0.1]])
    r = false_alarm_stats(data, conf_thr=0.25, fps=30, crops_per_frame=1)["ground"]
    assert r["crops_with_fa"] == 2                    # 0,25 (>= nguong) va 0,9 ; 0,2 bi bo
    assert r["n_dets"] == 2
    assert false_alarm_stats(data, conf_thr=0.5, fps=30, crops_per_frame=1)["ground"]["crops_with_fa"] == 1
    assert false_alarm_stats(data, conf_thr=0.0, fps=30, crops_per_frame=1)["ground"]["n_dets"] == 4


def test_false_alarm_per_second_scales_with_fps_and_crops_per_frame():
    from eval_metrics import false_alarm_stats
    data = crops("ground", 100, [[0.9]])
    r30 = false_alarm_stats(data, conf_thr=0.25, fps=30, crops_per_frame=1)
    r10 = false_alarm_stats(data, conf_thr=0.25, fps=10, crops_per_frame=1)
    r_tiles = false_alarm_stats(data, conf_thr=0.25, fps=30, crops_per_frame=32)   # quet 32 o moi khung
    assert r30["ground"]["per_second"] == pytest.approx(0.3)
    assert r10["ground"]["per_second"] == pytest.approx(0.1)
    assert r_tiles["ground"]["per_second"] == pytest.approx(0.01 * 30 * 32)
    assert r_tiles["ground"]["per_100"] == pytest.approx(1.0)       # per_100 khong phu thuoc
    assert "sky" not in r30
    with pytest.raises(ValueError):
        false_alarm_stats([], conf_thr=0.25, fps=30, crops_per_frame=1)


def test_false_alarm_requires_fps_and_crops_per_frame():
    from eval_metrics import false_alarm_stats
    data = crops("ground", 10, [])
    with pytest.raises(TypeError):
        false_alarm_stats(data, conf_thr=0.25)
    with pytest.raises(TypeError):
        false_alarm_stats(data, conf_thr=0.25, fps=30)


def test_background_kind_follows_direction():
    from eval_metrics import background_kind
    assert background_kind("Bottom_Up") == "sky"
    assert background_kind("Top_Down") == "ground"
    assert background_kind("Horizontal") == "mixed"
    with pytest.raises(ValueError):
        background_kind("Sideways")


# ---------------- vong 3 ----------------
def test_box_format_conversion_hand_computed():
    from eval_metrics import xyxy_to_cxcywh, cxcywh_to_xyxy
    assert tuple(xyxy_to_cxcywh((10, 20, 50, 60))) == pytest.approx((30, 40, 40, 40))
    assert tuple(xyxy_to_cxcywh((1534.8, 573.6, 1587.6, 605.4))) == pytest.approx((1561.2, 589.5, 52.8, 31.8))
    assert tuple(cxcywh_to_xyxy((30, 40, 40, 20))) == pytest.approx((10, 30, 50, 50))
    # giu conf neu co phan tu thu 5
    assert tuple(xyxy_to_cxcywh((10, 20, 50, 60, 0.7))) == pytest.approx((30, 40, 40, 40, 0.7))
    assert tuple(cxcywh_to_xyxy((30, 40, 40, 20, 0.25))) == pytest.approx((10, 30, 50, 50, 0.25))
    assert len(xyxy_to_cxcywh((1, 2, 3, 4))) == 4 and len(xyxy_to_cxcywh((1, 2, 3, 4, 0.5))) == 5


def test_box_format_round_trip():
    import random
    from eval_metrics import xyxy_to_cxcywh, cxcywh_to_xyxy
    rng = random.Random(0)
    for _ in range(100):
        x1, y1 = rng.uniform(0, 2000), rng.uniform(0, 1000)
        d = (x1, y1, x1 + rng.uniform(1, 300), y1 + rng.uniform(1, 300), rng.random())
        assert tuple(cxcywh_to_xyxy(xyxy_to_cxcywh(d))) == pytest.approx(d)


def test_bootstrap_zero_resamples_is_not_computable_and_does_not_raise():
    from eval_metrics import recall_with_spread
    r = recall_with_spread(_six_segments([100, 80, 60, 40, 20, 0]), seed=0, n_boot=0)
    assert r["computable"] is False
    assert r["lo"] is None and r["hi"] is None
    assert r["recall"] == pytest.approx(300 / 600)
