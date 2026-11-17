"""Test do ben cua tracker (T9c): bbox cat o mep, NaN, dong ho lui/tuong lai, quaternion hong,
nhieu tu the FC, muc tieu gan mep khung."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.geometry import angle_between, pixel_to_ray_cam, quat_from_euler, quat_multiply, ray_cam_to_ned
from dtrack.synthetic import SyntheticConfig, SyntheticDetector
from dtrack.tracker import SingleTargetTracker, TrackerConfig
from dtrack.types import CameraModel, Detection, OwnState, TrackStatus
from test_tracker import chaser_pos, target_pos   # quy dao muc tieu/drone bam dung chung

CAM = CameraModel()
DT = 1.0 / 30
D2R = math.pi / 180.0
Q0 = (1.0, 0.0, 0.0, 0.0)


def own_at(t, q=Q0):
    return OwnState(t=t, pos_ned=(0.0, 0.0, 0.0), vel_ned=(0.0, 0.0, 0.0), q_world_body=q)


def clip(cx, cy, w, h):
    x0, x1 = max(0.0, cx - w / 2), min(float(CAM.width), cx + w / 2)
    y0, y1 = max(0.0, cy - h / 2), min(float(CAM.height), cy + h / 2)
    return (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


def static_det(t, u, v, r, rng, size=0.30):
    s = CAM.fx * size / r
    cx, cy, w, h = clip(u + rng.normal(0, 0.5), v + rng.normal(0, 0.5),
                        s + rng.normal(0, 1), s + rng.normal(0, 1))
    return Detection(t, cx, cy, w, h, 0.8)


# ---------------- 1. bbox cat o goc anh ----------------
def test_corner_clipped_bbox_never_reports_valid_far_range():
    rng = np.random.default_rng(1)
    trk = SingleTargetTracker(CAM)
    u1, v1 = CAM.width - 0.5, CAM.height - 0.5
    states = []
    for k in range(int(3.5 * 30)):
        t = k * DT
        f = min(max((t - 0.5) / 1.0, 0.0), 1.0)          # giu 0.5 s, truot 1 s, giu 2 s
        u, v = CAM.cx + f * (u1 - CAM.cx), CAM.cy + f * (v1 - CAM.cy)
        states.append((t, trk.update([static_det(t, u, v, 30.0, rng)], own_at(t), t)))
    valid = [(t, s) for t, s in states if s.range_valid]
    assert valid, "range_valid khong bao gio True (khong hoi tu) "
    assert any(t < 1.5 for t, _ in valid)
    assert all(s.range_m <= 36.0 for _, s in valid), max(s.range_m for _, s in valid)
    assert all(not s.range_valid for t, s in states if t >= 3.0)   # bi cat 2 s: het hieu luc


def test_range_valid_is_set_in_every_branch():
    trk = SingleTargetTracker(CAM)
    st = trk.update([], own_at(0.0), 0.0)
    assert st.status == TrackStatus.SEARCH and st.range_valid is False
    rng = np.random.default_rng(2)
    sts = [trk.update([static_det(k * DT, CAM.cx, CAM.cy, 30.0, rng)], own_at(k * DT), k * DT)
           for k in range(60)]
    assert sts[-1].status == TrackStatus.TRACK and sts[-1].range_valid is True
    # mat do 1 s: COAST va het hieu luc
    st = trk.update([], own_at(60 * DT + 1.0), 60 * DT + 1.0)
    assert st.status == TrackStatus.COAST and st.range_valid is False
    # LOST
    st = trk.update([], own_at(60 * DT + 5.0), 60 * DT + 5.0)
    assert st.status == TrackStatus.LOST and st.range_valid is False


# ---------------- 3. NaN ----------------
def _track_up(trk, n=60, seed=4):
    rng = np.random.default_rng(seed)
    for k in range(n):
        trk.update([static_det(k * DT, CAM.cx, CAM.cy, 30.0, rng)], own_at(k * DT), k * DT)
    return rng


def test_nan_bbox_in_track_does_not_poison_range():
    trk = SingleTargetTracker(CAM)
    rng = _track_up(trk)
    t = 60 * DT
    bad = Detection(t, CAM.cx, CAM.cy, math.nan, math.nan, 0.8)
    st = trk.update([bad], own_at(t), t)
    for k in range(61, 120):
        t = k * DT
        st = trk.update([static_det(t, CAM.cx, CAM.cy, 30.0, rng)], own_at(t), t)
    assert st.status == TrackStatus.TRACK
    assert st.range_m is not None and math.isfinite(st.range_m) and abs(st.range_m - 30.0) < 1.5
    assert math.isfinite(st.range_sigma_m) and st.range_valid
    assert trk.stats.bad_detections >= 1


@pytest.mark.parametrize("field", ["t_capture", "cx", "cy", "w", "h", "conf"])
@pytest.mark.parametrize("val", [math.nan, math.inf, -math.inf])
def test_any_nonfinite_detection_field_is_dropped(field, val):
    trk = SingleTargetTracker(CAM)
    rng = _track_up(trk)
    t = 60 * DT
    d = static_det(t, CAM.cx, CAM.cy, 30.0, rng)
    d = Detection(**{**d.__dict__, field: val})
    st = trk.update([d], own_at(t), t)
    assert st.status in (TrackStatus.TRACK, TrackStatus.COAST)
    assert all(math.isfinite(c) for c in st.los_ned)
    assert math.isfinite(st.range_m) and math.isfinite(st.predicted_px[0])
    assert trk.stats.bad_detections == 1


# ---------------- 4. dong ho / timestamp ----------------
def test_pose_buffer_recovers_after_clock_jump_back():
    trk = SingleTargetTracker(CAM)
    trk.update([], own_at(1000.0, (1.0, 0.0, 0.0, 0.0)), 1000.0)
    q_new = tuple(quat_from_euler(0.0, 0.0, 0.5))
    for k in range(60):
        t = 1.0 + k * 0.05                      # 1.0 .. 3.95
        trk.update([], own_at(t, q_new), t)
    q = trk._attitude_at(3.0)
    assert np.allclose(q, q_new, atol=1e-9)
    assert trk.stats.own_clock_resets == 1


def test_future_pose_sample_is_dropped():
    trk = SingleTargetTracker(CAM)
    q_good = tuple(quat_from_euler(0.0, 0.0, 0.5))
    trk.update([], own_at(1.0, q_good), 1.0)
    trk.update([], own_at(1000.0, Q0), 1.05)     # tem thoi gian tuong lai bat thuong
    trk.update([], own_at(1.1, q_good), 1.1)
    assert np.allclose(trk._attitude_at(1.1), q_good)
    assert trk.stats.own_future_dropped == 1


def test_clock_jump_back_resets_track_instead_of_freezing():
    trk = SingleTargetTracker(CAM)
    _track_up(trk)
    t0 = 60 * DT
    rng = np.random.default_rng(9)
    st = None
    for k in range(60):                          # dong ho nhay ve 0 (khoi dong lai FC)
        t = 0.0 + k * DT
        st = trk.update([static_det(t, CAM.cx, CAM.cy, 30.0, rng)], own_at(t), t)
    assert t0 > 1.0 and st.status == TrackStatus.TRACK and st.range_valid
    assert st.age_s < 0.1


# ---------------- 7. quaternion hong / dau vao tuy y ----------------
@pytest.mark.parametrize("q", [(0.0, 0.0, 0.0, 0.0), (math.nan, 0.0, 0.0, 1.0),
                               (1.0, math.inf, 0.0, 0.0), (1e-9, 0.0, 0.0, 0.0)])
def test_bad_quaternion_dropped_without_exception(q):
    trk = SingleTargetTracker(CAM)
    rng = _track_up(trk)
    t = 60 * DT
    st = trk.update([static_det(t, CAM.cx, CAM.cy, 30.0, rng)], own_at(t, q), t)
    assert st.status in (TrackStatus.TRACK, TrackStatus.COAST)
    assert all(math.isfinite(c) for c in st.los_ned)
    assert trk.stats.own_bad == 1


def test_bad_quaternion_before_any_good_sample_does_not_raise():
    trk = SingleTargetTracker(CAM)
    st = trk.update([Detection(0.0, 700.0, 500.0, 20.0, 20.0, 0.9)], own_at(0.0, (0, 0, 0, 0)), 0.0)
    assert st.status == TrackStatus.SEARCH and st.range_valid is False


def test_fuzz_arbitrary_numeric_inputs_never_raise():
    rng = np.random.default_rng(0)
    nasty = [0.0, -0.0, 1.0, -1.0, 1e-300, 1e300, -1e300, math.nan, math.inf, -math.inf, 1e6, 3.0]
    trk = SingleTargetTracker(CAM)
    t = 0.0
    for k in range(3000):
        pick = lambda: float(rng.choice(nasty)) if rng.random() < 0.3 else float(rng.normal(0, 400))
        t += DT if rng.random() < 0.9 else float(rng.choice(nasty[:6] + [-50.0, 50.0]))
        if rng.random() < 0.5:
            good = Detection(t, CAM.cx + rng.normal(0, 3), CAM.cy + rng.normal(0, 3), 23.0, 23.0, 0.8)
        else:
            good = None
        dets = []
        for _ in range(int(rng.integers(0, 3))):
            dets.append(Detection(pick() if rng.random() < .3 else t, pick(), pick(), pick(), pick(),
                                  pick() if rng.random() < .3 else 0.7))
        if good:
            dets.append(good)
        q = tuple(pick() if rng.random() < 0.3 else v for v in (1.0, 0.0, 0.0, 0.0))
        tn = t if rng.random() < 0.95 else pick()
        st = trk.update(dets, own_at(pick() if rng.random() < 0.1 else t, q), tn)
        for v in (st.los_ned or ()):
            assert math.isfinite(v)
        if st.range_valid:
            assert math.isfinite(st.range_m) and math.isfinite(st.range_sigma_m)


# ---------------- 6. nhieu tu the FC ----------------
def _true_own(t, wobble):
    pos = chaser_pos(t)
    vel = (chaser_pos(t + 0.01) - chaser_pos(t - 0.01)) / 0.02
    d = target_pos(t) - pos
    yaw0 = math.atan2(d[1], d[0])
    pitch0 = math.atan2(-d[2], math.hypot(d[0], d[1]))
    w = 2 * math.pi * t
    q = quat_from_euler(wobble * math.sin(w), pitch0 + wobble * math.sin(w + 1.0),
                        yaw0 + wobble * math.sin(w + 2.0))
    return OwnState(t=t, pos_ned=tuple(pos), vel_ned=tuple(vel), q_world_body=tuple(q))


def sim_noisy_attitude(att_sigma_deg, wobble_deg=10.0, seed=1, duration=40.0, trk_cfg=None):
    rng = np.random.default_rng(1000 + seed)
    det = SyntheticDetector(CAM, SyntheticConfig(seed=seed))
    trk = SingleTargetTracker(CAM, trk_cfg)
    n = tr = 0
    wrong = run = 0
    for k in range(int(duration * 30)):
        t = k * DT
        own = _true_own(t, wobble_deg * D2R)
        dets = det.process(t, target_pos(t), own)          # bo sinh dung tu the THAT
        dv = rng.normal(0, att_sigma_deg * D2R, 3)
        dq = np.array([1.0, *(0.5 * dv)])
        dq /= np.linalg.norm(dq)
        noisy = OwnState(t=t, pos_ned=own.pos_ned, vel_ned=own.vel_ned,
                         q_world_body=tuple(quat_multiply(dq, own.q_world_body)))
        st = trk.update(dets, noisy, t)
        n += 1
        if st.status == TrackStatus.TRACK:
            tr += 1
            err = angle_between(st.los_ned, target_pos(t) - np.array(own.pos_ned))
            run = run + 1 if err > 2.0 * D2R else 0
            wrong = max(wrong, run)
        else:
            run = 0
    return tr / n, wrong * DT


@pytest.mark.parametrize("att_deg,min_frac", [(0.5, 0.97), (1.0, 0.93)])
def test_attitude_noise_tolerated(att_deg, min_frac):
    res = [sim_noisy_attitude(att_deg, seed=sd) for sd in (1, 2, 3)]
    print(f"\n[attitude noise {att_deg} deg] TRACK frac / wrong_s per seed: {res}")
    for frac, wrong_s in res:
        assert frac >= min_frac
        assert wrong_s <= 0.5


# ---------------- 8. muc tieu gan mep khung ----------------
def test_target_near_frame_edge_wobble_14deg_stays_tracked():
    res = [sim_noisy_attitude(0.0, wobble_deg=14.0, seed=sd) for sd in (1, 2, 3)]
    print(f"\n[wobble 14 deg] TRACK frac / wrong_s per seed: {res}")
    for frac, wrong_s in res:
        assert frac >= 0.90
        assert wrong_s <= 0.5


def test_synthetic_detector_clips_bbox_at_frame_edge():
    own = OwnState(t=0.0, pos_ned=(0, 0, 0), vel_ned=(0, 0, 0), q_world_body=Q0)
    ray = pixel_to_ray_cam(CAM, CAM.width - 0.5, CAM.height - 0.5)
    pos = 20.0 * ray_cam_to_ned(CAM, Q0, ray)
    cfg = dict(p_miss=0.0, p_false=0.0, center_sigma_px=0.0, size_sigma_px=0.0, latency_s=0.0)
    d = SyntheticDetector(CAM, SyntheticConfig(**cfg)).process(0.0, pos, own)[0]
    assert d.cx + d.w / 2 <= CAM.width + 1e-6 and d.cy + d.h / 2 <= CAM.height + 1e-6
    full = CAM.fx * 0.30 / 20.0
    assert d.w < 0.6 * full and d.h < 0.6 * full
    d2 = SyntheticDetector(CAM, SyntheticConfig(clip_to_frame=False, **cfg)).process(0.0, pos, own)[0]
    assert d2.w == pytest.approx(full)


# ---------------- T9d: update goi nhanh hon detector khong lam mat ung vien bat lai ----------------
def test_reacquire_works_when_update_runs_faster_than_detector():
    """update 120 Hz, detector 30 Hz (3 goi trong 4 khong co phat hien). Mat 1 s roi bat lai:
    ung vien tai bat khong duoc bi xoa boi cac goi rong; phai ve TRACK trong 0.5 s (khong cho 3 s)."""
    rng = np.random.default_rng(5)
    trk = SingleTargetTracker(CAM)
    for k in range(60):
        trk.update([static_det(k * DT, CAM.cx, CAM.cy, 30.0, rng)], own_at(k * DT), k * DT)
    t_back = 59 * DT + 1.0
    status_at = None
    for i in range(int(3.0 * 120)):
        t = 59 * DT + 0.2 + i / 120.0
        dets = []
        if t >= t_back and (i % 4) == 0:                      # detector 30 Hz sau khi quay lai
            dets = [static_det(t, CAM.cx, CAM.cy, 30.0, rng)]
        st = trk.update(dets, own_at(t), t)
        if t >= t_back and st.status == TrackStatus.TRACK and status_at is None:
            status_at = t - t_back
    assert status_at is not None and status_at <= 0.5, status_at
