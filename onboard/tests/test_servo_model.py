"""Buoc 3 cua thiet ke khop gat (.office/design-gimbal-steps-3-6.md): ServoModel + SimGimbalPort - TEST VIET TRUOC (pha do).

San pham can lam cho test pass: simtools/servo_model.py voi ServoModel va SimGimbalPort.
Moi test import LAZY (ham _sm) de moi test do rieng vi thieu module, khong gop thanh mot loi thu thap.

Tat ca thong so servo TRUYEN VAO (gia dinh), khong dua vao mac dinh. Don vi: rad trong ma, test doi tu do.
Cach hieu da chon cho cho mo ho cua thiet ke (xem them bao cao):
  - quant_rad = 0 nghia la KHONG luong tu (validate cho phep quant >= 0). Cac test khac dung quant rat nho 1e-9.
  - Lenh thoi diem t_cmd co hieu luc khi t - dead_time >= t_cmd.
  - command() tra ve gia tri DA kep roi luong tu; SimGimbalPort.last_cmd = gia tri do (test chi dung goc nam tren
    luoi luong tu nen cach hieu nao cung cho cung ket qua).
  - last_rate_rad_s = (delta moi - delta cu)/dt cua lan advance gan nhat (co dau).
"""
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

D = math.radians
BIG_RATE = 1.0e6          # rad/s: coi nhu khong gioi han toc do
TINY_Q = 1.0e-9           # rad: luong tu rat nho (gan nhu tat)


def _sm():
    import simtools.servo_model as m
    return m


def make(init_deg=20.0, lo_deg=10.0, hi_deg=90.0, rate=BIG_RATE, lag=0.05, dead=0.0, quant=TINY_Q, slow=1.0):
    return _sm().ServoModel(delta_init_rad=D(init_deg), delta_min_rad=D(lo_deg), delta_max_rad=D(hi_deg),
                            rate_rad_s=rate, lag_s=lag, dead_time_s=dead, quant_rad=quant, slow_factor=slow)


# ---------------------------------------------------------------- (1) kep gioi han
def test_command_outside_limits_is_clamped_and_returned_clamped():
    s = make()
    s.advance(0.0)
    assert s.command(0.0, D(200.0)) == pytest.approx(D(90.0), abs=1e-9)
    assert s.command(0.0, D(-50.0)) == pytest.approx(D(10.0), abs=1e-9)


