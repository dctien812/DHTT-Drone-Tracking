"""Kich ban mo phong: muc tieu bay 20 m/s co doi huong, drone bam bay theo sau
(tre 0.9-2.6 s doc quy dao muc tieu -> cach ~18-52 m), huong mui luon ngam ve
muc tieu that cong them lac +-10 do (roll/pitch/yaw) o 1 Hz. Detector tong hop:
nhieu tam 1.5 px, bo sot 20%, gia 5%/khung, tre 60 ms, 30 Hz.
"""
import math
import os
import sys
from functools import lru_cache

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.geometry import angle_between, quat_from_euler
from dtrack.synthetic import SyntheticConfig, SyntheticDetector
from dtrack.tracker import SingleTargetTracker, TrackerConfig
from dtrack.types import CameraModel, OwnState, TrackStatus

CAM = CameraModel()
HZ = 30.0
DT = 1.0 / HZ
D2R = math.pi / 180.0
WOBBLE = 10.0 * D2R


@lru_cache(maxsize=1)
def _target_path():
    t = np.arange(-6.0, 75.0, 0.005)
    psi = 0.8 * np.sin(2 * np.pi * t / 24.0) + 0.2 * np.sin(2 * np.pi * t / 7.0)
    gam = 0.1 * np.sin(2 * np.pi * t / 13.0)
    v = 20.0 * np.stack([np.cos(gam) * np.cos(psi), np.cos(gam) * np.sin(psi), -np.sin(gam)], axis=1)
    p = np.vstack([[0, 0, -50.0], np.cumsum(0.5 * (v[1:] + v[:-1]) * 0.005, axis=0) + [0, 0, -50.0]])
    return t, p


def target_pos(t):
    ts, p = _target_path()
    return np.array([np.interp(t, ts, p[:, i]) for i in range(3)])


def chaser_pos(t):
    return target_pos(t - (1.75 + 0.85 * math.sin(2 * math.pi * t / 17.0)))


def own_state(t):
    pos = chaser_pos(t)
    vel = (chaser_pos(t + 0.01) - chaser_pos(t - 0.01)) / 0.02
    d = target_pos(t) - pos
    yaw0 = math.atan2(d[1], d[0])
    pitch0 = math.atan2(-d[2], math.hypot(d[0], d[1]))
    w = 2 * math.pi * t
    q = quat_from_euler(WOBBLE * math.sin(w), pitch0 + WOBBLE * math.sin(w + 1.0),
                        yaw0 + WOBBLE * math.sin(w + 2.0))
    return OwnState(t=t, pos_ned=tuple(pos), vel_ned=tuple(vel), q_world_body=tuple(q))


def simulate(duration=60.0, seed=1, blackout=None, det_cfg=None, trk_cfg=None):
    det = SyntheticDetector(CAM, det_cfg or SyntheticConfig(seed=seed))
    trk = SingleTargetTracker(CAM, trk_cfg)
    recs = []
    for k in range(int(duration * HZ)):
        t = k * DT
        own = own_state(t)
        dets = det.process(t, target_pos(t), own)
        if blackout and blackout[0] <= t < blackout[1]:
            dets = []
        st = trk.update(dets, own, t)
        d = target_pos(t) - np.array(own.pos_ned)
        rng_true = float(np.linalg.norm(d))
        err = angle_between(st.los_ned, d) if st.los_ned is not None else None
        recs.append(dict(t=t, st=st, err=err, rng=rng_true))
    return recs


def metrics(recs):
    tr = [r for r in recs if r["st"].status == TrackStatus.TRACK]
    errs = np.array([r["err"] for r in tr])
    rms_deg = float(np.degrees(np.sqrt(np.mean(errs ** 2))))
    # thoi gian lien tuc dai nhat o TRACK ma sai so > 2 do (bam nham)
    worst = run_len = 0
    for r in recs:
        if r["st"].status == TrackStatus.TRACK and r["err"] > 2.0 * D2R:
            run_len += 1
            worst = max(worst, run_len)
        else:
            run_len = 0
    return dict(rms_deg=rms_deg, track_frac=len(tr) / len(recs), wrong_s=worst * DT,
                max_err_deg=float(np.degrees(errs.max())))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_scenario_rms_and_no_false_lock(seed):
    recs = simulate(seed=seed)
    ranges = [r["rng"] for r in recs]
    m = metrics(recs)
    rr = [r["st"] for r in recs if r["st"].status == TrackStatus.TRACK and r["st"].range_m]
    rerr = [s.range_m - r["rng"] for r, s in zip(recs, [r["st"] for r in recs]) if s.range_m and s.status == TrackStatus.TRACK]
    print(f"\n[scenario seed={seed}] range {min(ranges):.1f}-{max(ranges):.1f} m  {m}  "
          f"range_err_RMS={np.sqrt(np.mean(np.square(rerr))):.2f} m")
    assert min(ranges) > 14.0 and max(ranges) < 55.0
    assert m["rms_deg"] < 0.5
    assert m["wrong_s"] <= 0.5
    assert m["track_frac"] > 0.9


