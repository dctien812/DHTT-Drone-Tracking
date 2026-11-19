"""Test PHA DO cho GimbalController.step(t, q_body, track, scan_delta_rad=x) (.office/design-search.md (a), (c)).

Quy uoc tu chot: scan_delta_rad khac None -> delta_cmd_rad = kep(x, [delta_min, delta_max]) truc tiep (KHONG on dinh
theo tu the: khong phu thuoc q_body), mode "scan", kiem TRUOC nhanh TRACK/COAST. Khong quy dinh co sat khi kep.
Ca bao ve (khong truyen scan_delta_rad): hanh vi cu giu nguyen -> PASS ngay.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

D = math.radians


def q_pitch_roll(theta_down=0.0, roll=0.0):
    """Quaternion than FRD -> NED, khong yaw: pitch = -theta_down quanh y, roll quanh x (q = qy * qx)."""
    cy, sy = math.cos(-theta_down / 2), math.sin(-theta_down / 2)
    cx, sx = math.cos(roll / 2), math.sin(roll / 2)
    return (cy * cx, cy * sx, sy * cx, -sy * sx)


def los(elev_deg, az_deg=40.0):
    e, a = D(elev_deg), D(az_deg)
    return (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), -math.sin(e))


def track(status_name, t, elev_deg=-12.0):
    from dtrack.types import TrackState, TrackStatus
    st = getattr(TrackStatus, status_name)
    if status_name in ("SEARCH", "LOST"):
        return TrackState(t=t, status=st)
    return TrackState(t=t, status=st, los_ned=los(elev_deg), los_rate_ned=(0.0, 0.0, 0.0),
                      range_m=20.0, range_sigma_m=1.0, range_rate_mps=0.0, range_valid=True)


def make_ctrl(**kw):
    from dtrack.gimbal_control import GimbalController
    from dtrack.config import GimbalConfig
    return GimbalController(GimbalConfig(**kw))


# ---------------- ca bao ve: khong co scan_delta_rad -> nhu cu ----------------
def test_guard_without_scan_arg_behaviour_unchanged():
    ctrl = make_ctrl()
    c = ctrl.step(1.0, q_pitch_roll(D(30)), track("TRACK", 1.0, -12.0))
    assert c.mode == "track" and c.delta_cmd_rad == pytest.approx(D(72.0), abs=1e-9)
    c = ctrl.step(1.1, q_pitch_roll(D(30)), track("COAST", 1.1, -12.0))
    assert c.mode == "coast" and c.delta_cmd_rad == pytest.approx(D(72.0), abs=1e-9)
    c = ctrl.step(1.2, q_pitch_roll(D(30)), track("LOST", 1.2))
    assert c.mode == "hold"


def test_guard_init_mode_before_lock_unchanged():
    c = make_ctrl().step(0.0, q_pitch_roll(0.0), track("SEARCH", 0.0))
    assert c.mode == "init" and c.delta_cmd_rad == pytest.approx(D(90.0))


# ---------------- scan_delta_rad=None giong het ----------------
def test_explicit_none_identical_to_omitted_over_a_sequence():
    seq = [("SEARCH", 0.0), ("TRACK", 0.1), ("TRACK", 0.2), ("COAST", 0.3), ("LOST", 0.4), ("SEARCH", 0.5)]
    a, b = make_ctrl(), make_ctrl()
    for st, t in seq:
        q = q_pitch_roll(D(20), D(5))
        ca = a.step(t, q, track(st, t))
        cb = b.step(t, q, track(st, t), scan_delta_rad=None)
        assert ca == cb


# ---------------- quet ----------------
def test_scan_returns_requested_delta_in_scan_mode():
    c = make_ctrl().step(1.0, q_pitch_roll(0.0), track("LOST", 1.0), scan_delta_rad=D(60.0))
    assert c.mode == "scan"
    assert c.delta_cmd_rad == pytest.approx(D(60.0), abs=1e-9)
    assert c.t == 1.0


def test_scan_is_not_stabilised_by_body_attitude():
    q = q_pitch_roll(D(30), D(15))
    c = make_ctrl().step(1.0, q, track("LOST", 1.0), scan_delta_rad=D(45.0))
    assert c.delta_cmd_rad == pytest.approx(D(45.0), abs=1e-9)


@pytest.mark.parametrize("x_deg,expect_deg", [(5.0, 10.0), (0.0, 10.0), (-30.0, 10.0), (115.0, 110.0), (170.0, 110.0),
                                               (10.0, 10.0), (110.0, 110.0)])
def test_scan_clamped_to_default_range(x_deg, expect_deg):
    c = make_ctrl().step(1.0, q_pitch_roll(0.0), track("LOST", 1.0), scan_delta_rad=D(x_deg))
    assert c.mode == "scan"
    assert c.delta_cmd_rad == pytest.approx(D(expect_deg), abs=1e-9)


def test_scan_clamped_to_configured_range():
    ctrl = make_ctrl(delta_min_deg=20.0, delta_max_deg=60.0, delta_init_deg=40.0)
    assert ctrl.step(1.0, q_pitch_roll(0.0), track("LOST", 1.0), scan_delta_rad=D(85.9)).delta_cmd_rad \
        == pytest.approx(D(60.0), abs=1e-9)
    assert ctrl.step(1.1, q_pitch_roll(0.0), track("LOST", 1.1), scan_delta_rad=D(12.0)).delta_cmd_rad \
        == pytest.approx(D(20.0), abs=1e-9)


@pytest.mark.parametrize("status", ["TRACK", "COAST"])
def test_scan_has_priority_over_track_and_coast_branches(status):
    ctrl = make_ctrl()
    ctrl.step(0.9, q_pitch_roll(D(30)), track("TRACK", 0.9, -12.0))      # da khoa muc tieu
    c = ctrl.step(1.0, q_pitch_roll(D(30)), track(status, 1.0, -12.0), scan_delta_rad=D(33.0))
    assert c.mode == "scan"
    assert c.delta_cmd_rad == pytest.approx(D(33.0), abs=1e-9)


def test_scan_has_priority_over_hold_after_lock():
    ctrl = make_ctrl()
    ctrl.step(0.9, q_pitch_roll(D(30)), track("TRACK", 0.9, -12.0))
    c = ctrl.step(1.0, q_pitch_roll(D(30)), track("LOST", 1.0), scan_delta_rad=D(100.0))
    assert c.mode == "scan" and c.delta_cmd_rad == pytest.approx(D(100.0), abs=1e-9)


def test_track_branch_resumes_normally_after_scan():
    """S-3: scan_delta_rad=None tro lai -> nhanh TRACK chay nhu thuong (elev -12, theta 30 -> 72 do)."""
    ctrl = make_ctrl()
    ctrl.step(1.0, q_pitch_roll(D(30)), track("LOST", 1.0), scan_delta_rad=D(100.0))
    c = ctrl.step(1.1, q_pitch_roll(D(30)), track("TRACK", 1.1, -12.0), scan_delta_rad=None)
    assert c.mode == "track" and c.delta_cmd_rad == pytest.approx(D(72.0), abs=1e-9)
