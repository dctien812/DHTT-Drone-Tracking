"""Test dan duong (khong can SITL)."""
import json
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.config import AppConfig, GuidanceConfig, load_config, make_camera
from dtrack.geometry import pixel_to_los_ned, quat_from_euler
from dtrack.guidance import Guidance, compute_guidance, compute_guidance_ex
from dtrack.types import GuidanceCommand, OwnState, TrackState, TrackStatus

CFG = GuidanceConfig(cam_tilt_up_deg=0.0)
Q0 = (1.0, 0.0, 0.0, 0.0)


def own(v=(0.0, 0.0, 0.0), alt=30.0, q=Q0, t=10.0):
    return OwnState(t=t, pos_ned=(0.0, 0.0, -alt), vel_ned=v, q_world_body=q, armed=True, mode="GUIDED")


def track(r=25.0, u=(1.0, 0.0, 0.0), valid=True, status=TrackStatus.TRACK, rate=(0.0, 0.0, 0.0),
          rdot=0.0, t=10.0):
    return TrackState(t=t, status=status, los_ned=u, los_rate_ned=rate, range_m=r, range_sigma_m=1.0,
                      range_rate_mps=rdot, range_valid=valid)


def prev_cmd(v=(0.0, 0.0, 0.0), dt=0.1, t=10.0, reason="track"):
    return GuidanceCommand(t=t - dt, vel_ned=v, yaw_rad=0.0, valid=True, reason=reason)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def radial(cmd, u):
    return float(np.dot(cmd.vel_ned, u))


# ---------------- dau lenh ----------------
def test_far_goes_forward_along_los():
    u = unit((1.0, 1.0, 0.0))
    c = compute_guidance(track(r=30.0, u=tuple(u)), own(), CFG, prev_cmd())
    assert radial(c, u) > 0.1


def test_near_goes_backward_along_los():
    c = compute_guidance(track(r=12.0), own(), CFG, prev_cmd())
    assert c.vel_ned[0] < -0.1


def test_at_set_range_matches_target_velocity():
    # r = r_dat, muc tieu xa ra 5 m/s doc duong ngam, khong quay: lenh ~ v_own + 5
    c = compute_guidance(track(r=15.0, rdot=5.0), own(v=(5.0, 0.0, 0.0)), CFG, prev_cmd(v=(9.0, 0.0, 0.0)))
    assert 9.0 < c.vel_ned[0] <= 10.0 + 1e-6 or abs(c.vel_ned[0] - 10.0) < 1.0


def test_los_rate_term_follows_crossing_target():
    # muc tieu o 15 m, quay duong ngam 0.2 rad/s quanh truc z (xuong): van toc ngang = r*w = 3 m/s theo +y
    c = compute_guidance(track(r=15.0, rate=(0.0, 0.0, 0.2)), own(), CFG, prev_cmd(v=(0.0, 3.0, 0.0)))
    assert abs(c.vel_ned[1] - 3.0) < 0.3


def test_range_tau_raises_set_range():
    cfg = GuidanceConfig(cam_tilt_up_deg=0.0, range_tau_s=3.0)   # 10 m/s -> r_dat 30 m
    c = compute_guidance(track(r=20.0), own(v=(10.0, 0.0, 0.0)), cfg, prev_cmd(v=(10.0, 0.0, 0.0)))
    assert c.vel_ned[0] < 10.0 - 0.05          # 20 m < 30 m: lui so voi muc tieu dang dung yen tuong doi


# ---------------- range_valid = False ----------------
@pytest.mark.parametrize("seed", range(40))
def test_invalid_range_never_closes_beyond_matching(seed):
    rng = np.random.default_rng(seed)
    u = unit(rng.normal(size=3))
    v_own = tuple(rng.uniform(-8, 8, 3) * (1, 1, 0.3))
    prev = prev_cmd(v=tuple(rng.uniform(-8, 8, 3) * (1, 1, 0.3)), dt=0.05)
    r = rng.choice([4.0, 9.0, 12.0, 20.0, 60.0])
    tr = track(r=float(r), u=tuple(u), valid=False, rdot=float(rng.uniform(-60, 60)),
               rate=tuple(rng.normal(size=3) * 0.1))
    c = compute_guidance(tr, own(v=v_own, alt=40.0), CFG, prev)
    rad_own = float(np.dot(v_own, u))
    if "min_range" in c.reason:
        # dang lui khoi vung duoi khoang cach toi thieu: chi can GIAM thanh phan tien lai gan so voi lenh truoc
        assert radial(c, u) <= max(float(np.dot(prev.vel_ned, u)), -CFG.back_speed_mps) + 0.1
    else:
        # khong tien lai gan nhanh hon toc do ban than hien tai doc duong ngam (khop), rdot rac khong duoc dung
        assert radial(c, u) <= rad_own + 0.3


