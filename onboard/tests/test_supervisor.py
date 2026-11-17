"""Test supervisor: moi chuyen trang thai, engage / disengage, watchdog (khong can SITL)."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.config import GuidanceConfig, SupervisorConfig
from dtrack.supervisor import SupState, Supervisor, SupervisorInput
from dtrack.types import OwnState, TrackState, TrackStatus

GC = GuidanceConfig(cam_tilt_up_deg=0.0)


def sup(**kw):
    return Supervisor(SupervisorConfig(**kw), GC)


def own(armed=True, mode="GUIDED", v=(0.0, 0.0, 0.0), t=0.0):
    return OwnState(t=t, pos_ned=(0.0, 0.0, -30.0), vel_ned=v, q_world_body=(1.0, 0.0, 0.0, 0.0),
                    armed=armed, mode=mode)


def trk(status, t, r=25.0, valid=True):
    if status in (TrackStatus.SEARCH, TrackStatus.LOST):
        return TrackState(t=t, status=status)
    return TrackState(t=t, status=status, los_ned=(1.0, 0.0, 0.0), los_rate_ned=(0.0, 0.0, 0.0),
                      range_m=r, range_sigma_m=1.0, range_rate_mps=0.0, range_valid=valid)


def inp(t, status=TrackStatus.TRACK, o="default", engage=True, hb=0.1, pose=0.02, dt=0.033, **tk):
    return SupervisorInput(t=t, track=trk(status, t, **tk), own=own() if o == "default" else o,
                           engage=engage, heartbeat_age_s=hb, pose_age_s=pose, loop_dt_s=dt)


# ---------------- engage / disengage ----------------
def test_starts_idle_and_sends_nothing_without_engage():
    s = sup()
    o = s.step(inp(0.0, engage=False))
    assert o.state == SupState.IDLE and not o.send and o.cmd is None


@pytest.mark.parametrize("kw,why", [
    (dict(engage=False), "no_engage"),
    (dict(o=own(armed=False)), "disarmed"),
    (dict(o=own(mode="LOITER")), "mode=LOITER"),
    (dict(o=own(mode="RTL")), "mode=RTL"),
    (dict(o=None), "no_own"),
])
def test_no_command_unless_armed_guided_engaged(kw, why):
    s = sup()
    out = s.step(inp(0.0, **kw))
    assert out.state == SupState.IDLE and not out.send and out.cmd is None and why in out.reason


def test_engage_then_track_sends():
    s = sup()
    out = s.step(inp(0.0))
    assert out.state == SupState.TRACK and out.send and out.cmd is not None and out.engaged


def test_search_when_no_target_after_engage_brakes():
    s = sup()
    out = s.step(inp(0.0, TrackStatus.SEARCH))
    assert out.state == SupState.SEARCH and out.send and out.cmd.vel_ned == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("kw", [dict(engage=False), dict(o=own(mode="LOITER")), dict(o=own(armed=False))])
def test_disengage_mid_flight_stops_immediately(kw):
    s = sup()
    assert s.step(inp(0.0)).send
    out = s.step(inp(0.033, **kw))
    assert out.state == SupState.IDLE and not out.send and out.cmd is None


def test_reengage_restarts_clean():
    s = sup()
    s.step(inp(0.0))
    s.step(inp(0.033, engage=False))
    out = s.step(inp(0.066))
    assert out.state == SupState.TRACK and out.send


# ---------------- TRACK / COAST / LOST ----------------
def test_track_to_coast_to_lost_by_timeout():
    s = sup(coast_follow_s=2.0)
    assert s.step(inp(0.0)).state == SupState.TRACK
    o = s.step(inp(0.3, TrackStatus.COAST))
    assert o.state == SupState.COAST and o.send and o.cmd.reason.find("coast") >= 0
    o = s.step(inp(2.2, TrackStatus.COAST))
    assert o.state == SupState.COAST
    o = s.step(inp(2.5, TrackStatus.COAST))          # > 2 s ke tu luc vao COAST (0.3)
    assert o.state == SupState.LOST and o.cmd.vel_ned == (0.0, 0.0, 0.0)


def test_coast_to_track_recovers():
    s = sup()
    s.step(inp(0.0))
    assert s.step(inp(0.4, TrackStatus.COAST)).state == SupState.COAST
    assert s.step(inp(0.5, TrackStatus.TRACK)).state == SupState.TRACK


def test_tracker_lost_brakes_and_holds():
    s = sup()
    s.step(inp(0.0))
    o = s.step(inp(3.5, TrackStatus.LOST), )
    assert o.state == SupState.LOST and o.send and o.cmd.vel_ned == (0.0, 0.0, 0.0)
    o = s.step(inp(4.5, TrackStatus.SEARCH))          # tracker ve SEARCH sau khi giu LOST: van LOST o supervisor
    assert o.state == SupState.LOST


def test_lost_to_track_reacquire():
    s = sup()
    s.step(inp(0.0))
    s.step(inp(3.5, TrackStatus.LOST))
    assert s.step(inp(4.0, TrackStatus.TRACK)).state == SupState.TRACK


def test_lost_too_long_requests_rtl_once():
    s = sup(lost_rtl_s=5.0)
    s.step(inp(0.0))
    s.step(inp(1.0, TrackStatus.LOST))
    assert not s.step(inp(5.9, TrackStatus.LOST)).request_rtl
    o = s.step(inp(6.1, TrackStatus.LOST))
    assert o.request_rtl and "rtl_requested" in o.reason
    assert not s.step(inp(7.0, TrackStatus.LOST)).request_rtl          # chi mot lan


def test_rtl_can_be_disabled():
    s = sup(lost_rtl_s=1.0, rtl_on_lost=False)
    s.step(inp(0.0))
    for t in (1.0, 5.0, 20.0):
        assert not s.step(inp(t, TrackStatus.LOST)).request_rtl


def test_never_found_target_requests_rtl_after_timeout():
    s = sup(lost_rtl_s=5.0)
    s.step(inp(0.0, TrackStatus.SEARCH))
    assert not s.step(inp(4.0, TrackStatus.SEARCH)).request_rtl
    assert s.step(inp(5.5, TrackStatus.SEARCH)).request_rtl


def test_rtl_flag_resets_after_disengage():
    s = sup(lost_rtl_s=1.0)
    s.step(inp(0.0))
    s.step(inp(2.0, TrackStatus.LOST))
    assert s.step(inp(3.5, TrackStatus.LOST)).request_rtl
    s.step(inp(3.6, engage=False))
    s.step(inp(4.0))
    s.step(inp(5.0, TrackStatus.LOST))
    assert s.step(inp(6.5, TrackStatus.LOST)).request_rtl


# ---------------- watchdog / ABORT ----------------
def test_abort_on_heartbeat_lost():
    s = sup(heartbeat_timeout_s=3.0)
    s.step(inp(0.0))
    o = s.step(inp(0.1, hb=3.5))
    assert o.state == SupState.ABORT and not o.send and "heartbeat" in o.reason     # mat link: khong gui duoc


def test_abort_on_stale_pose_brakes_if_link_alive():
    s = sup(pose_timeout_s=0.5)
    s.step(inp(0.0))
    o = s.step(inp(0.1, pose=0.8))
    assert o.state == SupState.ABORT and o.send and o.cmd.vel_ned == (0.0, 0.0, 0.0)
    assert "pose_stale" in o.reason


def test_abort_on_slow_loop():
    s = sup(loop_slow_s=0.25)
    s.step(inp(0.0))
    o = s.step(inp(0.5, dt=0.4))
    assert o.state == SupState.ABORT and o.send and o.cmd.vel_ned == (0.0, 0.0, 0.0) and "loop_slow" in o.reason
    assert len(s.abort_reasons) == 1


def test_abort_recovers_after_clear_period():
    s = sup(abort_recover_s=1.0)
    s.step(inp(0.0))
    s.step(inp(0.1, pose=1.0))
    assert s.step(inp(0.2)).state == SupState.ABORT          # moi het loi: giu ABORT
    assert s.step(inp(1.0)).state == SupState.ABORT
    o = s.step(inp(1.3))
    assert o.state in (SupState.SEARCH, SupState.TRACK)
    assert o.state == SupState.TRACK


def test_abort_has_priority_over_min_range_and_tracking():
    s = sup()
    o = s.step(inp(0.0, pose=2.0, r=5.0))
    assert o.state == SupState.ABORT and o.cmd.vel_ned == (0.0, 0.0, 0.0)


def test_abort_does_not_send_when_not_engaged():
    s = sup()
    o = s.step(inp(0.0, engage=False, pose=5.0, hb=9.0))
    assert o.state == SupState.IDLE and not o.send


def test_abort_when_no_heartbeat_ever():
    s = sup()
    o = s.step(inp(0.0, hb=float("inf")))
    assert o.state == SupState.ABORT and not o.send


# ---------------- lenh cuoi cung luon huu han / an toan ----------------
def test_nan_track_gives_brake_command():
    s = sup()
    bad = TrackState(t=0.0, status=TrackStatus.TRACK, los_ned=(float("nan"), 0.0, 0.0), los_rate_ned=(0, 0, 0),
                     range_m=20.0, range_valid=True)
    o = s.step(SupervisorInput(t=0.0, track=bad, own=own(), engage=True, heartbeat_age_s=0.1, pose_age_s=0.02))
    assert o.send and o.cmd.vel_ned == (0.0, 0.0, 0.0)
    assert all(math.isfinite(c) for c in o.cmd.vel_ned)


def test_range_invalid_in_supervisor_does_not_approach():
    s = sup()
    o = s.step(inp(0.0, valid=False, r=40.0))
    assert o.state == SupState.TRACK and o.cmd.vel_ned[0] <= 0.0 + 1e-9
    assert "range_invalid" in o.cmd.reason


# ---------------- T9a/B6a: bay tiep khi mat muc tieu, het han moi phanh ----------------
def own_v(v=(8.0, 0.0, 0.0)):
    return own(v=v)


def test_tracker_lost_but_within_follow_window_keeps_flying():
    s = sup(coast_follow_s=4.0)
    t = 0.0
    while t < 2.0:                                      # TRACK hop le, bay 8 m/s
        s.step(inp(t, o=own_v()))
        t += 0.033
    o = s.step(inp(2.1, TrackStatus.COAST, o=own_v()))
    assert o.state == SupState.COAST and o.cmd.vel_ned[0] > 5.0
    o = s.step(inp(5.2, TrackStatus.LOST, o=own_v()))   # 3.1 s ke tu COAST: tracker da reset (LOST), supervisor van COAST
    assert o.state == SupState.COAST and o.send and "blind" in o.cmd.reason and o.cmd.vel_ned[0] > 2.0
    o = s.step(inp(5.9, TrackStatus.SEARCH, o=own_v()))  # 3.8 s: van trong han
    assert o.state == SupState.COAST and "blind" in o.cmd.reason


def test_follow_window_expires_to_lost_brake():
    s = sup(coast_follow_s=4.0)
    for k in range(60):
        s.step(inp(k * 0.033, o=own_v()))
    s.step(inp(2.1, TrackStatus.COAST, o=own_v()))
    o = s.step(inp(6.2, TrackStatus.LOST, o=own_v()))   # 4.1 s ke tu COAST: het han
    assert o.state == SupState.LOST and o.cmd.vel_ned == (0.0, 0.0, 0.0) and o.cmd.reason.startswith("brake")


def test_blind_reacquire_returns_to_track():
    s = sup()
    for k in range(60):
        s.step(inp(k * 0.033, o=own_v()))
    s.step(inp(2.1, TrackStatus.COAST, o=own_v()))
    assert s.step(inp(4.0, TrackStatus.LOST, o=own_v())).state == SupState.COAST
    o = s.step(inp(4.2, TrackStatus.TRACK, o=own_v(), valid=False))
    assert o.state == SupState.TRACK and o.send and o.cmd.vel_ned[0] <= 8.0 + 1e-6