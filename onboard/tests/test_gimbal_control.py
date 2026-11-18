"""Test PHA DO cho GimbalController (dtrack/gimbal_control.py, buoc 4 cua .office/design-gimbal-steps-3-6.md).

Quy uoc (nhu test_gimbal_geometry.py): quaternion (w,x,y,z) than FRD -> NED; theta > 0 = mui chui xuong = pitch -theta.
Khong roll: delta = 90 - theta - elev (do). Ky vong tinh tay, khong goi lai elev_to_delta cua du an.
  (1) theta=30, elev=-12  -> 90-30+12 = 72
  (2) hold_offset=3, elev_los=-12 -> aim=-9 -> 90-30+9 = 69
  (3) theta=0, elev=-12   -> 102 > 90 -> ket 90, sat=True
  (5) elev=-5: theta=30 -> 65 ; theta=10 -> 85 (tang 20), aim van -5
  (10) gioi han [20,60]: theta=30, elev=-12 -> 72 -> ket 60 sat ; theta=80, elev=0 -> 10 -> ket 20 sat
Cach dung: GimbalConfig THAT (dtrack.config, buoc 3) qua kwargs do; TrackState THAT (dtrack.types);
LOS don vi NED = (cos e cos az, cos e sin az, -sin e).
Import dtrack.gimbal_control / GimbalConfig / servo_model ben TRONG ham de moi ca do rieng.
"""
import dataclasses
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

D = math.radians


# ---------------- tien ich (sao tu test_gimbal_geometry.py de file doc lap) ----------------
def _qaxis(axis, a):
    return np.array([math.cos(a / 2), *(math.sin(a / 2) * np.array(axis, float))])


def _qmul(a, b):
    aw, av = a[0], a[1:]
    bw, bv = b[0], b[1:]
    return np.array([aw * bw - av @ bv, *(aw * bv + bw * av + np.cross(av, bv))])


def body_quat(theta_down=0.0, roll=0.0, yaw=0.0):
    q = _qmul(_qmul(_qaxis((0, 0, 1), yaw), _qaxis((0, 1, 0), -theta_down)), _qaxis((1, 0, 0), roll))
    return tuple(float(c) for c in q)


def mat_from_q(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def los(elev_deg, az_deg=40.0):
    e, a = D(elev_deg), D(az_deg)
    return (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), -math.sin(e))


def track(status_name, t, elev_deg=-12.0, u=None):
    from dtrack.types import TrackState, TrackStatus
    st = getattr(TrackStatus, status_name)
    if status_name in ("SEARCH", "LOST"):
        return TrackState(t=t, status=st)
    return TrackState(t=t, status=st, los_ned=los(elev_deg) if u is None else u, los_rate_ned=(0.0, 0.0, 0.0),
                      range_m=20.0, range_sigma_m=1.0, range_rate_mps=0.0, range_valid=True)


def make_ctrl(**kw):
    from dtrack.gimbal_control import GimbalController   # import dau tien: ly do do mong doi
    from dtrack.config import GimbalConfig
    return GimbalController(GimbalConfig(**kw))


# ---------------- GimbalCommand / GimbalPort ----------------
def test_gimbal_command_is_frozen_dataclass_with_spec_fields():
    from dtrack.gimbal_control import GimbalCommand
    assert dataclasses.is_dataclass(GimbalCommand)
    names = [f.name for f in dataclasses.fields(GimbalCommand)]
    assert names == ["t", "delta_cmd_rad", "sat", "mode", "elev_los_rad", "elev_aim_rad"]
    c = GimbalCommand(t=1.0, delta_cmd_rad=1.0, sat=False, mode="init", elev_los_rad=None, elev_aim_rad=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.t = 2.0


def test_sim_gimbal_port_satisfies_gimbal_port_protocol():
    from dtrack.gimbal_control import GimbalPort
    from dtrack.config import GimbalConfig
    from simtools.servo_model import ServoModel, SimGimbalPort
    port = SimGimbalPort(ServoModel.from_config(GimbalConfig()))
    assert callable(getattr(port, "command")) and callable(getattr(port, "angle"))
    assert GimbalPort is not None


# ---------------- (1) hanh vi 1: theta=30, elev -12 -> 72 ----------------
def test_track_theta30_elev_minus12_gives_delta_72():
    ctrl = make_ctrl()
    c = ctrl.step(1.0, body_quat(D(30)), track("TRACK", 1.0, -12.0))
    assert c.mode == "track" and c.sat is False
    assert c.t == 1.0
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(72.0, abs=1e-6)
    assert math.degrees(c.elev_los_rad) == pytest.approx(-12.0, abs=1e-6)
    assert math.degrees(c.elev_aim_rad) == pytest.approx(-12.0, abs=1e-6)


def test_track_with_roll_and_yaw_aims_los_to_boresight_elevation():
    # delta tra ve phai dua truc quang len dung goc nang -12 do (kiem doc lap bang ma tran)
    from dtrack.gimbal import camera_attitude
    ctrl = make_ctrl()
    q = body_quat(D(35), D(20), D(77))
    c = ctrl.step(0.0, q, track("TRACK", 0.0, -12.0))
    assert c.sat is False
    fwd = mat_from_q(camera_attitude(q, c.delta_cmd_rad))[:, 0]
    assert math.asin(-fwd[2]) == pytest.approx(D(-12.0), abs=D(0.01))


# ---------------- (2) hanh vi 2: hold_offset ----------------
def test_hold_offset_3deg_adds_to_aim_not_to_los():
    ctrl = make_ctrl(hold_offset_deg=3.0)
    c = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -12.0))
    assert math.degrees(c.elev_los_rad) == pytest.approx(-12.0, abs=1e-6)
    assert math.degrees(c.elev_aim_rad) == pytest.approx(-9.0, abs=1e-6)
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(69.0, abs=1e-6)


