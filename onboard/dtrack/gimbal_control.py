"""Bo dieu khien khop gat camera (buoc 4 cua .office/design-gimbal-steps-3-6.md).

Nhan quaternion than + trang thai bam -> lenh goc khop delta (rad). Khong vong I, khong tu gioi han toc do (servo lo).
"""
import math
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from .config import GimbalConfig
from .gimbal import elev_to_delta
from .types import TrackState, TrackStatus


@runtime_checkable
class GimbalPort(Protocol):
    def command(self, t: float, delta_rad: float) -> object: ...

    def angle(self, t: float) -> float: ...


@dataclass(frozen=True)
class GimbalCommand:
    t: float
    delta_cmd_rad: float
    sat: bool
    mode: str   # "init" | "track" | "coast" | "hold" | "hold_last" | "frozen"
    elev_los_rad: Optional[float]
    elev_aim_rad: Optional[float]


class GimbalController:
    def __init__(self, cfg: GimbalConfig):
        self.cfg = cfg
        self._init = math.radians(cfg.delta_init_deg)
        self._min = math.radians(cfg.delta_min_deg)
        self._max = math.radians(cfg.delta_max_deg)
        self._offset = math.radians(cfg.hold_offset_deg)
        self.reset()

    def reset(self) -> None:
        self._locked = False
        self._last_aim: Optional[float] = None
        self._last_delta: Optional[float] = None
        self._last_sat = False

    def step(self, t: float, q_body, track: TrackState) -> GimbalCommand:
        if self.cfg.frozen:
            return self._emit(t, self._init, False, "frozen", None, None)
        try:
            return self._step(t, q_body, track)
        except ValueError:
            d = self._init if self._last_delta is None else self._last_delta
            return GimbalCommand(t, d, self._last_sat, "hold_last", None, None)

    def _step(self, t, q_body, track: TrackState) -> GimbalCommand:
        if track.status in (TrackStatus.TRACK, TrackStatus.COAST):
            u = track.los_ned
            if u is not None:
                if len(u) != 3:
                    raise ValueError("los_ned sai dang")
                n = math.sqrt(sum(float(c) * float(c) for c in u))
                if not math.isfinite(n):
                    raise ValueError("los_ned khong huu han")
                if n >= 0.5:
                    elev_los = math.asin(max(-1.0, min(1.0, -float(u[2]) / n)))
                    aim = elev_los + self._offset
                    delta, sat = elev_to_delta(q_body, aim, self._min, self._max)
                    self._last_aim = aim
                    self._locked = True
                    mode = "track" if track.status is TrackStatus.TRACK else "coast"
                    return self._emit(t, delta, sat, mode, elev_los, aim)
            # los_ned None hoac norm < 0,5: xu ly nhu mat hinh (hold/init)
        if not self._locked:
            return self._emit(t, self._init, False, "init", None, None)
        delta, sat = elev_to_delta(q_body, self._last_aim, self._min, self._max)
        return self._emit(t, delta, sat, "hold", None, self._last_aim)

    def _emit(self, t, delta, sat, mode, elev_los, aim) -> GimbalCommand:
        self._last_delta = delta
        self._last_sat = sat
        return GimbalCommand(t, delta, sat, mode, elev_los, aim)
