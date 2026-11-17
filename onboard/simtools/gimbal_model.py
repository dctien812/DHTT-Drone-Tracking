"""Mo hinh khop gat mot truc (servo) on dinh pitch cho camera, CHI dung trong mo phong / do dac.

Camera giu huong nhin theo phuong NGANG cua the gioi cong goc ngam co dinh san co (tilt_up); roll va yaw van
theo than. Khop co hanh trinh gioi han +-travel quanh vi tri lap danh dinh, toc do quay toi da va tre bac nhat.

step(t, q_body) tra ve quaternion "than hieu dung" q_eff = euler(roll, pitch_than + delta, yaw): dung cung R_body_cam
danh dinh de chieu tia (camera that = q_eff * R_body_cam). Phan mem bam dung q_eff cho tracker; guidance giu nguyen
q than (guidance tinh lech dung trong khung chi giu yaw nen khong bu hai lan).
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

from dtrack.geometry import quat_from_euler


def euler_from_quat(q) -> Tuple[float, float, float]:
    w, x, y, z = q
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    s = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(s)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return roll, pitch, yaw


class GimbalModel:
    def __init__(self, travel_deg: float = 50.0, rate_dps: float = 300.0, lag_s: float = 0.05):
        self.travel = math.radians(travel_deg)
        self.rate = math.radians(rate_dps)
        self.lag = max(float(lag_s), 1e-6)
        self.reset()

    def reset(self) -> None:
        self.delta = 0.0                       # rad, goc khop so voi vi tri lap danh dinh (cong vao pitch than)
        self._t: Optional[float] = None
        self.last_rate = 0.0                   # rad/s, toc do quay vua roi

    def advance(self, t: float, pitch_body: float) -> float:
        """Cap nhat khop toi thoi diem t (giay, dong ho don dieu); tra ve delta (rad)."""
        if self._t is None or not (t > self._t):
            if self._t is None:
                self.delta = max(-self.travel, min(self.travel, -pitch_body))   # khoi dong: da on dinh
                self._t = t
            return self.delta
        dt = t - self._t
        self._t = t
        cmd = max(-self.travel, min(self.travel, -pitch_body))     # lenh: huy pitch than
        # tre bac nhat (loi giai chinh xac theo buoc dt) roi gioi han toc do quay
        want = (cmd - self.delta) * (1.0 - math.exp(-dt / self.lag))
        step = max(-self.rate * dt, min(self.rate * dt, want))
        self.delta = max(-self.travel, min(self.travel, self.delta + step))
        self.last_rate = step / dt
        return self.delta

    def step(self, t: float, q_body):
        roll, pitch, yaw = euler_from_quat(q_body)
        d = self.advance(t, pitch)
        q = quat_from_euler(roll, pitch + d, yaw)
        return tuple(float(c) for c in q), d