# ---------------- (3) hanh vi 3: bao hoa ----------------
def test_hover_theta0_elev_minus12_saturates_at_90():
    ctrl = make_ctrl()
    c = ctrl.step(0.0, body_quat(0.0), track("TRACK", 0.0, -12.0))
    assert c.sat is True
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(90.0, abs=1e-6)
    assert c.mode == "track"


# ---------------- (4) hanh vi 4: SEARCH chua khoa ----------------
@pytest.mark.parametrize("status", ["SEARCH", "LOST"])
def test_never_locked_search_or_lost_commands_delta_init(status):
    ctrl = make_ctrl(delta_init_deg=75.0)
    c = ctrl.step(0.0, body_quat(D(30)), track(status, 0.0))
    assert c.mode == "init"
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(75.0, abs=1e-9)
    assert c.elev_los_rad is None and c.elev_aim_rad is None


# ---------------- (5) hanh vi 5: khoa roi LOST, giu huong nhin so voi duong chan troi ----------------
def test_after_lock_lost_holds_aim_while_body_pitch_changes():
    ctrl = make_ctrl()
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    assert math.degrees(c1.delta_cmd_rad) == pytest.approx(65.0, abs=1e-6)
    c2 = ctrl.step(0.1, body_quat(D(10)), track("LOST", 0.1))
    assert c2.mode == "hold" and c2.sat is False
    assert math.degrees(c2.delta_cmd_rad) == pytest.approx(85.0, abs=1e-6)        # tang dung 20 do
    assert math.degrees(c2.delta_cmd_rad - c1.delta_cmd_rad) == pytest.approx(20.0, abs=1e-6)
    assert math.degrees(c2.elev_aim_rad) == pytest.approx(-5.0, abs=1e-6)         # aim giu nguyen


def test_search_after_lock_also_holds():
    ctrl = make_ctrl()
    ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    c = ctrl.step(0.1, body_quat(D(30)), track("SEARCH", 0.1))
    assert c.mode == "hold" and math.degrees(c.delta_cmd_rad) == pytest.approx(65.0, abs=1e-6)


def test_hold_includes_hold_offset_in_remembered_aim():
    # last_aim = elev_los + offset (luat TRACK) -> hold dung lai aim do: -5 + 3 = -2, theta 30 -> 90-30+2 = 62
    ctrl = make_ctrl(hold_offset_deg=3.0)
    ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    c = ctrl.step(0.1, body_quat(D(30)), track("LOST", 0.1))
    assert c.mode == "hold"
    assert math.degrees(c.elev_aim_rad) == pytest.approx(-2.0, abs=1e-6)
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(62.0, abs=1e-6)


# ---------------- (6) hanh vi 6: COAST dung LOS nhu TRACK ----------------
def test_coast_uses_los_like_track():
    a = make_ctrl().step(0.0, body_quat(D(30)), track("TRACK", 0.0, -12.0))
    b = make_ctrl().step(0.0, body_quat(D(30)), track("COAST", 0.0, -12.0))
    assert b.mode == "coast"
    assert b.delta_cmd_rad == pytest.approx(a.delta_cmd_rad, abs=1e-12)
    assert b.elev_los_rad == pytest.approx(a.elev_los_rad, abs=1e-12)
    assert math.degrees(b.delta_cmd_rad) == pytest.approx(72.0, abs=1e-6)