def test_invalid_without_range_value_does_not_close():
    u = unit((1.0, 0.2, 0.0))
    tr = TrackState(t=10.0, status=TrackStatus.TRACK, los_ned=tuple(u), los_rate_ned=(0, 0, 0), range_m=None,
                    range_valid=False)
    c = compute_guidance(tr, own(v=(3.0, 0.0, 0.0)), CFG, prev_cmd(v=(3.0, 0.0, 0.0)))
    assert radial(c, u) <= float(np.dot((3.0, 0.0, 0.0), u)) + 1e-6
    assert "range_invalid" in c.reason


def test_invalid_closing_decays_over_time():
    u = (1.0, 0.0, 0.0)
    g = Guidance(CFG)
    v = own(v=(10.0, 0.0, 0.0))
    first = g.step(track(r=30.0, valid=False, t=10.0), v)
    last = first
    for k in range(1, 60):
        last = g.step(track(r=30.0, valid=False, t=10.0 + k * 0.033), v)
    assert radial(last, u) < radial(first, u) - 1.0


# ---------------- khoang cach toi thieu ----------------
@pytest.mark.parametrize("valid", [True, False])
@pytest.mark.parametrize("r", [3.0, 6.0, 9.0, 9.9])
def test_below_min_range_always_backs_off(valid, r):
    u = (1.0, 0.0, 0.0)
    c = compute_guidance(track(r=r, valid=valid, rdot=3.0), own(v=(6.0, 0.0, 0.0)), CFG, prev_cmd(v=(6.0, 0.0, 0.0)))
    assert "min_range" in c.reason
    # dang lui: thanh phan tien lai gan giam di (theo gioi han a_back), khong bao gio tang
    assert radial(c, u) < 6.0
    assert radial(c, u) <= 6.0 - 0.5 * min(CFG.a_back_mps2 * 0.1, math.sqrt(2 * CFG.jerk_max_mps3 * 0.1))
    # ap dung lien tuc: toc do lenh hoi tu ve (van toc muc tieu - back_speed); khong ro muc tieu thi lui tuyet doi
    g = Guidance(CFG)
    o = own(v=(6.0, 0.0, 0.0))
    for k in range(300):
        c2 = g.step(track(r=r, valid=valid, rdot=3.0, t=10.0 + k / 30.0), o)
    bound = (6.0 + 3.0 - CFG.back_speed_mps) if valid else -CFG.back_speed_mps
    assert radial(c2, u) <= bound + 1e-3
    assert radial(c2, u) < 6.0 + 3.0     # luon lui so voi muc tieu


def test_min_range_hysteresis_and_exit():
    g = Guidance(CFG)
    o = own()
    assert "min_range" in g.step(track(r=9.0, t=10.0), o).reason
    assert "min_range" in g.step(track(r=11.0, t=10.03), o).reason       # trong vung hysteresis (< 12)
    assert "min_range" not in g.step(track(r=13.0, t=10.06), o).reason


def test_min_range_overrides_even_when_target_receding_fast():
    # muc tieu chay xa +15 m/s; van phai thua toc do khop (khong tien tuong doi): lenh < v_muc_tieu
    g = Guidance(CFG)
    for k in range(600):
        c = g.step(track(r=8.0, rdot=15.0, t=10.0 + k / 30.0), own())
    assert radial(c, (1.0, 0.0, 0.0)) <= 15.0 - CFG.back_speed_mps + 1e-6