def test_blackout_1s_coasts_then_reacquires():
    recs = simulate(duration=40.0, blackout=(20.0, 21.0))
    win = [r["st"].status for r in recs if 20.5 <= r["t"] < 21.0]
    assert all(s == TrackStatus.COAST for s in win)
    assert not any(r["st"].status == TrackStatus.LOST for r in recs if 20 <= r["t"] < 22)
    after = [r for r in recs if 21.0 <= r["t"] < 22.5]
    first = next(r["t"] for r in after if r["st"].status == TrackStatus.TRACK)
    print(f"\n[blackout 1 s] re-TRACK {first - 21.0:.2f} s after blackout end")
    assert first - 21.0 < 1.0
    # sau khi bat lai, dung muc tieu that
    r = next(r for r in recs if r["t"] >= 23.0)
    assert r["st"].status == TrackStatus.TRACK and r["err"] < 0.5 * D2R


def test_blackout_5s_goes_lost():
    recs = simulate(duration=40.0, blackout=(20.0, 25.0))
    sts = {r["t"]: r["st"].status for r in recs}
    lost_t = [t for t, s in sts.items() if s == TrackStatus.LOST]
    assert lost_t and 22.9 < min(lost_t) < 24.0
    # khong con TRACK/COAST tu luc LOST toi het mat do
    assert all(s not in (TrackStatus.TRACK, TrackStatus.COAST) for t, s in sts.items() if min(lost_t) <= t < 25.0)
    assert any(r["st"].status == TrackStatus.TRACK for r in recs if r["t"] > 28.0)


def test_search_before_confirm_and_output_fields():
    recs = simulate(duration=5.0)
    assert recs[0]["st"].status == TrackStatus.SEARCH and recs[0]["st"].los_ned is None
    tr = next(r["st"] for r in recs if r["st"].status == TrackStatus.TRACK)
    assert tr.los_rate_ned is not None and tr.range_m and tr.range_sigma_m and tr.predicted_px is not None
    assert abs(np.linalg.norm(tr.los_ned) - 1.0) < 1e-9
    assert tr.age_s >= 0.0


def test_low_confidence_ignored():
    trk = SingleTargetTracker(CAM, TrackerConfig(min_conf=0.5))
    from dtrack.types import Detection
    own = own_state(0.0)
    st = trk.update([Detection(0.0, 728, 544, 20, 20, 0.3)], own, 0.05)
    assert st.status == TrackStatus.SEARCH and st.los_ned is None


def test_synthetic_detector_statistics_latency_and_fov():
    cfg = SyntheticConfig(seed=5, p_miss=0.2, p_false=0.05, latency_s=0.06)
    det = SyntheticDetector(CAM, cfg)
    own = OwnState(t=0.0, pos_ned=(0.0, 0.0, 0.0), vel_ned=(0.0, 0.0, 0.0), q_world_body=(1.0, 0.0, 0.0, 0.0))
    n_true = n_false = n_frames = 0
    for k in range(6000):
        t = k * DT
        out = det.process(t, (30.0, 0.0, 0.0), own)   # thang truoc mui
        for d in out:
            # tra ra o buoc dau tien >= t_capture + latency (luoi 30 Hz nen lam tron len)
            assert 0.06 - 1e-6 <= t - d.t_capture < 0.06 + DT
            if abs(d.cx - CAM.cx) < 15 and abs(d.cy - CAM.cy) < 15:
                n_true += 1
            else:
                n_false += 1
        n_frames += 1
    assert 0.76 < n_true / n_frames < 0.84
    assert 0.03 < n_false / n_frames < 0.07
    # muc tieu sau camera hoac ngoai khung: khong sinh phat hien that
    det = SyntheticDetector(CAM, SyntheticConfig(seed=5, p_miss=0.0, p_false=0.0))
    for k in range(100):
        assert det.process(k * DT, (-30.0, 0.0, 0.0), own) == []
        assert det.process(k * DT + 1e-3, (30.0, 30.0, 0.0), own) == []


def test_deterministic_with_seed():
    a = simulate(duration=5.0, seed=7)
    b = simulate(duration=5.0, seed=7)
    assert [r["err"] for r in a] == [r["err"] for r in b]
