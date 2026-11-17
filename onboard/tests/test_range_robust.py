"""Test do ben cua uoc luong khoang cach (T9c): dong nhanh, bbox bi cat o mep,
NaN, sai so he thong cua kich thuoc that. Lien quan tracker o test_tracker_robust.py."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.range_estimator import RangeConfig, RangeEstimator
from dtrack.types import CameraModel

CAM = CameraModel()
F = CAM.fx
SIZE = 0.30
DT = 1.0 / 30


def _valid(e):
    return e.valid


def closing_run(speed, r0, r_end, seed, size_sigma=1.0, cfg=None, true_size=SIZE):
    """r(t) = r0 - speed*t (speed < 0 la mo xa) toi khi cham r_end. Tra ve cac mau (r that, e)."""
    rng = np.random.default_rng(seed)
    est = RangeEstimator(F, cfg or RangeConfig(size_sigma_px=size_sigma), (CAM.width, CAM.height))
    out = []
    t = 0.0
    while True:
        r = r0 - speed * t
        if (speed > 0 and r < r_end) or (speed < 0 and r > r_end):
            break
        s = F * true_size / r
        est.update(t, s + rng.normal(0, size_sigma), s + rng.normal(0, size_sigma), CAM.cx, CAM.cy)
        e = est.estimate(t)
        out.append((r, e, speed))
        t += DT
    return out


def band_stats(samples, lo, hi):
    pts = [(e.range_m - r, e.range_sigma_m) for r, e, _ in samples if lo <= r < hi and _valid(e)]
    if not pts:
        return None
    err = np.array([p[0] for p in pts])
    sig = np.array([p[1] for p in pts])
    return dict(n=len(pts), bias=float(err.mean()), sigma=float(sig.mean()),
                cover=float(np.mean(np.abs(err) <= 2 * sig)))


CASES = [(30.0, 300.0, 10.0), (60.0, 300.0, 10.0), (100.0, 300.0, 10.0), (-30.0, 10.0, 300.0)]


@pytest.mark.parametrize("rel", [0.0, 0.25])
@pytest.mark.parametrize("speed,r0,r_end", CASES)
def test_fast_closing_range_is_honest(speed, r0, r_end, rel):
    """Dong/mo xa nhanh: tren mau range_valid, phu 2 sigma >= 90% va sai so TB <= +1 sigma TB."""
    cfg = RangeConfig(size_rel_sigma=rel)
    runs = [closing_run(speed, r0, r_end, sd, cfg=cfg) for sd in range(8)]
    samples = [s for run in runs for s in run]
    for lo, hi in ((10.0, 40.0), (40.0, 100.0)):
        st = band_stats(samples, lo, hi)
        print(f"\n[closing {speed:+.0f} m/s rel={rel} band {lo:.0f}-{hi:.0f}] {st}")
        assert st is not None and st["n"] > 20, "khong co mau hop le trong dai"
        assert st["cover"] >= 0.90
        assert st["bias"] <= 1.0 * st["sigma"]
    # range_valid phai len True truoc khi muc tieu vao 100 m
    first_valid = next(r for r, e, _ in runs[0] if _valid(e))
    assert first_valid > 100.0 or speed < 0


def test_valid_false_until_converged():
    est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
    s = F * SIZE / 30.0
    assert est.estimate(0.0) is None
    est.update(0.0, s, s, CAM.cx, CAM.cy)
    assert est.estimate(0.0).valid is False       # moi 1 mau
    for k in range(1, 40):
        est.update(k * DT, s, s, CAM.cx, CAM.cy)
    assert est.estimate(39 * DT).valid is True
    assert est.estimate(39 * DT + 2.0).valid is False   # 2 s khong do: het hieu luc


# ---------------- bbox bi cat o mep ----------------
def _clip(cx, cy, w, h):
    x0, x1 = max(0.0, cx - w / 2), min(float(CAM.width), cx + w / 2)
    y0, y1 = max(0.0, cy - h / 2), min(float(CAM.height), cy + h / 2)
    return (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


def test_corner_clipped_bbox_does_not_update_range():
    est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
    s = F * SIZE / 30.0
    for k in range(60):
        est.update(k * DT, s, s, CAM.cx, CAM.cy)
    before = est.estimate(60 * DT)
    cx, cy, w, h = _clip(CAM.width - 0.5, CAM.height - 0.5, s, s)
    for k in range(60, 120):
        assert est.update(k * DT, w, h, cx, cy) is False
    after = est.estimate(120 * DT)
    assert after.range_m == pytest.approx(before.range_m, abs=0.5)   # khong bi keo ra 60 m
    assert after.range_sigma_m > before.range_sigma_m
    assert after.valid is False


def test_one_edge_clipped_uses_other_edge():
    est = RangeEstimator(F, RangeConfig(size_rel_sigma=0.0), (CAM.width, CAM.height))
    rng = np.random.default_rng(3)
    s = F * SIZE / 30.0
    errs = []
    for k in range(150):
        # tam sat mep PHAI, giua chieu cao: chi w bi cat (con mot nua)
        cx, cy, w, h = _clip(CAM.width - 1.0, CAM.cy, s + rng.normal(0, 1), s + rng.normal(0, 1))
        est.update(k * DT, w, h, cx, cy)
        if k > 60:
            e = est.estimate(k * DT)
            errs.append((e.range_m - 30.0, e.range_sigma_m, e.valid))
    assert all(v for _, _, v in errs)
    assert np.mean([abs(a) <= 2 * b for a, b, _ in errs]) >= 0.9
    assert abs(np.mean([a for a, _, _ in errs])) < 1.0


def test_clipped_long_side_with_short_unclipped_side_is_skipped():
    # bbox dai theo chieu bi cat (w cat con 30 px, h = 5 px khong cat): khong du de do
    est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
    assert est.update(0.0, 30.0, 5.0, CAM.width - 15.0, CAM.cy) is False
    assert est.estimate(0.0) is None


# ---------------- NaN / vo han ----------------
@pytest.mark.parametrize("bad", [(math.nan, math.nan), (math.inf, 20.0), (20.0, -math.inf)])
def test_nonfinite_bbox_ignored_and_filter_survives(bad):
    est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
    s = F * SIZE / 30.0
    for k in range(40):
        est.update(k * DT, s, s, CAM.cx, CAM.cy)
    assert est.update(40 * DT, bad[0], bad[1], CAM.cx, CAM.cy) is False
    for k in range(41, 60):
        est.update(k * DT, s, s, CAM.cx, CAM.cy)
    e = est.estimate(60 * DT)
    assert math.isfinite(e.range_m) and abs(e.range_m - 30.0) < 1.0
    assert math.isfinite(e.range_sigma_m) and e.valid


def test_nan_state_self_heals():
    est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
    s = F * SIZE / 30.0
    for k in range(40):
        est.update(k * DT, s, s, CAM.cx, CAM.cy)
    est._x = np.array([math.nan, math.nan])      # gia lap trang thai hong
    e = est.estimate(41 * DT)
    assert e is None or (math.isfinite(e.range_m) and not e.valid)
    for k in range(41, 80):
        est.update(k * DT, s, s, CAM.cx, CAM.cy)
    e = est.estimate(80 * DT)
    assert math.isfinite(e.range_m) and abs(e.range_m - 30.0) < 1.5 and e.valid


# ---------------- sai so he thong kich thuoc ----------------
def test_size_systematic_error_inside_published_2sigma():
    """Muc tieu that 0.45 m (gia dinh 0.30) o 30 m: sai so that nam trong 2 sigma cong bo."""
    # Luu y: 0.45/0.30 = +50% = dung +2 sigma_size (0.25), nen sai so ~ 2 sigma cong bo, sat bien.
    # Sai so he thong la hang so nen so sanh trung binh theo thoi gian (khong theo tung mau).
    assert RangeConfig().size_rel_sigma == pytest.approx(0.25)
    for sd in range(6):
        rng = np.random.default_rng(sd)
        est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
        s = F * 0.45 / 30.0
        errs, sigs = [], []
        for k in range(300):
            est.update(k * DT, s + rng.normal(0, 1), s + rng.normal(0, 1), CAM.cx, CAM.cy)
            if k > 60:
                e = est.estimate(k * DT)
                errs.append(e.range_m - 30.0)
                sigs.append(e.range_sigma_m)
        assert abs(np.mean(errs)) <= 2 * np.mean(sigs), (np.mean(errs), np.mean(sigs))
        assert abs(np.mean(errs)) > 5.0     # sai so that su ton tai (khong phai test vo nghia)
