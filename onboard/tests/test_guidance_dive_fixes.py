"""Test (pha do, viet truoc ma) cho 3 thay doi dan duong sau kich ban "muc tieu cam xuong".

T1: bo phanh tu khoa khi mat hinh (Guidance._safe_hold nhanh "dang phanh thi phanh tiep").
T2: descend_max_mps mac dinh 4.8.
T3: tham so moi range_back_m (mac dinh 15.0, >= range_min_m): che do lui kich hoat khi r < range_back_m.
"""
import json
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.config import AppConfig, GuidanceConfig, load_config, load_profile, validate
from dtrack.guidance import Guidance, compute_guidance
from dtrack.types import GuidanceCommand, OwnState, TrackState, TrackStatus

CFG = GuidanceConfig(cam_tilt_up_deg=0.0)
Q0 = (1.0, 0.0, 0.0, 0.0)
DT = 1.0 / 30


def own(v=(0.0, 0.0, 0.0), alt=30.0, t=10.0):
    return OwnState(t=t, pos_ned=(0.0, 0.0, -alt), vel_ned=v, q_world_body=Q0, armed=True, mode="GUIDED")


def track(r=25.0, u=(1.0, 0.0, 0.0), status=TrackStatus.TRACK, rdot=0.0, t=10.0):
    return TrackState(t=t, status=status, los_ned=u, los_rate_ned=(0.0, 0.0, 0.0), range_m=r,
                      range_sigma_m=1.0, range_rate_mps=rdot, range_valid=True)


def prev_cmd(v=(0.0, 0.0, 0.0), dt=0.1, t=10.0, reason="track"):
    return GuidanceCommand(t=t - dt, vel_ned=v, yaw_rad=0.0, valid=True, reason=reason)


# ---------------- T1: khong con phanh tu khoa khi COAST ----------------
CFG25 = GuidanceConfig(cam_tilt_up_deg=0.0, range_set_m=25.0)   # nhu ho so nghiem thu giu 25 m


def _warm_at(g, speed, n=60, t0=10.0, r=15.0):
    o = own(v=(speed, 0.0, 0.0))
    t = t0
    for _ in range(n):
        g.step(track(r=r, rdot=0.0, t=t), o)
        t += DT
    return t


def _coast_lagged(seconds, a_prev, r=23.5, tau=0.6):
    """Kich ban 10: nho 8.6 m/s, lenh truoc 8.2 m/s voi gia toc a_prev, khoang cach dong bang 23.5 < r_dat 25
    (COAST: thanh phan P lui ra keo lenh cham xuong); van toc that bam lenh qua tre bac nhat tau.
    Tra ve (toc do ngang lenh cuoi, lenh cuoi)."""
    g = Guidance(CFG25)
    t = _warm_at(g, 8.6, r=r)
    g.prev = prev_cmd(v=(8.2, 0.0, 0.0), dt=DT, t=t)
    g.prev_accel = (a_prev, 0.0, 0.0)
    v = np.array([8.6, 0.0, 0.0])
    c = None
    for k in range(int(round(seconds / DT))):
        c = g.step(track(r=r, status=TrackStatus.COAST, t=t + (k + 1) * DT), own(v=tuple(v)))
        v = v + (np.array(c.vel_ned) - v) * (1.0 - math.exp(-DT / tau))
    return math.hypot(c.vel_ned[0], c.vel_ned[1]), c


@pytest.mark.parametrize("a_prev", [-2.85, -1.0, 0.0])
def test_coast_after_light_braking_follows_remembered_velocity_not_zero(a_prev):
    # thiet ke: giu 1 s roi giam blind_decel 1 m/s^2 => ~8.6 - 2 = 6.6 m/s sau 3 s (khong tu khoa ve ~0)
    sp, c = _coast_lagged(3.0, a_prev)
    assert "coast" in c.reason
    assert sp >= 4.0, "toc do ngang lenh sau 3 s COAST = %.2f (ky vong ~6, >= 4.0; ma cu ~0.9)" % sp


def test_coast_decay_rate_follows_blind_decel_design():
    # 4 s COAST tu 8.6: thiet ke 8.6 - 1.0*(4-1) = 5.6 (them thanh phan P lui ra nho); cua so [4.0, 6.5]
    sp, _ = _coast_lagged(4.0, -2.85)
    assert 4.0 <= sp <= 6.5, sp

