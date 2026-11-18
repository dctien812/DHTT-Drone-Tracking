"""Buoc 3 thiet ke khop gat: ServoModel (tre bac nhat + gioi han toc do + thoi gian chet + luong tu) va SimGimbalPort."""
import math


class ServoModel:
    MAX_SUBSTEP_S = 0.005

    def __init__(self, delta_init_rad, delta_min_rad, delta_max_rad, rate_rad_s, lag_s, dead_time_s, quant_rad,
                 slow_factor=1.0):
        self.delta_min = float(delta_min_rad)
        self.delta_max = float(delta_max_rad)
        self.quant = float(quant_rad)
        self.slow_factor = float(slow_factor)
        self.rate_eff = float(rate_rad_s) / self.slow_factor
        self.lag_eff = float(lag_s) * self.slow_factor
        self.dead_eff = float(dead_time_s) * self.slow_factor
        self.reset(delta_init_rad)

    @classmethod
    def from_config(cls, g):
        r = math.radians
        return cls(r(g.delta_init_deg), r(g.delta_min_deg), r(g.delta_max_deg), r(g.rate_dps), g.lag_s,
                   g.dead_time_s, r(g.quant_deg), g.slow_factor)

    def reset(self, delta_init_rad=None):
        if delta_init_rad is not None:
            self.delta_init = float(delta_init_rad)
        self.delta = self.delta_init
        self._t = None
        self._queue = []          # [(t_cmd, delta_cmd)], t_cmd khong giam
        self.last_rate_rad_s = 0.0

    def command(self, t, delta_rad):
        x = min(max(float(delta_rad), self.delta_min), self.delta_max)
        if self.quant > 0.0:
            x = round(x / self.quant) * self.quant
        t_cmd = max(float(t), self._queue[-1][0]) if self._queue else float(t)
        self._queue.append((t_cmd, x))
        return x

    def _effective(self, s):
        """Lenh moi nhat co t_cmd + dead <= s; chua co thi delta_init."""
        eff = self.delta_init
        for t_cmd, x in self._queue:
            if t_cmd + self.dead_eff <= s:
                eff = x
            else:
                break
        return eff

    def advance(self, t):
        t = float(t)
        if self._t is None:
            self._t = t
            return self.delta
        if t <= self._t:
            return self.delta
        t0, old = self._t, self.delta
        # moc cat: luc moi lenh bat dau co hieu luc nam trong (t0, t)
        edges = sorted({t_cmd + self.dead_eff for t_cmd, _ in self._queue if t0 < t_cmd + self.dead_eff < t})
        edges = [t0] + edges + [t]
        d = old
        for a, b in zip(edges[:-1], edges[1:]):
            n = max(1, int(math.ceil((b - a) / self.MAX_SUBSTEP_S - 1e-9)))
            h = (b - a) / n
            eff = self._effective(a + 0.5 * (b - a))
            for _ in range(n):
                if self.lag_eff > 0.0:
                    step = (eff - d) * (1.0 - math.exp(-h / self.lag_eff))
                else:
                    step = eff - d
                lim = self.rate_eff * h
                d += min(max(step, -lim), lim)
        self.delta = min(max(d, self.delta_min), self.delta_max)
        self._t = t
        self.last_rate_rad_s = (self.delta - old) / (t - t0)
        # bo lenh da bi thay the vinh vien (giu lenh co hieu luc moi nhat tai t va cac lenh sau do)
        k = 0
        for i, (t_cmd, _) in enumerate(self._queue):
            if t_cmd + self.dead_eff <= t:
                k = i
        self._queue = self._queue[k:]
        return self.delta


class SimGimbalPort:
    def __init__(self, servo):
        self.servo = servo
        self.last_cmd = servo.delta_init

    def command(self, t, delta_rad):
        self.last_cmd = self.servo.command(t, delta_rad)

    def angle(self, t):
        return self.servo.advance(t)

    def rate(self):
        return self.servo.last_rate_rad_s

    def reset(self):
        self.servo.reset()
        self.last_cmd = self.servo.delta_init