def test_coast_counts_as_locked_for_later_hold():
    ctrl = make_ctrl()
    ctrl.step(0.0, body_quat(D(30)), track("COAST", 0.0, -5.0))
    c = ctrl.step(0.1, body_quat(D(10)), track("LOST", 0.1))
    assert c.mode == "hold" and math.degrees(c.delta_cmd_rad) == pytest.approx(85.0, abs=1e-6)


def test_non_unit_los_is_normalised():
    # |u| = 2 (>= 0.5, hop le): elev van tinh tren u/|u|
    u = tuple(2.0 * c for c in los(-12.0))
    c = make_ctrl().step(0.0, body_quat(D(30)), track("TRACK", 0.0, u=u))
    assert math.degrees(c.elev_los_rad) == pytest.approx(-12.0, abs=1e-6)
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(72.0, abs=1e-6)


# ---------------- (7) hanh vi 7: frozen ----------------
@pytest.mark.parametrize("status", ["TRACK", "COAST", "SEARCH", "LOST"])
def test_frozen_always_commands_delta_init(status):
    ctrl = make_ctrl(frozen=True, delta_init_deg=75.0)
    c = ctrl.step(0.0, body_quat(D(30)), track(status, 0.0, -12.0))
    assert c.mode == "frozen" and c.sat is False
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(75.0, abs=1e-9)


# ---------------- (8) hanh vi 8: dau vao hong khong nem, hold_last ----------------
def test_nan_quaternion_does_not_raise_and_repeats_previous_command():
    ctrl = make_ctrl()
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -12.0))
    c2 = ctrl.step(0.033, (float("nan"), 0.0, 0.0, 0.0), track("TRACK", 0.033, -12.0))
    assert c2.mode == "hold_last"
    assert c2.delta_cmd_rad == c1.delta_cmd_rad
    assert c2.t == 0.033


def test_nan_los_does_not_raise_and_repeats_previous_command():
    ctrl = make_ctrl()
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -12.0))
    nan_u = (float("nan"), 0.0, 0.0)
    c2 = ctrl.step(0.033, body_quat(D(30)), track("TRACK", 0.033, u=nan_u))
    assert c2.mode == "hold_last"
    assert c2.delta_cmd_rad == c1.delta_cmd_rad


def test_hold_last_chain_then_recovers_on_valid_input():
    ctrl = make_ctrl()
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -12.0))
    bad = (float("inf"), 0.0, 0.0, 0.0)
    for k in (1, 2):
        c = ctrl.step(k * 0.033, bad, track("TRACK", k * 0.033, -12.0))
        assert c.mode == "hold_last" and c.delta_cmd_rad == c1.delta_cmd_rad
    c = ctrl.step(0.1, body_quat(D(60)), track("TRACK", 0.1, -12.0))
    assert c.mode == "track" and math.degrees(c.delta_cmd_rad) == pytest.approx(42.0, abs=1e-6)   # 90-60+12


# ---------------- (9) hanh vi 9: reset ----------------
def test_reset_forgets_lock_and_returns_to_init():
    ctrl = make_ctrl(delta_init_deg=75.0)
    ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    ctrl.reset()
    c = ctrl.step(1.0, body_quat(D(30)), track("LOST", 1.0))
    assert c.mode == "init" and math.degrees(c.delta_cmd_rad) == pytest.approx(75.0, abs=1e-9)


# ---------------- (10) hanh vi 10: gioi han tuy chinh tu cfg ----------------
def test_custom_limits_from_config_clamp_both_sides():
    ctrl = make_ctrl(delta_min_deg=20.0, delta_max_deg=60.0, delta_init_deg=40.0)
    hi = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -12.0))     # 72 -> 60
    assert hi.sat is True and math.degrees(hi.delta_cmd_rad) == pytest.approx(60.0, abs=1e-6)
    lo = ctrl.step(0.1, body_quat(D(80)), track("TRACK", 0.1, 0.0))       # 10 -> 20
    assert lo.sat is True and math.degrees(lo.delta_cmd_rad) == pytest.approx(20.0, abs=1e-6)


