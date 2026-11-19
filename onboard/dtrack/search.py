"""Khoi tim lai muc tieu khi mat (design-search.md muc (a), (c), (d), S-3, S-9). Logic thuan, khong I/O.

- tri_sweep: song tam giac theo quang duong.
- SearchEpisode: dong ho dot mat (tuyet doi tu COAST dau), chuoi TRACK lien tuc, dong dot, het han.
- SearchPlanner: quet khop + quet yaw (pha 1), them leo thang dung va dai quet thap (pha 2).
Ghep lenh ngang (step_hover), RTL va trang thai nam o supervisor.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .config import SearchConfig
from .types import OwnState, Vec3

_HOLD_EPS = 1e-9
_DT_MAX_S = 0.1           # dt toi da moi buoc quet (sau khi tam ngung quet, dt dau bi kep)
_CLIMB_MIN_HORIZ_M = 8.0  # p_stop phai cach it nhat chung nay theo phuong ngang moi duoc leo
_CLIMB_DONE_M = 0.25      # con <= chung nay thi dung leo


def tri_sweep(s: float, start: float, lo: float, hi: float, first_dir: int = 1) -> float:
    """Song tam giac: di tu start ve phia first_dir (+1 len hi, -1 xuong lo), phan xa o lo/hi; s = quang duong >= 0."""
    length = hi - lo
    if length <= 0.0:
        return lo
    p = ((start - lo) if first_dir >= 0 else (hi - start)) + s
    q = p % (2.0 * length)
    x = q if q <= length else 2.0 * length - q
    return lo + x if first_dir >= 0 else hi - x


@dataclass(frozen=True)
class EpisodeTick:
    ep_id: int
    ep_s: Optional[float]
    phase: Optional[int]
    closed: bool
    expired: bool
    run_s: float = 0.0


class SearchEpisode:
    """update(t, tracking, had_target): mo dot o chu ky dau co had_target ma khong TRACK; dong khi TRACK lien tuc
    >= reacquire_hold_s (closed True dung mot tick); expired khi ep_s > total_s."""

    def __init__(self, cfg: SearchConfig, coast_follow_s: float):
        self.cfg = cfg
        self.coast_follow_s = coast_follow_s
        self._ep_id = 0
        self.reset()

    def reset(self) -> None:
        self._t0: Optional[float] = None
        self._streak_t: Optional[float] = None

    def _phase(self, ep_s: float) -> int:
        if ep_s <= self.coast_follow_s:
            return 0
        if self.cfg.climb_m > 0.0 and ep_s >= self.cfg.climb_start_s:
            return 2
        return 1

    def update(self, t: float, tracking: bool, had_target: bool) -> EpisodeTick:
        if self._t0 is None:
            if not (had_target and not tracking):
                return EpisodeTick(self._ep_id, None, None, False, False)
            self._ep_id += 1
            self._t0 = t
            self._streak_t = None
        ep_s = t - self._t0
        run_s = 0.0
        if tracking:
            if self._streak_t is None:
                self._streak_t = t
            run_s = t - self._streak_t
            if run_s >= self.cfg.reacquire_hold_s - _HOLD_EPS:
                tk = EpisodeTick(self._ep_id, ep_s, self._phase(ep_s), True, False, run_s)
                self.reset()
                return tk
        else:
            self._streak_t = None
        return EpisodeTick(self._ep_id, ep_s, self._phase(ep_s), False, ep_s > self.cfg.total_s, run_s)


@dataclass(frozen=True)
class SearchInfo:
    ep_id: int
    ep_s: Optional[float]
    phase: Optional[int]
    run_s: float
    closed: bool
    climb_m: float
    scan_delta_rad: Optional[float]
    r_hat: Optional[float]


@dataclass(frozen=True)
class SearchOutput:
    vel_ned: Vec3                 # chi vz co y nghia (vx, vy do Guidance.step_hover cap)
    yaw_rad: Optional[float]
    scan_delta_rad: float
    climb_m: float                # do cao da tang luy ke (m)
    reason: str


class SearchPlanner:
    def __init__(self, cfg: SearchConfig, delta_min_rad: float, delta_max_rad: float):
        self.cfg = cfg
        self._lo = max(math.radians(cfg.scan_lo_deg), delta_min_rad)
        self._hi = min(math.radians(cfg.scan_hi_deg), delta_max_rad)
        self._lo2 = max(math.radians(cfg.climb_scan_lo_deg), self._lo)
        self.begin(0.0, None, 0.0, 0.5 * (self._lo + self._hi), None)

    def begin(self, t: float, own: Optional[OwnState], yaw0: float, delta0: float,
              p_stop_ned: Optional[Vec3]) -> None:
        self._t = t
        self._yaw0 = yaw0
        self._delta = delta0
        self._dir = 1                       # ve hi (nhin xuong) truoc
        self._ys = 0.0                      # quang duong quet yaw
        self._z0 = None if own is None else float(own.pos_ned[2])
        self._p_stop = p_stop_ned

    def step(self, t: float, own: OwnState, phase: int) -> SearchOutput:
        c = self.cfg
        dt = min(max(t - self._t, 0.0), _DT_MAX_S)
        self._t = t
        # --- khop: tich phan co phan xa o bien (lien tuc khi doi dai quet) ---
        lo = self._lo2 if phase >= 2 else self._lo
        hi = self._hi
        d = self._delta
        if d < lo:
            self._dir = 1
        elif d > hi:
            self._dir = -1
        d += self._dir * math.radians(c.scan_rate_dps) * dt
        if d >= hi:
            d, self._dir = 2.0 * hi - d, -1
        elif d <= lo and self._dir < 0:
            d, self._dir = 2.0 * lo - d, 1
        self._delta = d = max(lo, min(hi, d))
        # --- yaw ---
        amp = math.radians(c.yaw_amp_deg)
        if amp > 0.0:
            self._ys += math.radians(c.yaw_rate_dps) * dt
            yaw = (self._yaw0 + tri_sweep(self._ys, 0.0, -amp, amp, 1) + math.pi) % (2.0 * math.pi) - math.pi
        else:
            yaw = self._yaw0
        # --- leo thang dung (pha 2) ---
        gained = 0.0 if self._z0 is None else max(0.0, self._z0 - float(own.pos_ned[2]))
        vz = 0.0
        if (phase >= 2 and c.climb_m > 0.0 and self._p_stop is not None
                and math.hypot(own.pos_ned[0] - self._p_stop[0], own.pos_ned[1] - self._p_stop[1])
                >= _CLIMB_MIN_HORIZ_M):
            rem = c.climb_m - gained
            if rem > _CLIMB_DONE_M:
                vz = -min(c.climb_rate_mps, 0.5 * rem)
        return SearchOutput((0.0, 0.0, vz), yaw, d, gained, "search:p%d" % (2 if phase >= 2 else 1))
