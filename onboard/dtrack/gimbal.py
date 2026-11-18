"""Hinh hoc khop gat camera mot truc (gimbal), don vi rad.

Quy uoc: quaternion (w, x, y, z) than FRD -> NED (xem geometry.py). delta la goc giua
truc quang va truc luc day (-z than); truc quang trong than = (sin d, 0, -cos d).
Camera attitude = q_body * Ry(90 do - delta): truc x (tien) cua camera = truc quang.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np

from .geometry import quat_multiply, quat_normalize, quat_to_matrix

DELTA_MIN_RAD = math.radians(10.0)
DELTA_MAX_RAD = math.radians(90.0)
_SAT_EPS = 1e-9


def _require_finite(*vals) -> None:
    if not all(np.all(np.isfinite(np.asarray(v, dtype=float))) for v in vals):
        raise ValueError("dau vao khong huu han")


def boresight_body(delta: float) -> Tuple[float, float, float]:
    """Truc quang trong he than (hinh hoc thuan, khong ket)."""
    _require_finite(delta)
    return (math.sin(delta), 0.0, -math.cos(delta))


def camera_attitude(q_wxyz: Sequence[float], delta: float) -> np.ndarray:
    """Quaternion don vi camera->NED = q_body * Ry(90 do - delta)."""
    _require_finite(q_wxyz, delta)
    q = quat_normalize(q_wxyz)
    a = (math.pi / 2 - delta) / 2
    q_joint = np.array([math.cos(a), 0.0, math.sin(a), 0.0])
    return quat_normalize(quat_multiply(q, q_joint))


def elev_to_delta(q_wxyz: Sequence[float], elev_target: float,
                  delta_min: float = DELTA_MIN_RAD,
                  delta_max: float = DELTA_MAX_RAD) -> Tuple[float, bool]:
    """Tim delta de truc quang co goc nang elev_target (rad, duong = len) trong NED.

    sin(elev) = -z_NED = A sin d + B cos d, A = -R[2,0], B = R[2,2] (R = than->NED)
              = C cos(d - phi), phi = atan2(A, B)  =>  d = phi +- acos(sin(elev)/C).
    Tra ve (delta da ket vao [min, max], sat). sat chi True khi nghiem chua ket lech
    ngoai gioi han qua 1e-9 rad hoac khong co nghiem (roll lon); khi do chon gioi han
    cho sai so sin(elev) nho nhat tren ca dai: ung vien gom hai gioi han va cac cuc tri
    d = phi, phi + pi neu roi vao dai.
    Hai nghiem cung trong dai: lay nhanh "+" (phi + k) truoc. C ~ 0 (than dung, truc
    delta khong doi elev) thi coi nhu khong co nghiem, roi vao nhanh bao hoa.
    """
    _require_finite(q_wxyz, elev_target, delta_min, delta_max)
    if delta_min > delta_max:
        raise ValueError("delta_min > delta_max")
    R = quat_to_matrix(q_wxyz)
    a, b = -float(R[2, 0]), float(R[2, 2])
    s = math.sin(elev_target)
    c = math.hypot(a, b)
    phi = math.atan2(a, b)
    if c > 1e-12 and abs(s) <= c:
        k = math.acos(s / c)
        for d in (phi + k, phi - k):
            d = math.atan2(math.sin(d), math.cos(d))
            if delta_min - _SAT_EPS <= d <= delta_max + _SAT_EPS:
                return float(min(max(d, delta_min), delta_max)), False
    cands = [delta_min, delta_max]
    for d in (phi, phi + math.pi):
        d = math.atan2(math.sin(d), math.cos(d))
        if delta_min <= d <= delta_max:
            cands.append(d)
    best = min(cands, key=lambda d: abs(a * math.sin(d) + b * math.cos(d) - s))
    return float(best), True