# ---------------- (11) hanh vi 11: vong kin voi SimGimbalPort + camera_attitude ----------------
def _closed_loop(slow_factor, ideal, n=300, f_hz=0.2, amp_deg=10.0, mean_deg=30.0, elev_deg=-12.0):
    """Muc tieu co dinh (LOS NED co dinh, elev -12). Than lac pitch mean +- amp (theta 20..40 -> delta 62..82, khong ket).
    Mot chu ky 30 Hz: angle -> do sai so -> controller.step -> port.command. Tra ve sai so |elev_boresight - elev_los| (rad)."""
    from dtrack.config import GimbalConfig
    from dtrack.gimbal import camera_attitude
    from dtrack.gimbal_control import GimbalController
    from simtools.servo_model import ServoModel, SimGimbalPort
    if ideal:
        g = GimbalConfig(rate_dps=1e5, lag_s=1e-3, dead_time_s=0.0, quant_deg=0.0)
    else:
        g = GimbalConfig(slow_factor=slow_factor)
    port = SimGimbalPort(ServoModel.from_config(g))
    ctrl = GimbalController(g)
    errs = []
    for k in range(n):
        t = k / 30.0
        theta = D(mean_deg + amp_deg * math.sin(2 * math.pi * f_hz * t))
        q = body_quat(theta, 0.0, D(25))
        delta_act = port.angle(t)
        fwd = mat_from_q(camera_attitude(q, delta_act))[:, 0]
        errs.append(abs(math.asin(-fwd[2]) - D(elev_deg)))
        gc = ctrl.step(t, q, track("TRACK", t, elev_deg))
        assert gc.sat is False
        port.command(t, gc.delta_cmd_rad)
    return errs


def test_closed_loop_ideal_servo_keeps_los_within_half_degree():
    # bo 3 chu ky dau (servo con o delta_init=90). Sai so con lai = tre 1 chu ky 30 Hz:
    # toc do theta toi da = 10 do * 2pi*0.2 = 12.57 do/s -> /30 = 0.42 do < 0.5 do
    errs = _closed_loop(1.0, ideal=True)
    assert max(errs[3:]) < D(0.5)


def test_closed_loop_slow_x2_servo_error_is_bounded():
    # rate 150 do/s (> 12.57 do/s can theo), lag 0.1 s, dead 0.04 s: tre tong ~0.17 s -> sai so ~12.57*0.17 = 2.1 do < 3 do
    errs = _closed_loop(2.0, ideal=False)
    steady = errs[int(2.0 * 30):]               # bo 2 s dau (dich chuyen tu delta_init)
    assert max(steady) < D(3.0)
    assert max(steady) > D(0.5)                 # servo cham that su kem hon ly tuong (tranh test rong)


# ================= BO SUNG (ra soat buoc 4): cac ca ma sai van pass =================
# Cac ca (a)-(d) viet sao cho dung CA voi ma hien tai (hold_last) LAN quy tac (f) moi (hold/init):
# chi khang dinh: khong nem, khong "track"/"coast", goc lenh dung (cung tu the than nen hold == hold_last).

# ---------------- (a) nguong do dai duong ngam ----------------
@pytest.mark.parametrize("scale", [0.0, 0.3])
def test_short_los_after_lock_is_not_tracked(scale):
    # khoa elev -5, theta 30 -> 65. LOS ngan chi ve elev -20: neu bo nguong se ra "track" 80 (hoac chia cho 0)
    ctrl = make_ctrl()
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    u = tuple(scale * c for c in los(-20.0))
    c2 = ctrl.step(0.033, body_quat(D(30)), track("TRACK", 0.033, u=u))
    assert c2.mode not in ("track", "coast")
    assert c2.elev_los_rad is None
    assert c2.delta_cmd_rad == pytest.approx(c1.delta_cmd_rad, abs=1e-9)


def test_los_just_below_half_is_rejected_and_just_above_is_used():
    ctrl = make_ctrl(delta_init_deg=75.0)
    lo = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, u=tuple(0.49 * c for c in los(-12.0))))
    assert lo.mode not in ("track", "coast")
    assert math.degrees(lo.delta_cmd_rad) == pytest.approx(75.0, abs=1e-9)
    hi = ctrl.step(0.033, body_quat(D(30)), track("TRACK", 0.033, u=tuple(0.51 * c for c in los(-12.0))))
    assert hi.mode == "track" and math.degrees(hi.delta_cmd_rad) == pytest.approx(72.0, abs=1e-6)


# ---------------- (b) reset xoa goc lenh da nho ----------------
def test_reset_clears_last_delta_so_nonfinite_input_returns_delta_init():
    ctrl = make_ctrl(delta_init_deg=75.0)
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    assert math.degrees(c1.delta_cmd_rad) == pytest.approx(65.0, abs=1e-6)
    ctrl.reset()
    c2 = ctrl.step(1.0, (float("nan"), 0.0, 0.0, 0.0), track("TRACK", 1.0, -5.0))
    assert c2.mode == "hold_last"
    assert math.degrees(c2.delta_cmd_rad) == pytest.approx(75.0, abs=1e-9)


