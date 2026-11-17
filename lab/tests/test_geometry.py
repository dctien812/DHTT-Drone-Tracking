import math

import pytest

from labview.geometry import Intrinsics, angle_offsets, estimate_distance


def test_from_hfov_edge_is_half_fov():
    k = Intrinsics.from_hfov(1000, 600, 90.0)
    assert k.fx == pytest.approx(500.0)
    assert (k.cx, k.cy) == (500.0, 300.0)
    yaw, pitch = angle_offsets(k, (990, 295, 1010, 305))  # tâm ở mép phải ảnh (x=1000)
    assert yaw == pytest.approx(45.0)
    assert pitch == pytest.approx(0.0)


def test_center_is_zero():
    k = Intrinsics.from_hfov(640, 480, 66.0)
    yaw, pitch = angle_offsets(k, (310, 230, 330, 250))
    assert yaw == pytest.approx(0.0) and pitch == pytest.approx(0.0)


def test_signs_right_up():
    k = Intrinsics.from_hfov(640, 480, 66.0)
    yaw, pitch = angle_offsets(k, (400, 50, 420, 70))
    assert yaw > 0 and pitch > 0
    yaw, pitch = angle_offsets(k, (100, 400, 120, 420))
    assert yaw < 0 and pitch < 0


def test_explicit_intrinsics_override():
    k = Intrinsics.build(640, 480, 66.0, fx=800, cx=300)
    assert k.fx == 800 and k.fy == 800 and k.cx == 300 and k.cy == 240
    yaw, _ = angle_offsets(k, (790, 0, 810, 10))  # u=800, du=500
    assert yaw == pytest.approx(math.degrees(math.atan(500 / 800)))


def test_distance():
    k = Intrinsics(fx=1000.0, fy=1000.0, cx=0, cy=0)
    assert estimate_distance(k, (0, 0, 60, 30), 0.30) == pytest.approx(5.0)
    assert estimate_distance(k, (0, 0, 0, 30), 0.30) is None
    assert estimate_distance(k, (0, 0, 60, 30), 0.0) is None


def test_bad_fov():
    with pytest.raises(ValueError):
        Intrinsics.from_hfov(640, 480, 0)