def test_safe_hold_part1_caps_hold_to_own_horizontal_speed():
    # GIU phan (1): van toc giu vo ly (nho 10 m/s) khi minh chi bay 4 m/s thi bi chan o 4 m/s
    g = Guidance(CFG)
    t = _warm_at(g, 10.0)
    g.prev = prev_cmd(v=(4.0, 0.0, 0.0), dt=DT, t=t)
    g.prev_accel = (0.0, 0.0, 0.0)
    h = g._safe_hold((10.0, 0.0, 0.0), own(v=(4.0, 0.0, 0.0)), t)
    assert math.hypot(h[0], h[1]) == pytest.approx(4.0, abs=1e-9)
    c = g.step(track(r=15.0, status=TrackStatus.COAST, t=t), own(v=(4.0, 0.0, 0.0)))
    assert c.vel_ned[0] <= 4.0 + 1e-6


def test_safe_hold_does_not_clamp_hold_when_previous_accel_was_braking():
    # truc tiep: prev_accel = -3 (dang phanh), prev v = 6; van toc giu 8 va minh dang bay 8 => giu nguyen 8
    g = Guidance(CFG)
    t = _warm_at(g, 8.0)
    g.prev = prev_cmd(v=(6.0, 0.0, 0.0), dt=DT, t=t)
    g.prev_accel = (-3.0, 0.0, 0.0)
    h = g._safe_hold((8.0, 0.0, 0.0), own(v=(8.0, 0.0, 0.0)), t)
    assert h[0] == pytest.approx(8.0, abs=1e-9)


# ---------------- T2: descend_max_mps = 4.8 ----------------
def test_descend_max_default_is_4_8():
    assert GuidanceConfig().descend_max_mps == pytest.approx(4.8)


def test_descend_command_saturates_at_4_8_when_target_descends_faster():
    cfg = GuidanceConfig(cam_tilt_up_deg=0.0)
    # muc tieu hat xuong 7 m/s (v_own z = +7, NED xuong duong), lenh truoc dang 4.7 m/s xuong
    c = compute_guidance(track(r=15.0), own(v=(0.0, 0.0, 7.0), alt=80.0), cfg,
                         prev_cmd(v=(0.0, 0.0, 4.7), dt=0.2))
    assert c.vel_ned[2] == pytest.approx(4.8, abs=1e-6)
    # lap nhieu chu ky: van bao hoa o 4.8, khong vuot
    g = Guidance(cfg)
    for k in range(120):
        c = g.step(track(r=15.0, t=10.0 + k * DT), own(v=(0.0, 0.0, 7.0), alt=80.0))
    assert c.vel_ned[2] == pytest.approx(4.8, abs=1e-6)


# ---------------- T3: range_back_m ----------------
# cau hinh "lui som" nhu ho so nghiem thu giu 25 m: range_back 15 (> range_min 12,5), range_set 25
CFGB = GuidanceConfig(cam_tilt_up_deg=0.0, range_set_m=25.0, range_back_m=15.0)


def test_range_back_default_equals_range_min_so_no_early_back():
    g = GuidanceConfig()
    assert g.range_back_m == pytest.approx(12.5)
    assert g.range_min_m == pytest.approx(12.5)


def test_accept_profile_sets_range_back_15():
    cfg = load_profile("accept_gimbal_r25")
    assert cfg.guidance.range_back_m == pytest.approx(15.0)
    assert cfg.guidance.range_min_m == pytest.approx(12.5)


def test_default_config_does_not_back_off_at_14m():
    c = compute_guidance(track(r=14.0), own(v=(6.0, 0.0, 0.0)), CFG, prev_cmd(v=(6.0, 0.0, 0.0)))
    assert "min_range" not in c.reason


def test_back_mode_active_at_14m_between_range_min_and_range_back():
    c = compute_guidance(track(r=14.0), own(v=(6.0, 0.0, 0.0)), CFGB, prev_cmd(v=(6.0, 0.0, 0.0)))
    assert "min_range" in c.reason
    assert float(np.dot(c.vel_ned, (1.0, 0.0, 0.0))) < 6.0 - 0.5


