"""Test mo hinh khop gat (hanh trinh, toc do quay, tre) va cau hinh."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.config import AppConfig, load_config
from dtrack.geometry import quat_from_euler
from simtools.gimbal_model import GimbalModel, euler_from_quat


def q(roll=0.0, pitch=0.0, yaw=0.0):
    return tuple(float(c) for c in quat_from_euler(roll, pitch, yaw))


def test_default_is_fixed_camera():
    cfg = AppConfig()
    assert cfg.camera.gimbal_enabled is False and cfg.guidance.elev_accel_comp == 1.0


def test_enabling_gimbal_disables_double_compensation(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"camera": {"gimbal_enabled": true}}')
    assert load_config(str(p)).guidance.elev_accel_comp == 0.0


def test_stabilizes_slow_pitch():
    g = GimbalModel(50, 300, 0.05)
    t = 0.0
    for k in range(200):
        t = k * 0.01
        qe, d = g.step(t, q(0.1, math.radians(20.0) * min(1.0, t), 0.3))   # pitch tang tu tu toi 20 do
    r, p, y = euler_from_quat(qe)
    assert abs(p) < math.radians(1.0) and abs(r - 0.1) < 1e-6 and abs(y - 0.3) < 1e-6


def test_travel_limit():
    g = GimbalModel(50, 300, 0.05)
    g.step(0.0, q())
    for k in range(1, 300):
        qe, d = g.step(k * 0.01, q(0.0, math.radians(80.0)))
    assert abs(d + math.radians(50.0)) < 1e-9            # kep o -50 do
    assert abs(euler_from_quat(qe)[1] - math.radians(30.0)) < 1e-6   # con du 30 do pitch


def test_rate_limit():
    g = GimbalModel(50, 300, 0.05)
    g.step(0.0, q())
    _, d = g.step(0.01, q(0.0, math.radians(40.0)))      # nhay 40 do trong 10 ms
    assert abs(d) <= math.radians(300.0) * 0.01 + 1e-9
    assert abs(g.last_rate) <= math.radians(300.0) + 1e-9


def test_first_order_lag():
    g = GimbalModel(50, 1e6, 0.05)                        # khong gioi han toc do
    g.step(0.0, q())
    _, d = g.step(0.05, q(0.0, math.radians(10.0)))       # 1 hang so thoi gian
    assert abs(d + math.radians(10.0) * (1 - math.exp(-1))) < 1e-6