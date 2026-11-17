"""Hình học ước lượng: góc lệch so với trục quang và khoảng cách theo bề rộng.

Quy ước: yaw dương = mục tiêu lệch sang PHẢI tâm ảnh; pitch dương = lệch LÊN TRÊN.
Mọi giá trị pixel là pixel của khung hình đã xử lý (sau khi thu nhỏ nếu có).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float

    @classmethod
    def from_hfov(cls, width: int, height: int, hfov_deg: float) -> "Intrinsics":
        if not (1.0 <= hfov_deg <= 179.0):
            raise ValueError("hfov_deg phải nằm trong [1, 179]")
        fx = (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
        return cls(fx=fx, fy=fx, cx=width / 2.0, cy=height / 2.0)

    @classmethod
    def build(cls, width: int, height: int, hfov_deg: float,
              fx: Optional[float] = None, fy: Optional[float] = None,
              cx: Optional[float] = None, cy: Optional[float] = None) -> "Intrinsics":
        base = cls.from_hfov(width, height, hfov_deg)
        fx_ = fx if fx is not None else base.fx
        return cls(fx=fx_, fy=fy if fy is not None else fx_,
                   cx=cx if cx is not None else base.cx,
                   cy=cy if cy is not None else base.cy)


def box_center(box: Sequence[float]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def angle_offsets(k: Intrinsics, box: Sequence[float]) -> tuple[float, float]:
    """Trả về (yaw_deg, pitch_deg) của tâm khung bao so với trục quang."""
    u, v = box_center(box)
    yaw = math.degrees(math.atan2(u - k.cx, k.fx))
    pitch = math.degrees(math.atan2(k.cy - v, k.fy))
    return yaw, pitch


def estimate_distance(k: Intrinsics, box: Sequence[float], real_width_m: float) -> Optional[float]:
    """Khoảng cách (m) = fx * bề_rộng_thật / bề_rộng_khung_bao. None nếu khung bao suy biến."""
    w = box[2] - box[0]
    if w <= 0 or real_width_m <= 0:
        return None
    return k.fx * real_width_m / w