def test_back_mode_uses_a_back_accel_limit_at_14m():
    dt = 0.1
    c = compute_guidance(track(r=14.0), own(v=(6.0, 0.0, 0.0)), CFGB, prev_cmd(v=(6.0, 0.0, 0.0), dt=dt))
    dv = 6.0 - c.vel_ned[0]
    assert dv > CFGB.a_decel_mps2 * dt + 0.3, dv
    assert dv <= CFGB.a_back_mps2 * dt + 1e-6, dv


def test_back_mode_not_active_at_16m():
    c = compute_guidance(track(r=16.0), own(v=(6.0, 0.0, 0.0)), CFGB, prev_cmd(v=(6.0, 0.0, 0.0)))
    assert "min_range" not in c.reason


def test_back_mode_hysteresis_stays_until_range_back_plus_hyst():
    g = Guidance(CFGB)
    o = own(v=(0.0, 0.0, 0.0))
    exit_r = CFGB.range_back_m + CFGB.range_min_hyst_m
    assert "min_range" in g.step(track(r=14.0, t=10.0), o).reason
    assert "min_range" in g.step(track(r=CFGB.range_back_m + 0.5, t=10.03), o).reason
    assert "min_range" not in g.step(track(r=exit_r + 0.5, t=10.06), o).reason


def test_range_back_below_range_min_is_rejected_by_validate():
    cfg = AppConfig()
    cfg.guidance.range_back_m = 13.0           # hop le: >= range_min 12.5, va set 15 >= 13 + 1
    validate(cfg)
    cfg.guidance.range_back_m = 12.0           # < range_min 12.5
    with pytest.raises(ValueError):
        validate(cfg)


def test_range_set_below_range_back_plus_hyst_is_rejected_by_validate():
    cfg = AppConfig()
    cfg.guidance.range_set_m = 15.0
    cfg.guidance.range_back_m = 14.0           # 15 >= 14 + 1: dung bien, hop le
    validate(cfg)
    cfg.guidance.range_back_m = 15.0           # 15 < 15 + 1
    with pytest.raises(ValueError):
        validate(cfg)


def test_range_back_below_range_min_is_rejected_by_load_config(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"guidance": {"range_back_m": 14.0}}))
    assert load_config(str(p)).guidance.range_back_m == pytest.approx(14.0)   # khoa phai duoc chap nhan
    p.write_text(json.dumps({"guidance": {"range_back_m": 12.0}}))
    with pytest.raises(ValueError, match="range_back"):
        load_config(str(p))


def test_range_set_below_range_back_plus_hyst_is_rejected_by_load_config(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"guidance": {"range_set_m": 15.0, "range_back_m": 14.0}}))
    load_config(str(p))
    p.write_text(json.dumps({"guidance": {"range_set_m": 15.0, "range_back_m": 15.0}}))
    with pytest.raises(ValueError):
        load_config(str(p))


# ---------------- hoi quy co nhieu: mac dinh khong duoc dao dong lui/tien ----------------
@pytest.mark.parametrize("target_speed", [0.0, 5.0])
def test_noisy_range_default_config_keeps_range_in_narrow_band(target_speed):
    # 1 chieu doc duong ngam; nhieu do r sigma 0,3 m; van toc that bam lenh qua tre bac nhat 0,6 s; 60 s
    rng = np.random.default_rng(12345)
    g = Guidance(CFG)
    tau = 0.6
    x_t, x_c, v = 15.0, 0.0, target_speed
    alpha = 1.0 - math.exp(-DT / tau)
    rs, back = [], 0
    for k in range(int(60.0 / DT)):
        r = x_t - x_c
        tr = track(r=r + float(rng.normal(0.0, 0.3)), rdot=target_speed - v, t=10.0 + k * DT)
        c = g.step(tr, own(v=(v, 0.0, 0.0)))
        v += (c.vel_ned[0] - v) * alpha
        x_c += v * DT
        x_t += target_speed * DT
        rs.append(x_t - x_c)
        back += "min_range" in c.reason
    rs = np.array(rs)
    assert rs.min() >= 12.5 - 0.3 and rs.max() <= 18.0, (rs.min(), rs.max())
    assert back / len(rs) < 0.1, back / len(rs)