# ---------------- (c) hold dung gioi han tuy chinh cua cfg ----------------
def test_hold_uses_custom_limits_from_config():
    ctrl = make_ctrl(delta_min_deg=20.0, delta_max_deg=60.0, delta_init_deg=40.0)
    c0 = ctrl.step(0.0, body_quat(D(50)), track("TRACK", 0.0, -12.0))       # 90-50+12 = 52, trong dai
    assert c0.sat is False and math.degrees(c0.delta_cmd_rad) == pytest.approx(52.0, abs=1e-6)
    hi = ctrl.step(0.1, body_quat(D(10)), track("LOST", 0.1))                # 92 -> ket 60 (mac dinh se ra 90)
    assert hi.mode == "hold" and hi.sat is True
    assert math.degrees(hi.delta_cmd_rad) == pytest.approx(60.0, abs=1e-6)
    lo = ctrl.step(0.2, body_quat(D(85)), track("LOST", 0.2))                # 17 -> ket 20 (mac dinh se ra 17)
    assert lo.mode == "hold" and lo.sat is True
    assert math.degrees(lo.delta_cmd_rad) == pytest.approx(20.0, abs=1e-6)


# ---------------- (d) nhanh los_ned is None ----------------
@pytest.mark.parametrize("status", ["TRACK", "COAST"])
def test_los_none_after_lock_does_not_raise_and_keeps_command(status):
    from dtrack.types import TrackState, TrackStatus
    ctrl = make_ctrl()
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    c2 = ctrl.step(0.033, body_quat(D(30)), TrackState(t=0.033, status=getattr(TrackStatus, status)))
    assert c2.mode not in ("track", "coast") and c2.elev_los_rad is None
    assert c2.delta_cmd_rad == pytest.approx(c1.delta_cmd_rad, abs=1e-9)


def test_los_none_never_locked_commands_delta_init():
    from dtrack.types import TrackState, TrackStatus
    ctrl = make_ctrl(delta_init_deg=75.0)
    c = ctrl.step(0.0, body_quat(D(30)), TrackState(t=0.0, status=TrackStatus.TRACK))
    assert c.mode not in ("track", "coast")
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(75.0, abs=1e-9)


# ---------------- (e) dau vao sai dang: khong nem, hold_last ----------------
@pytest.mark.parametrize("bad", ["los_len2", "q_len3", "q_none"])
def test_malformed_input_does_not_raise_and_repeats_previous_command(bad):
    ctrl = make_ctrl()
    c1 = ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -12.0))
    q, u = body_quat(D(30)), los(-12.0)
    if bad == "los_len2":
        u = u[:2]
    elif bad == "q_len3":
        q = q[:3]
    else:
        q = None
    c2 = ctrl.step(0.033, q, track("TRACK", 0.033, u=u))
    assert c2.mode == "hold_last"
    assert c2.delta_cmd_rad == c1.delta_cmd_rad
    assert c2.t == 0.033


# ---------------- (f) TRACK/COAST voi LOS khong hop le = mat hinh ----------------
@pytest.mark.parametrize("status", ["TRACK", "COAST"])
@pytest.mark.parametrize("bad_u", ["none", "short"])
def test_invalid_los_after_lock_holds_aim_with_current_body(status, bad_u):
    # khoa elev -5 o theta 30 (65); LOS hong khi theta 10 -> hold: aim -5 giu, delta 85 (bu tu the moi)
    from dtrack.types import TrackState, TrackStatus
    ctrl = make_ctrl()
    ctrl.step(0.0, body_quat(D(30)), track("TRACK", 0.0, -5.0))
    st = getattr(TrackStatus, status)
    if bad_u == "none":
        ts = TrackState(t=0.1, status=st)
    else:
        ts = track(status, 0.1, u=tuple(0.3 * c for c in los(-20.0)))
    c = ctrl.step(0.1, body_quat(D(10)), ts)
    assert c.mode == "hold"
    assert math.degrees(c.elev_aim_rad) == pytest.approx(-5.0, abs=1e-6)
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(85.0, abs=1e-6)


@pytest.mark.parametrize("status", ["TRACK", "COAST"])
@pytest.mark.parametrize("bad_u", ["none", "short"])
def test_invalid_los_never_locked_is_init(status, bad_u):
    from dtrack.types import TrackState, TrackStatus
    ctrl = make_ctrl(delta_init_deg=75.0)
    st = getattr(TrackStatus, status)
    ts = TrackState(t=0.0, status=st) if bad_u == "none" else track(status, 0.0, u=(0.0, 0.0, 0.0))
    c = ctrl.step(0.0, body_quat(D(30)), ts)
    assert c.mode == "init"
    assert math.degrees(c.delta_cmd_rad) == pytest.approx(75.0, abs=1e-9)