def test_actual_angle_never_leaves_limits_under_extreme_commands():
    s = make(lag=0.02)
    s.advance(0.0)
    lo, hi = D(10.0) - 1e-9, D(90.0) + 1e-9
    t = 0.0
    for k in range(400):
        t = k * 0.005
        s.command(t, D(500.0) if (k // 40) % 2 == 0 else D(-500.0))
        assert lo <= s.advance(t) <= hi
    # cuoi chu ky lenh am: ve sat can duoi
    assert s.advance(t + 5.0) == pytest.approx(D(10.0), abs=1e-6)


# ---------------------------------------------------------------- (2) gioi han toc do
def test_rate_limit_bounds_step_and_slews_at_rate():
    # lag 1 ms, rate 300 do/s, nhay 40 do (20 -> 60) trong 10 ms: toi da 300*0.01 = 3.0 do.
    s = make(rate=D(300.0), lag=1e-3)
    s.advance(0.0)
    s.command(0.0, D(60.0))
    d = s.advance(0.010)
    moved = d - D(20.0)
    assert moved <= D(3.0) + 1e-9
    assert moved >= D(2.9)                       # lag 1 ms nen gan nhu quay het toc do toi da
    assert s.last_rate_rad_s == pytest.approx(D(300.0), rel=0.02)


def test_rate_limit_holds_for_every_call_step():
    s = make(rate=D(300.0), lag=1e-3)
    s.advance(0.0)
    s.command(0.0, D(80.0))
    prev, tp = s.advance(0.0), 0.0
    for k in range(1, 100):
        t = k * 0.004
        cur = s.advance(t)
        assert abs(cur - prev) <= D(300.0) * (t - tp) + 1e-9
        prev, tp = cur, t


# ---------------------------------------------------------------- (3) tre bac nhat
def test_first_order_reaches_63_percent_after_one_tau():
    # tay: tau = 0.05 s, buoc 20 -> 60 do (40 do). Sau 1 tau: 1 - e^-1 = 0.63212 => 20 + 40*0.63212 = 45.285 do.
    s = make(lag=0.05, dead=0.0)
    s.advance(0.0)
    s.command(0.0, D(60.0))
    d = s.advance(0.05)
    assert math.degrees(d) == pytest.approx(20.0 + 40.0 * (1.0 - math.exp(-1.0)), abs=0.05)
    # va 2 tau: 1 - e^-2 = 0.86466 => 54.586 do
    assert math.degrees(s.advance(0.10)) == pytest.approx(20.0 + 40.0 * (1.0 - math.exp(-2.0)), abs=0.05)


# ---------------------------------------------------------------- (4) thoi gian chet
def test_command_has_no_effect_before_dead_time_elapsed():
    # lenh luc t=1.0, dead=0.1: den 1.099 van dung yen o 20 do (chinh xac), sau do moi di.
    s = make(dead=0.1, lag=0.05)
    s.advance(0.0)
    s.advance(0.5)
    s.command(1.0, D(60.0))
    assert s.advance(1.0) == pytest.approx(D(20.0), abs=1e-9)
    assert s.advance(1.099) == pytest.approx(D(20.0), abs=1e-9)
    assert s.advance(1.12) > D(20.0) + 1e-4       # da qua t_cmd + dead
    # tay: sau do ~10 tau (0.5 s) -> 60 do trong 0.1 do
    assert math.degrees(s.advance(1.1 + 0.5)) == pytest.approx(60.0, abs=0.1)


def test_dead_time_picks_latest_command_at_or_before_t_minus_dead():
    # hai lenh: 50 do luc 1.0, 30 do luc 1.05; dead 0.1. Tai 1.12: chi lenh 50 co hieu luc (lenh 30 den 1.15).
    # Voi lag lon (0.5 s) delta tien ve 50 (tang), khong co dau hieu quay ve 30 truoc 1.15.
    s = make(dead=0.1, lag=0.5)
    s.advance(0.0)
    s.command(1.0, D(50.0))
    s.command(1.05, D(30.0))
    a = s.advance(1.12)
    b = s.advance(1.149)
    assert a > D(20.0) and b > a                 # van duoi theo 50 do
    # cuoi cung hoi tu ve lenh moi nhat (30 do)
    assert math.degrees(s.advance(1.15 + 10.0)) == pytest.approx(30.0, abs=0.05)


# ---------------------------------------------------------------- (5) luong tu
def test_command_is_quantized_to_grid():
    s = make(quant=D(0.1))
    s.advance(0.0)
    out = s.command(0.0, D(45.04))            # 45.04/0.1 = 450.4 -> round 450 -> 45.0 do
    assert out == pytest.approx(D(45.0), abs=1e-9)
    assert s.command(0.0, D(45.06)) == pytest.approx(D(45.1), abs=1e-9)   # 450.6 -> 451
    # goc thuc su toi duoc la 45.0, khong phai 45.04
    s.command(1.0, D(45.04))
    assert math.degrees(s.advance(1.0 + 5.0)) == pytest.approx(45.0, abs=1e-4)


def test_zero_quant_means_no_quantization():
    s = make(quant=0.0)
    s.advance(0.0)
    assert s.command(0.0, D(45.04)) == pytest.approx(D(45.04), abs=1e-12)


# ---------------------------------------------------------------- (6) slow_factor
def _t_cross(slow, lag, dead, rate, target_deg, init_deg=20.0, cmd_deg=60.0, dt=0.001):
    s = make(init_deg=init_deg, lag=lag, dead=dead, rate=rate, slow=slow)
    s.advance(0.0)
    s.command(0.0, D(cmd_deg))
    t = 0.0
    while t < 5.0:
        t += dt
        if s.advance(t) >= D(target_deg):
            return t
    raise AssertionError("khong toi duoc %s do" % target_deg)


def test_slow_factor_doubles_lag_plus_dead_response_time():
    # tay: 50% buoc (40 do -> 40 do muc 40) toi o t = dead + tau*ln2.
    #   slow 1: 0.02 + 0.05*0.6931 = 0.0547 s ;  slow 2: 0.04 + 0.10*0.6931 = 0.1093 s  (ti so 2)
    t1 = _t_cross(1.0, 0.05, 0.02, BIG_RATE, 40.0)
    t2 = _t_cross(2.0, 0.05, 0.02, BIG_RATE, 40.0)
    assert t1 == pytest.approx(0.02 + 0.05 * math.log(2.0), abs=0.004)
    assert t2 / t1 == pytest.approx(2.0, rel=0.05)


def test_slow_factor_halves_rate_limit():
    # lag ~ 0, rate 100 do/s, di 20 -> 60 (qua 40 do): can 0.2 s o slow 1, 0.4 s o slow 2.
    t1 = _t_cross(1.0, 1e-4, 0.0, D(100.0), 40.0)
    t2 = _t_cross(2.0, 1e-4, 0.0, D(100.0), 40.0)
    assert t1 == pytest.approx(0.2, abs=0.01)
    assert t2 / t1 == pytest.approx(2.0, rel=0.05)


def test_slow_factor_scales_dead_time():
    # dead 0.04 * 2 = 0.08: o t=0.07 chua nhuc nhich; slow 1 (dead 0.04) da di o t=0.07.
    s2 = make(dead=0.04, lag=0.05, slow=2.0)
    s1 = make(dead=0.04, lag=0.05, slow=1.0)
    for s in (s1, s2):
        s.advance(0.0)
        s.command(0.0, D(60.0))
    assert s2.advance(0.07) == pytest.approx(D(20.0), abs=1e-9)
    assert s1.advance(0.07) > D(20.0) + 1e-3


# ---------------------------------------------------------------- (7) khong phu thuoc nhip goi
def _run_at(hz):
    s = make(rate=D(300.0), lag=0.05, dead=0.02, quant=D(0.1))
    sched = [(0.0, 30.0), (0.3, 70.0), (0.8, 40.0)]
    out = {}
    for k in range(int(round(1.2 * hz)) + 1):
        t = k / hz
        for tc, deg in sched:
            if abs(t - tc) < 1e-9:
                s.command(t, D(deg))
        d = s.advance(t)
        if abs(t * 10.0 - round(t * 10.0)) < 1e-9:
            out[round(t * 10.0)] = math.degrees(d)
    return out


def test_result_independent_of_call_rate_30hz_vs_200hz():
    # Moc chung moi 0.1 s (3 buoc 30 Hz = 20 buoc 200 Hz). Thiet ke: sai <= 0.1 do.
    a, b = _run_at(30.0), _run_at(200.0)
    assert sorted(a) == sorted(b) and len(a) >= 12
    for k in a:
        assert abs(a[k] - b[k]) <= 0.1, "t=%.1f: 30Hz %.3f vs 200Hz %.3f" % (k / 10.0, a[k], b[k])


# ---------------------------------------------------------------- (8) t lui / lap
def test_time_repeat_or_backward_does_not_change_state():
    s, ref = make(lag=0.05, dead=0.01), make(lag=0.05, dead=0.01)
    for x in (s, ref):
        x.advance(0.0)
        x.command(0.0, D(60.0))
    v = s.advance(0.04)
    assert s.advance(0.04) == v                      # lap
    assert s.advance(0.02) == v                      # lui: khong lui gia tri
    assert s.advance(0.0) == v
    ref.advance(0.04)
    assert s.advance(0.2) == pytest.approx(ref.advance(0.2), abs=1e-12)   # khong lech ve sau


def test_command_time_is_monotonic_a_late_stamp_does_not_reorder_queue():
    # t_cmd = max(t, t_cmd truoc): lenh b gui voi t cu hon van xep SAU lenh a => b thang.
    s = make(lag=0.02)
    s.advance(0.0)
    s.command(2.0, D(70.0))
    s.command(1.0, D(40.0))
    s.advance(0.0)
    assert math.degrees(s.advance(5.0)) == pytest.approx(40.0, abs=0.05)


# ---------------------------------------------------------------- (9) chua lenh
def test_without_command_holds_delta_init():
    s = make(init_deg=75.0, dead=0.02)
    assert s.advance(0.0) == pytest.approx(D(75.0), abs=1e-12)
    for t in (0.1, 1.0, 10.0):
        assert s.advance(t) == pytest.approx(D(75.0), abs=1e-12)
    assert s.last_rate_rad_s == pytest.approx(0.0, abs=1e-12)


def test_first_advance_returns_delta_init_even_at_large_t():
    s = make(init_deg=75.0)
    assert s.advance(123.456) == pytest.approx(D(75.0), abs=1e-12)


def test_command_before_first_advance_does_not_jump_at_first_call():
    s = make(init_deg=20.0, dead=0.0)
    s.command(0.0, D(60.0))
    assert s.advance(0.0) == pytest.approx(D(20.0), abs=1e-12)    # lan goi dau tra delta_init
    assert s.advance(5.0) == pytest.approx(D(60.0), abs=1e-3)


# ---------------------------------------------------------------- (10) reset
def test_reset_restores_init_and_clears_queue_and_rate():
    s = make(init_deg=20.0, rate=D(300.0), lag=0.02)
    s.advance(0.0)
    s.command(0.0, D(80.0))
    s.advance(0.05)
    assert s.last_rate_rad_s != 0.0
    s.reset()
    assert s.last_rate_rad_s == 0.0
    assert s.advance(100.0) == pytest.approx(D(20.0), abs=1e-12)   # lan goi dau sau reset
    assert s.advance(101.0) == pytest.approx(D(20.0), abs=1e-12)   # lenh cu khong con hieu luc


def test_reset_with_new_init():
    s = make(init_deg=20.0)
    s.advance(0.0)
    s.reset(delta_init_rad=D(55.0))
    assert s.advance(0.0) == pytest.approx(D(55.0), abs=1e-12)
    assert s.advance(3.0) == pytest.approx(D(55.0), abs=1e-12)


def test_reset_allows_time_to_restart_earlier():
    s = make()
    s.advance(10.0)
    s.reset()
    s.command(0.0, D(60.0))
    s.advance(0.0)
    assert s.advance(2.0) == pytest.approx(D(60.0), abs=1e-3)


# ---------------------------------------------------------------- from_config
def test_from_config_converts_degrees_to_radians():
    from dtrack.config import GimbalConfig
    g = GimbalConfig(delta_min_deg=15.0, delta_max_deg=80.0, delta_init_deg=40.0,
                     rate_dps=200.0, lag_s=0.03, dead_time_s=0.0, quant_deg=0.5, slow_factor=1.0)
    s = _sm().ServoModel.from_config(g)
    assert s.advance(0.0) == pytest.approx(D(40.0), abs=1e-12)
    assert s.command(0.0, D(170.0)) == pytest.approx(D(80.0), abs=1e-9)    # delta_max_deg
    assert s.command(0.0, D(1.0)) == pytest.approx(D(15.0), abs=1e-9)      # delta_min_deg
    assert s.command(0.0, D(50.3)) == pytest.approx(D(50.5), abs=1e-9)     # quant_deg 0.5: 50.3 -> 50.5


def test_from_config_uses_rate_and_slow_factor():
    from dtrack.config import GimbalConfig
    g = GimbalConfig(delta_min_deg=10.0, delta_max_deg=90.0, delta_init_deg=20.0,
                     rate_dps=100.0, lag_s=1e-4, dead_time_s=0.0, quant_deg=0.0, slow_factor=2.0)
    s = _sm().ServoModel.from_config(g)
    s.advance(0.0)
    s.command(0.0, D(80.0))
    # rate 100/slow 2 = 50 do/s: sau 0.2 s toi da 10 do
    moved = s.advance(0.2) - D(20.0)
    assert moved == pytest.approx(D(10.0), abs=D(0.3))


# ---------------------------------------------------------------- SimGimbalPort
def test_port_command_and_angle_match_underlying_servo():
    m = _sm()
    twin = make(rate=D(300.0), lag=0.05, dead=0.02, quant=D(0.1))
    port = m.SimGimbalPort(make(rate=D(300.0), lag=0.05, dead=0.02, quant=D(0.1)))
    assert port.angle(0.0) == pytest.approx(twin.advance(0.0), abs=1e-12)
    port.command(0.0, D(50.0))
    twin.command(0.0, D(50.0))
    for k in range(1, 40):
        t = k * 0.01
        assert port.angle(t) == pytest.approx(twin.advance(t), abs=1e-12)


def test_port_last_cmd_and_rate():
    port = _sm().SimGimbalPort(make(rate=D(300.0), lag=1e-3))
    port.angle(0.0)
    port.command(0.0, D(50.0))                 # 50.0 do nam tren luoi, trong gioi han
    assert port.last_cmd == pytest.approx(D(50.0), abs=1e-9)
    port.angle(0.01)
    assert port.rate() == pytest.approx(D(300.0), rel=0.02)


def test_port_reset_returns_to_init():
    port = _sm().SimGimbalPort(make(init_deg=20.0, lag=0.02))
    port.angle(0.0)
    port.command(0.0, D(80.0))
    assert port.angle(1.0) > D(70.0)
    port.reset()
    assert port.angle(5.0) == pytest.approx(D(20.0), abs=1e-12)
    assert port.rate() == pytest.approx(0.0, abs=1e-12)