# ---------------- COAST ----------------
def test_coast_does_not_approach():
    u = (1.0, 0.0, 0.0)
    c = compute_guidance(track(r=40.0, rdot=2.0, status=TrackStatus.COAST), own(v=(5.0, 0, 0)),
                         CFG, prev_cmd(v=(5.0, 0.0, 0.0)))
    assert radial(c, u) <= 5.0 + 2.0 + 1e-6       # <= v_t (v_own + rdot), khong cong them thanh phan P
    assert "coast" in c.reason


# ---------------- gioi han ----------------
def test_speed_limits_respected():
    # muc tieu uoc luong rat nhanh + xa: lenh van bi cat
    c = compute_guidance(track(r=200.0, rdot=60.0), own(v=(25.0, 0.0, 0.0)), CFG, prev_cmd(v=(29.0, 0.0, 0.0), dt=0.2))
    assert math.hypot(c.vel_ned[0], c.vel_ned[1]) <= CFG.v_max_mps + 1e-6
    u = unit((1.0, 0.0, 1.0))        # muc tieu o thap hon: vz duong (xuong)
    c = compute_guidance(track(r=100.0, u=tuple(u)), own(alt=80.0), CFG, prev_cmd(v=(0, 0, 3.9), dt=0.2))
    assert -CFG.climb_max_mps - 1e-6 <= c.vel_ned[2] <= CFG.descend_max_mps + 1e-6


def test_accel_limit_respected():
    p = prev_cmd(v=(0.0, 0.0, 0.0), dt=0.1)
    c = compute_guidance(track(r=80.0, rdot=10.0), own(), CFG, p)
    dv = np.array(c.vel_ned) - np.array(p.vel_ned)
    assert math.hypot(dv[0], dv[1]) / 0.1 <= CFG.a_max_mps2 + 1e-6
    assert abs(dv[2]) / 0.1 <= CFG.a_max_z_mps2 + 1e-6


def test_jerk_limit_respected():
    g = Guidance(CFG)
    o = own()
    acc_prev = (0.0, 0.0, 0.0)
    dt = 1.0 / 30
    for k in range(30):
        cmd, acc = compute_guidance_ex(track(r=80.0, t=10.0 + k * dt), o, CFG, g.prev, g.prev_accel)
        g.prev, g.prev_accel = cmd, acc
        da = np.linalg.norm(np.array(acc) - np.array(acc_prev))
        assert da / dt <= CFG.jerk_max_mps3 * 1.001 + 1e-6
        acc_prev = acc


def test_min_altitude_blocks_descent():
    u = unit((1.0, 0.0, 1.0))        # muc tieu thap hon
    c = compute_guidance(track(r=40.0, u=tuple(u)), own(alt=5.0), CFG, prev_cmd())
    assert c.vel_ned[2] < 0.0        # thap hon min_alt_m: leo len


# ---------------- dau vao xau / khong co muc tieu ----------------
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_inputs_brake(bad):
    for tr, ow in [
        (track(r=bad), own()),
        (track(u=(bad, 0.0, 0.0)), own()),
        (track(rate=(0.0, bad, 0.0)), own()),
        (track(), own(v=(bad, 0.0, 0.0))),
        (track(), own(q=(bad, 0.0, 0.0, 0.0))),
        (track(t=bad), own()),
    ]:
        c = compute_guidance(tr, ow, CFG, prev_cmd(v=(5.0, 0.0, 0.0)))
        assert c.vel_ned == (0.0, 0.0, 0.0)
        assert c.reason.startswith("brake")
        assert all(math.isfinite(x) for x in c.vel_ned)


def test_range_rate_nan_brakes():
    c = compute_guidance(track(r=25.0, rdot=float("nan")), own(), CFG, prev_cmd(v=(4.0, 0.0, 0.0)))
    assert c.vel_ned == (0.0, 0.0, 0.0) and c.reason.startswith("brake")


@pytest.mark.parametrize("st", [TrackStatus.SEARCH, TrackStatus.LOST])
def test_no_target_brakes(st):
    c = compute_guidance(TrackState(t=10.0, status=st), own(v=(8.0, 0, 0)), CFG, prev_cmd(v=(8.0, 0.0, 0.0)))
    assert c.vel_ned == (0.0, 0.0, 0.0) and c.reason.startswith("brake")


