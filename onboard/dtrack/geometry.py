"""Hinh hoc camera: pixel <-> tia nhin trong he camera / than / NED.

Chi dung numpy. Quy uoc theo types.py: quaternion (w, x, y, z) quay vector tu
than (FRD) sang the gioi (NED); camera x phai, y xuong, z quang truc;
R_body_cam quay vector tu camera sang than.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

import numpy as np

from .types import CameraModel

_BEHIND_EPS = 1e-9  # z_cam toi thieu de coi la truoc camera


# --------------------------------------------------------------------------
# Quaternion / ma tran quay
# --------------------------------------------------------------------------
def quat_normalize(q: Sequence[float]) -> np.ndarray:
    a = np.asarray(q, dtype=float)
    n = np.linalg.norm(a)
    if n == 0.0:
        raise ValueError("quaternion bang 0")
    return a / n


def quat_conjugate(q: Sequence[float]) -> np.ndarray:
    w, x, y, z = q
    return np.array([w, -x, -y, -z], dtype=float)


def quat_multiply(a: Sequence[float], b: Sequence[float]) -> np.ndarray:
    """Tich Hamilton a*b (ap dung b truoc, roi a)."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ], dtype=float)


def quat_to_matrix(q: Sequence[float]) -> np.ndarray:
    """Ma tran quay 3x3 (than -> the gioi) tu quaternion (w,x,y,z)."""
    w, x, y, z = quat_normalize(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ], dtype=float)


def quat_from_euler(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Quaternion than->NED tu goc Euler hang khong (thu tu Z-Y-X, rad).

    yaw quanh z (xuong), pitch quanh y (phai; duong = ngang mui len),
    roll quanh x (mui; duong = nghieng phai xuong).
    """
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return np.array([
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ], dtype=float)


def quat_slerp(q0: Sequence[float], q1: Sequence[float], s: float) -> np.ndarray:
    a = quat_normalize(q0)
    b = quat_normalize(q1)
    d = float(np.dot(a, b))
    if d < 0.0:
        b = -b
        d = -d
    if d > 0.9995:  # gan trung nhau: noi suy tuyen tinh
        return quat_normalize(a + s * (b - a))
    th = math.acos(min(1.0, d))
    return (math.sin((1 - s) * th) * a + math.sin(s * th) * b) / math.sin(th)


def body_cam_matrix(cam: CameraModel) -> np.ndarray:
    return np.asarray(cam.R_body_cam, dtype=float)


def camera_intrinsics(cam: CameraModel) -> np.ndarray:
    return np.array([[cam.fx, 0.0, cam.cx], [0.0, cam.fy, cam.cy], [0.0, 0.0, 1.0]])


# --------------------------------------------------------------------------
# Pixel <-> tia nhin
# --------------------------------------------------------------------------
def pixel_to_ray_cam(cam: CameraModel, u: float, v: float) -> np.ndarray:
    """Vector don vi trong he camera cua pixel (u, v)."""
    r = np.array([(u - cam.cx) / cam.fx, (v - cam.cy) / cam.fy, 1.0])
    return r / np.linalg.norm(r)


def ray_cam_to_ned(cam: CameraModel, q_world_body: Sequence[float],
                   ray_cam: Sequence[float]) -> np.ndarray:
    return quat_to_matrix(q_world_body) @ body_cam_matrix(cam) @ np.asarray(ray_cam, float)


def pixel_to_los_ned(cam: CameraModel, q_world_body: Sequence[float],
                     u: float, v: float) -> np.ndarray:
    """Vector don vi NED (tu camera toi pixel) cho tu the q_world_body."""
    return ray_cam_to_ned(cam, q_world_body, pixel_to_ray_cam(cam, u, v))


def project_cam_ray(cam: CameraModel, ray_cam: Sequence[float],
                    require_in_frame: bool = True) -> Optional[Tuple[float, float]]:
    """Chieu tia trong he camera ve pixel. None neu sau camera (z<=0) hoac,
    khi require_in_frame, nam ngoai khung."""
    x, y, z = (float(c) for c in ray_cam)
    if z <= _BEHIND_EPS:
        return None
    u = cam.fx * x / z + cam.cx
    v = cam.fy * y / z + cam.cy
    if require_in_frame and not (0.0 <= u < cam.width and 0.0 <= v < cam.height):
        return None
    return (u, v)


def project_los_ned(cam: CameraModel, q_world_body: Sequence[float],
                    los_ned: Sequence[float],
                    require_in_frame: bool = True) -> Optional[Tuple[float, float]]:
    """Chieu huong NED (khong can don vi) ve pixel."""
    ray_cam = (quat_to_matrix(q_world_body) @ body_cam_matrix(cam)).T @ np.asarray(los_ned, float)
    return project_cam_ray(cam, ray_cam, require_in_frame)


def project_ned_point(cam: CameraModel, q_world_body: Sequence[float],
                      own_pos_ned: Sequence[float], target_pos_ned: Sequence[float],
                      require_in_frame: bool = True) -> Optional[Tuple[float, float]]:
    """Chieu diem NED ve pixel (bo qua do lech camera so voi vi tri FC)."""
    d = np.asarray(target_pos_ned, float) - np.asarray(own_pos_ned, float)
    return project_los_ned(cam, q_world_body, d, require_in_frame)


def angle_between(a: Sequence[float], b: Sequence[float]) -> float:
    """Goc (rad) giua hai vector, on dinh so voi goc nho."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    return math.atan2(float(np.linalg.norm(np.cross(a, b))), float(np.dot(a, b)))
