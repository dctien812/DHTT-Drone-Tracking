"""Doc chuyen tiep goc nang tham chieu: tu goc LOS luc khoa toi `final_deg` voi toc do <= rate_dps (khong I/O).

Khoi dong o lan co so do elev_los hop le dau tien sau reset(); sau do KHONG khoi dong lai (ke ca khi mat muc tieu).
"""
from __future__ import annotations

import math
from typing import Optional


class ElevRefRamp:
    def __init__(self, final_deg: float, rate_dps: float, dt_max_s: float):
        self.final_deg = float(final_deg)
        self.rate_dps = float(rate_dps)
        self.dt_max_s = float(dt_max_s)
        self.reset()

    def reset(self) -> None:
        self.value: Optional[float] = None
        self._t_prev: Optional[float] = None

    def update(self, t: float, elev_los_rad: Optional[float]) -> Optional[float]:
        """elev_los_rad (rad, None/NaN/inf = khong co so do) -> goc nang tham chieu (do) hoac None neu chua khoi dong."""
        if self.value is None:
            if elev_los_rad is None or not math.isfinite(elev_los_rad) or not math.isfinite(t):
                return None
            self.value = math.degrees(elev_los_rad)
            self._t_prev = t
            return self.value
        if not math.isfinite(t):      # t NaN/inf: bo qua, giu nguyen value va moc thoi gian
            return self.value
        dt = max(0.0, min(t - self._t_prev, self.dt_max_s))
        step = self.rate_dps * dt
        self.value += max(-step, min(step, self.final_deg - self.value))
        self._t_prev = max(t, self._t_prev)
        return self.value
