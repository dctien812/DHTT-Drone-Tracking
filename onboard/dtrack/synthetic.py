"""Bo sinh phat hien tong hop, gia lap detector that de thu tracker.

Cach dung: moi buoc mo phong goi process(t, target_pos_ned, own) voi gia tri
THAT tai thoi diem t. Khi den han khung (frame_rate_hz) no chup khung do
(t_capture = t) va chi tra ra sau latency_s. Cac phat hien da du han tra ve o
lan goi hien tai.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .geometry import project_ned_point
from .types import CameraModel, Detection, OwnState


@dataclass
class SyntheticConfig:
    frame_rate_hz: float = 30.0       # Hz, tan so khung
    latency_s: float = 0.06           # s, tre tu luc chup toi luc tra ra
    center_sigma_px: float = 1.5      # px, nhieu Gauss len tam bbox (moi truc)
    size_sigma_px: float = 1.0        # px, nhieu Gauss len w va h (doc lap)
    target_size_m: float = 0.30       # m, kich thuoc that cua muc tieu
    p_miss: float = 0.20              # xac suat bo sot muc tieu moi khung
    p_false: float = 0.05             # xac suat co mot phat hien gia moi khung
    true_conf_mean: float = 0.8       # do tin cay phat hien that
    true_conf_sigma: float = 0.08
    false_conf_mean: float = 0.4      # phat hien gia thuong tin cay thap hon
    false_conf_sigma: float = 0.15
    false_size_range_px: Tuple[float, float] = (8.0, 40.0)  # px, kich thuoc bbox gia
    clip_to_frame: bool = True        # cat bbox theo khung anh (nhu detector that khi muc tieu cham mep)
    seed: int = 12345                 # seed co dinh de tai lap


class SyntheticDetector:
    def __init__(self, camera: Optional[CameraModel] = None,
                 config: Optional[SyntheticConfig] = None):
        self.cam = camera or CameraModel()
        self.cfg = config or SyntheticConfig()
        self.rng = np.random.default_rng(self.cfg.seed)
        self._next_frame_t: Optional[float] = None
        self._pending: List[Tuple[float, Detection]] = []  # (thoi diem tra, phat hien)

    def _clip01(self, v: float) -> float:
        return float(min(1.0, max(0.0, v)))

    def _clip_box(self, cx: float, cy: float, w: float, h: float) -> Optional[Tuple[float, float, float, float]]:
        """Cat bbox theo khung [0,W]x[0,H]; None neu khong con phan nao trong khung."""
        if not self.cfg.clip_to_frame:
            return cx, cy, w, h
        x0, x1 = max(0.0, cx - 0.5 * w), min(float(self.cam.width), cx + 0.5 * w)
        y0, y1 = max(0.0, cy - 0.5 * h), min(float(self.cam.height), cy + 0.5 * h)
        if x1 - x0 < 1.0 or y1 - y0 < 1.0:
            return None
        return 0.5 * (x0 + x1), 0.5 * (y0 + y1), x1 - x0, y1 - y0

    def _make_frame(self, t: float, target_pos_ned: Sequence[float], own: OwnState) -> List[Detection]:
        c, cam, rng = self.cfg, self.cam, self.rng
        out: List[Detection] = []
        # Luon rut cung so so ngau nhien moi khung de chuoi tai lap ben vung.
        r_miss = rng.random()
        noise = rng.normal(size=4)
        conf = rng.normal(c.true_conf_mean, c.true_conf_sigma)
        r_false = rng.random()
        fa = rng.random(4)
        fconf = rng.normal(c.false_conf_mean, c.false_conf_sigma)

        px = project_ned_point(cam, own.q_world_body, own.pos_ned, target_pos_ned)
        if px is not None and r_miss >= c.p_miss:
            rng_m = float(np.linalg.norm(np.asarray(target_pos_ned, float) - np.asarray(own.pos_ned, float)))
            size = 0.5 * (cam.fx + cam.fy) * c.target_size_m / max(rng_m, 1e-6)
            box = self._clip_box(px[0] + c.center_sigma_px * noise[0],
                                 px[1] + c.center_sigma_px * noise[1],
                                 max(1.0, size + c.size_sigma_px * noise[2]),
                                 max(1.0, size + c.size_sigma_px * noise[3]))
            if box is not None:
                out.append(Detection(t_capture=t, cx=box[0], cy=box[1], w=box[2], h=box[3],
                                     conf=self._clip01(conf)))
        if r_false < c.p_false:
            lo, hi = c.false_size_range_px
            box = self._clip_box(fa[0] * cam.width, fa[1] * cam.height,
                                 lo + fa[2] * (hi - lo), lo + fa[3] * (hi - lo))
            if box is not None:
                out.append(Detection(t_capture=t, cx=box[0], cy=box[1], w=box[2], h=box[3],
                                     conf=self._clip01(fconf)))
        return out

    def process(self, t: float, target_pos_ned: Sequence[float], own: OwnState) -> List[Detection]:
        """Xem docstring module. Tra danh sach Detection da du han tai thoi diem t."""
        period = 1.0 / self.cfg.frame_rate_hz
        if self._next_frame_t is None:
            self._next_frame_t = t
        if t >= self._next_frame_t - 1e-9:
            for d in self._make_frame(t, target_pos_ned, own):
                self._pending.append((t + self.cfg.latency_s, d))
            self._next_frame_t += period
            if self._next_frame_t < t:  # bo lo nhieu khung: khong don lai
                self._next_frame_t = t + period
        ready = [d for (tr, d) in self._pending if tr <= t + 1e-9]
        self._pending = [(tr, d) for (tr, d) in self._pending if tr > t + 1e-9]
        return ready
