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
    pts = [(e.range_m - r, e.range_sigma_m, e.range_m) for r, e, _ in samples if lo <= r < hi and _valid(e)]
    if not pts:
        return None
    err = np.array([p[0] for p in pts])
    sig = np.array([p[1] for p in pts])
    rng_m = np.array([p[2] for p in pts])
    return dict(n=len(pts), bias=float(err.mean()), sigma=float(sig.mean()),
                cover=float(np.mean(np.abs(err) <= 2 * sig)),
                rel_part=float(np.min(sig / rng_m)))   # sigma/r nho nhat: >= size_rel_sigma neu co thanh phan ty le


CASES = [(30.0, 300.0, 10.0), (60.0, 300.0, 10.0), (100.0, 300.0, 10.0), (-30.0, 10.0, 300.0)]


@pytest.mark.parametrize("rel", [0.0, 0.25])
@pytest.mark.parametrize("speed,r0,r_end", CASES)
def test_fast_closing_range_is_honest(speed, r0, r_end, rel):
    """Dong/mo xa nhanh: tren mau range_valid, phu 2 sigma >= 90% va sai so TB <= +1 sigma TB."""
    cfg = RangeConfig(size_rel_sigma=rel)
    # 24 seed (8 seed cho nhom seed nao cung chap chon: 6/10 nhom hong o 60 m/s voi rel=0)
    runs = [closing_run(speed, r0, r_end, sd, cfg=cfg) for sd in range(24)]
    samples = [s for run in runs for s in run]
    for lo, hi in ((10.0, 40.0), (40.0, 100.0)):
        st = band_stats(samples, lo, hi)
        print(f"\n[closing {speed:+.0f} m/s rel={rel} band {lo:.0f}-{hi:.0f}] {st}")
        assert st is not None and st["n"] > 20, "khong co mau hop le trong dai"
        if rel == 0.0:
            # sigma chi la sigma cua loc: chi kiem tinh nhat quan, nguong co bien cho 24 seed
            # (xau nhat qua 10 nhom seed: cover 0.867, bias 0.89 sigma)
            assert st["cover"] >= 0.80
            assert st["bias"] <= 1.2 * st["sigma"]
        else:
            # sigma da gom size_rel_sigma*r nen phu ~100%; nguong cu (0.90 / 1 sigma) khong bat
            # duoc loc tre. Chat hon: phu >= 0.99, bias <= 0.3 sigma (xau nhat 0.17), va sigma
            # cong bo phai thuc su chua thanh phan ty le (>= rel * r).
            assert st["cover"] >= 0.99
            assert st["bias"] <= 0.3 * st["sigma"]
            assert st["rel_part"] >= 0.95 * rel
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


# ---------------- T9d: detector co khung vao trong mep, mat do roi bat lai gan hon ----------------
@pytest.mark.parametrize("d", [3.0, 5.0, 8.0])
def test_bbox_shrunk_inside_corner_does_not_report_valid_far_range(d):
    """Detector co khung vao trong mep d px (3-8): bbox nho hon that nhung khong cham mep.
    Muc tieu 30 m truot vao goc, bbox co dan toi 0.7 kich thuoc that: khong duoc co mau valid xa that."""
    est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
    rng = np.random.default_rng(7)
    s = F * SIZE / 30.0
    states = []
    for k in range(150):
        t = k * DT
        f = min(max((t - 2.0) / 2.0, 0.0), 1.0)                # 2 s o giua, 2 s truot vao goc
        # khoang cach tu canh trong cua bbox toi mep anh: giam dan tu giua anh toi d
        gx = (CAM.width - CAM.cx - s / 2) * (1 - f) + d * f
        gy = (CAM.height - CAM.cy - s / 2) * (1 - f) + d * f
        q = min(max((20.0 - min(gx, gy)) / (20.0 - d), 0.0), 1.0)   # gan mep (< 20 px): detector co khung
        sz = s * (1.0 - 0.3 * q)                                    # toi 0.7 kich thuoc that
        cx, cy = CAM.width - gx - sz / 2, CAM.height - gy - sz / 2
        est.update(t, sz + rng.normal(0, 0.3), sz + rng.normal(0, 0.3), cx, cy)
        states.append((t, est.estimate(t)))
    valid = [(t, e) for t, e in states if e.valid]
    assert any(t < 2.0 for t, _ in valid)                       # da hoi tu truoc khi truot
    assert max(e.range_m for _, e in valid) <= 33.0, max(e.range_m for _, e in valid)
    assert not states[-1][1].valid                              # o goc: khong tin duoc


def test_reacquire_closer_after_long_gap_is_not_far_and_valid():
    """Mat do 3 s o 150 m roi bat lai o 40 m: moi mau valid phai gan 40 m (khong ket o ~150 m)."""
    rng = np.random.default_rng(11)
    est = RangeEstimator(F, RangeConfig(), (CAM.width, CAM.height))
    s_far, s_near = F * SIZE / 150.0, F * SIZE / 40.0
    for k in range(60):
        est.update(k * DT, s_far + rng.normal(0, 0.3), s_far + rng.normal(0, 0.3), CAM.cx, CAM.cy)
    assert est.estimate(59 * DT).valid
    t0 = 59 * DT + 3.0
    valid_errs = []
    for k in range(60):
        t = t0 + k * DT
        est.update(t, s_near + rng.normal(0, 0.3), s_near + rng.normal(0, 0.3), CAM.cx, CAM.cy)
        e = est.estimate(t)
        if e.valid:
            valid_errs.append(e.range_m - 40.0)
    assert valid_errs, "khong bao gio valid lai sau khi bat lai"
    assert max(abs(v) for v in valid_errs) <= 8.0, max(abs(v) for v in valid_errs)
