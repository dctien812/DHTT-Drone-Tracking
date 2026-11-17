import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.range_estimator import RangeConfig, RangeEstimator
from dtrack.types import CameraModel

F = CameraModel().fx          # 2319 px (lens 8 mm)
SIZE = 0.30                   # m
DT = 1.0 / 30
WARMUP_S = 2.0


def run(range_fn, seed, duration=60.0, size_sigma=1.0, cfg=None):
    """Chay loc voi bbox vuong co nhieu size_sigma px len moi canh.
    Tra ve (sai so, sigma, sai so toc do) sau warmup."""
    rng = np.random.default_rng(seed)
    est = RangeEstimator(F, cfg or RangeConfig(target_size_m=SIZE, size_sigma_px=size_sigma))
    errs, sigmas, rate_errs = [], [], []
    n = int(duration / DT)
    for k in range(n):
        t = k * DT
        r, rr = range_fn(t)
        s = F * SIZE / r
        est.update(t, s + rng.normal(0, size_sigma), s + rng.normal(0, size_sigma))
        if t >= WARMUP_S:
            e = est.estimate(t)
            errs.append(e.range_m - r)
            sigmas.append(e.range_sigma_m)
            rate_errs.append(e.range_rate_mps - rr)
    return np.array(errs), np.array(sigmas), np.array(rate_errs)


def stats(range_fn, seeds=range(10), **kw):
    E, S, RE = [], [], []
    for sd in seeds:
        e, s, re = run(range_fn, sd, **kw)
        E.append(e); S.append(s); RE.append(re)
    E, S, RE = map(np.concatenate, (E, S, RE))
    return (float(np.sqrt(np.mean(E ** 2))), float(np.mean(E)),
            float(np.mean(np.abs(E) < 2 * S)), float(np.sqrt(np.mean(RE ** 2))), float(np.mean(S)))


@pytest.mark.parametrize("r0", [15.0, 30.0, 50.0])
def test_static_range_rms_and_sigma_coverage(r0):
    rms, bias, cover, rate_rms, mean_sigma = stats(lambda t: (r0, 0.0))
    print(f"\n[range static {r0:4.0f} m] RMS={rms:.3f} m ({100*rms/r0:.2f}%) bias={bias:+.3f} m "
          f"cover2sigma={cover:.3f} mean_sigma={mean_sigma:.3f} m rate_RMS={rate_rms:.3f} m/s")
    # Nguong dat sau khi do (RMS do duoc: 0.097 / 0.277 / 0.604 m), du ~40% du dia
    assert rms < {15.0: 0.14, 30.0: 0.40, 50.0: 0.85}[r0]
    assert cover >= 0.90


def test_range_tracks_closing_motion():
    # Khoang cach doi 50 -> 15 m trong 60 s (toc do -0.58 m/s) roi doi 0.58 m/s: bam duoc
    def fn(t):
        return 32.5 + 17.5 * np.cos(2 * np.pi * t / 60.0), -17.5 * 2 * np.pi / 60.0 * np.sin(2 * np.pi * t / 60.0)
    rms, bias, cover, rate_rms, mean_sigma = stats(fn, seeds=range(5))
    print(f"\n[range moving 15-50 m] RMS={rms:.3f} m bias={bias:+.3f} m cover2sigma={cover:.3f} "
          f"rate_RMS={rate_rms:.3f} m/s")
    assert cover >= 0.90
    assert rms < 1.5


def test_elongated_bbox_uses_larger_side():
    est = RangeEstimator(F, RangeConfig())
    size, _ = est.measure_size_px(46.0, 10.0)
    assert size == 46.0
    size, sig = est.measure_size_px(46.4, 46.0)   # vuong trong nhieu -> trung binh
    assert size == pytest.approx(46.2)
    assert sig < RangeConfig().size_sigma_px


def test_outlier_rejected_and_estimate_none_before_first():
    est = RangeEstimator(F, RangeConfig())
    assert est.estimate(0.0) is None
    s = F * SIZE / 30.0
    for k in range(60):
        est.update(k * DT, s, s)
    assert est.update(60 * DT, 2 * s, 2 * s) is False   # nhay 30 m -> 15 m bi bo
    assert est.estimate(60 * DT).range_m == pytest.approx(30.0, abs=0.1)