# ---------------- yaw va giu giua anh ----------------
def test_yaw_turns_toward_los_with_rate_limit():
    u = (0.0, 1.0, 0.0)                         # muc tieu o phia Dong, mui huong Bac
    c = compute_guidance(track(r=15.0, u=u), own(), CFG, prev_cmd(dt=0.1))
    step = math.radians(CFG.yaw_rate_max_dps) * 0.1
    assert 0.0 < c.yaw_rad <= step + 1e-9
    c2 = compute_guidance(track(r=15.0, u=(math.cos(0.1), math.sin(0.1), 0.0)), own(), CFG, prev_cmd(dt=0.1))
    assert abs(c2.yaw_rad - 0.1) < 1e-6


def test_vertical_centering_sign():
    up = unit((1.0, 0.0, -0.2))                  # muc tieu cao hon tam anh (tilt 0)
    c = compute_guidance(track(r=15.0, u=tuple(up)), own(), CFG, prev_cmd())
    assert c.vel_ned[2] < 0.0
    down = unit((1.0, 0.0, 0.2))
    c = compute_guidance(track(r=15.0, u=tuple(down)), own(), CFG, prev_cmd())
    assert c.vel_ned[2] > 0.0


def test_camera_tilt_changes_vertical_reference():
    cfg = GuidanceConfig(cam_tilt_up_deg=15.0)
    u = unit((math.cos(math.radians(15.0)), 0.0, -math.sin(math.radians(15.0))))   # dung tren truc camera
    c = compute_guidance(track(r=15.0, u=tuple(u)), own(), cfg, prev_cmd())
    assert abs(c.vel_ned[2]) < 0.05


def test_guidance_wrapper_keeps_state():
    g = Guidance(CFG)
    c1 = g.step(track(t=10.0, r=60.0), own())
    c2 = g.step(track(t=10.033, r=60.0), own())
    assert c2.vel_ned[0] > c1.vel_ned[0] > 0.0        # tang toc dan


# ---------------- config ----------------
def test_make_camera_boresight():
    cam = make_camera(15.0)
    # pixel giua anh -> huong nhin = (cos15, 0, -sin15) trong than; voi q don vi = NED
    z = pixel_to_los_ned(cam, Q0, cam.cx, cam.cy)
    assert np.allclose(z, [math.cos(math.radians(15)), 0.0, -math.sin(math.radians(15))], atol=1e-9)
    assert make_camera(0.0).R_body_cam == ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def test_load_config_json_and_reject_unknown(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"loop_hz": 20, "guidance": {"range_set_m": 25.0}, "camera": {"tilt_up_deg": 20}}))
    cfg = load_config(str(p))
    assert cfg.loop_hz == 20.0 and cfg.guidance.range_set_m == 25.0
    assert cfg.guidance.cam_tilt_up_deg == 20.0           # dong bo tu camera
    p.write_text(json.dumps({"guidance": {"khong_co": 1}}))
    with pytest.raises(ValueError):
        load_config(str(p))
    p.write_text(json.dumps({"guidance": {"range_set_m": 8.0}}))
    with pytest.raises(ValueError):
        load_config(str(p))


def test_load_config_toml(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[supervisor]\nlost_rtl_s = 5.0\nrtl_on_lost = false\n")
    cfg = load_config(str(p))
    assert cfg.supervisor.lost_rtl_s == 5.0 and cfg.supervisor.rtl_on_lost is False


def test_coast_uses_frozen_last_valid_range_not_extrapolation():
    g = Guidance(CFG)
    o = own(v=(4.0, 0.0, 0.0))
    g.step(track(r=20.0, rdot=-4.0, t=10.0), o)
    # tracker ngoai suy khoang cach xuong 5 m (r_dot cu), nhung ta khong tin ngoai suy
    c = g.step(track(r=5.0, rdot=-4.0, status=TrackStatus.COAST, t=10.3), o)
    assert "min_range" not in c.reason and "coast" in c.reason


def test_braking_slower_than_accelerating():
    p = prev_cmd(v=(10.0, 0.0, 0.0), dt=0.1)
    c = compute_guidance(track(r=15.0, rdot=-10.0), own(v=(10.0, 0.0, 0.0)), CFG, p)   # can giam toc
    dv = abs(c.vel_ned[0] - 10.0)
    assert dv <= CFG.a_decel_mps2 * 0.1 + 1e-6
