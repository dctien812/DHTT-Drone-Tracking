import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.geometry import (angle_between, pixel_to_los_ned, project_ned_point,
                             quat_conjugate, quat_from_euler, quat_multiply,
                             quat_slerp, quat_to_matrix)
from dtrack.types import CameraModel

CAM = CameraModel()
Q_ID = (1.0, 0.0, 0.0, 0.0)
OWN = (0.0, 0.0, 0.0)
D2R = math.pi / 180.0


def px(q, target, own=OWN, **kw):
    return project_ned_point(CAM, q, own, target, **kw)


def test_quat_basics():
    q = quat_from_euler(0.3, -0.2, 1.1)
    assert np.allclose(quat_to_matrix(q) @ quat_to_matrix(q).T, np.eye(3), atol=1e-12)
    assert np.allclose(quat_multiply(q, quat_conjugate(q)), [1, 0, 0, 0], atol=1e-12)
    # yaw +90 deg: x_body (nose) -> East (0,1,0) in NED
    assert np.allclose(quat_to_matrix(quat_from_euler(0, 0, math.pi / 2)) @ [1, 0, 0], [0, 1, 0], atol=1e-12)
    # pitch +90 deg (nose up): x_body -> Up = (0,0,-1)
    assert np.allclose(quat_to_matrix(quat_from_euler(0, math.pi / 2, 0)) @ [1, 0, 0], [0, 0, -1], atol=1e-12)
    # roll +90 deg (right wing down): y_body (right) -> Down (0,0,1)
    assert np.allclose(quat_to_matrix(quat_from_euler(math.pi / 2, 0, 0)) @ [0, 1, 0], [0, 0, 1], atol=1e-12)
    # slerp giua hai tu the cho goc o giua
    mid = quat_slerp(quat_from_euler(0, 0, 0), quat_from_euler(0, 0, 0.4), 0.5)
    assert np.allclose(mid, quat_from_euler(0, 0, 0.2), atol=1e-9)


def test_target_ahead_is_image_center():
    for target in [(100.0, 0.0, 0.0), (5.0, 0.0, 0.0)]:
        u, v = px(Q_ID, target)
        assert u == pytest.approx(CAM.cx, abs=1e-9)
        assert v == pytest.approx(CAM.cy, abs=1e-9)


def test_hand_computed_offsets():
    f = CAM.fx
    # Muc tieu 100 m phia Bac, 10 m phia Dong (ben phai mui): u tang
    u, v = px(Q_ID, (100.0, 10.0, 0.0))
    assert (u, v) == pytest.approx((CAM.cx + f * 0.1, CAM.cy), abs=1e-9)
    # 10 m phia DUOI (NED z duong): v tang (y camera huong xuong)
    u, v = px(Q_ID, (100.0, 0.0, 10.0))
    assert (u, v) == pytest.approx((CAM.cx, CAM.cy + f * 0.1), abs=1e-9)
    # Yaw +90 (mui huong Dong). Muc tieu 100 Dong, 10 Bac: Bac nam ben TRAI mui -> u giam
    q = quat_from_euler(0, 0, 90 * D2R)
    u, v = px(q, (10.0, 100.0, 0.0))
    assert (u, v) == pytest.approx((CAM.cx - f * 0.1, CAM.cy), abs=1e-6)
    # Pitch +10 (ngang mui len): muc tieu ngang tam bay xuong duoi trong anh
    q = quat_from_euler(0, 10 * D2R, 0)
    u, v = px(q, (100.0, 0.0, 0.0))
    assert u == pytest.approx(CAM.cx, abs=1e-6)
    assert v == pytest.approx(CAM.cy + f * math.tan(10 * D2R), abs=1e-6)
    # Roll +10 (canh phai chuc xuong): vat o phia duoi 10 m (muc tieu 100 m phia truoc) dich sang PHAI
    q = quat_from_euler(10 * D2R, 0, 0)
    u, v = px(q, (100.0, 0.0, 10.0))
    s, c = math.sin(10 * D2R), math.cos(10 * D2R)
    assert (u, v) == pytest.approx((CAM.cx + f * 10 * s / 100, CAM.cy + f * 10 * c / 100), abs=1e-6)
    # Muc tieu phia tren (z am) voi pitch 0 -> v giam
    u, v = px(Q_ID, (100.0, 0.0, -10.0))
    assert v == pytest.approx(CAM.cy - f * 0.1, abs=1e-9)


def test_behind_and_outside_frame_return_none():
    assert px(Q_ID, (-50.0, 0.0, 0.0)) is None          # sau camera
    assert px(Q_ID, (100.0, 100.0, 0.0)) is None        # ngoai khung (45 do)
    assert px(Q_ID, (100.0, 100.0, 0.0), require_in_frame=False) is not None
    assert px(Q_ID, (0.0, 100.0, 0.0), require_in_frame=False) is None  # z_cam = 0
    # tu the lam muc tieu phia Nam di vao khung
    assert px(quat_from_euler(0, 0, math.pi), (-100.0, 0.0, 0.0)) is not None


def test_roundtrip_error_below_1e6():
    rng = np.random.default_rng(1)
    worst = 0.0
    for _ in range(200):
        q = quat_from_euler(*rng.uniform(-0.5, 0.5, 2), rng.uniform(-math.pi, math.pi))
        own = rng.uniform(-50, 50, 3)
        u0, v0 = rng.uniform(0, CAM.width), rng.uniform(0, CAM.height)
        los = pixel_to_los_ned(CAM, q, u0, v0)
        assert np.linalg.norm(los) == pytest.approx(1.0, abs=1e-12)
        target = own + rng.uniform(5, 80) * los
        u1, v1 = project_ned_point(CAM, q, own, target)
        worst = max(worst, abs(u1 - u0), abs(v1 - v0))
    assert worst < 1e-6
    # nguoc lai: diem NED -> pixel -> tia -> trung huong voi diem
    q = quat_from_euler(0.1, 0.2, 0.3)
    target = np.array([60.0, 10.0, -3.0])
    u, v = project_ned_point(CAM, q, OWN, target)
    assert angle_between(pixel_to_los_ned(CAM, q, u, v), target) < 1e-9
