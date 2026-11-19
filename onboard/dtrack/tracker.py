"""Tracker mot muc tieu loc theo HUONG NHIN trong he NED.

Trang thai Kalman: x = [u(3), du/dt(3)], u la vector don vi tu drone bam toi
muc tieu trong NED. Dung vector don vi (khong phai phuong vi/goc ngang) de khong
co ky di o thien dinh, va vi huong trong NED khong doi khi drone bam quay, nen
chuyen dong quay cua chinh no khong lam hong du doan. Moi phat hien duoc doi
sang NED bang tu the tai t_capture (noi suy tu bo dem OwnState).

Bo loc luon duoc giu o thoi diem do cuoi; dau ra duoc du doan toi t_now tu do
(bu tre) bang phep quay deu tren mat cau (toc do goc hang), con hiep phuong
sai truyen theo mo hinh tuyen tinh.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .geometry import (angle_between, pixel_to_los_ned, project_los_ned,
                       quat_slerp)
from .range_estimator import RangeConfig, RangeEstimator
from .types import CameraModel, Detection, OwnState, TrackState, TrackStatus


@dataclass
class TrackerConfig:
    min_conf: float = 0.25             # bo phat hien co conf thap hon
    # So lan khop de SEARCH -> TRACK. "Lien tiep" theo nghia ung vien: hai lan khop cach nhau
    # toi da coast_after_s (khung bi sot khong co phat hien nao thi khong tinh), va mot khung co
    # phat hien nhung KHONG khop ung vien thi bo ung vien va bat dau lai (khong phai 3 khung lien tiep).
    confirm_hits: int = 3
    coast_after_s: float = 0.25        # s, tuoi do cuoi > nguong -> COAST (phai > tre + vai khung)
    coast_timeout_s: float = 3.0       # s, tuoi do cuoi > nguong -> LOST
    lost_hold_s: float = 1.0           # s, giu bao LOST truoc khi ve SEARCH
    meas_sigma_px: float = 2.0         # px, nhieu tam bbox gia dinh (hoi cao hon nhieu that)
    accel_psd: float = 0.05            # (rad/s^2)^2 * s, nhieu gia toc cua huong nhin
    init_rate_sigma_rad_s: float = 0.3  # rad/s, bat dinh toc do goc ban dau
    gate_chi2: float = 16.0            # nguong Mahalanobis^2 (3 bac) de nhan phat hien
    reacquire_hits: int = 2            # khop lien tiep can co khi dang COAST de bat lai
    max_los_rate_rad_s: float = 1.5    # rad/s, toc do goc toi da hop ly (kiem tra xac nhan)
    # Khi COAST: co bbox phai trong [1/k, k] lan f*S/r_nho. k=2: khoang cach nho troi ~ +-30% sau
    # vai giay + bbox doi ti le do doi huong nhin; G2 (x0.6, x1.6) van qua; bbox gia 21 px vs ~195 px bi chan.
    size_ratio_max: float = 2.0
    # sigma them theo truc pixel bi cat khi bbox cham mep: tam do lech toi ~ nua phan bi cat (<= nua bbox).
    # UOC LUONG, chua kiem bang du lieu that (30 px khong du cho ca C; 100 va 300 deu xanh)
    edge_clip_sigma_px: float = 100.0
    # Sai so tuong doi cua co bbox nho khi dung lai tam that cua bbox bi cat (UOC LUONG, chua kiem du lieu that)
    edge_rebuild_rel_sigma: float = 0.3
    attitude_sigma_rad: float = 0.4 * math.pi / 180.0  # rad, nhieu tu the FC (moi truc), cong vao nhieu do goc
    own_buffer_s: float = 1.5          # s, do dai bo dem OwnState
    own_back_jump_s: float = 1.0       # s, OwnState lui hon nguong so voi mau cuoi -> xoa bo dem + khoi tao lai
    own_future_s: float = 1.0          # s, OwnState.t > t_now + nguong -> bo mau
    max_abs_px: float = 1e6            # px, |cx|,|cy|,|w|,|h| vuot nguong coi la hong
    next_frame_dt_s: float = 1.0 / 30  # s, tu t_now toi khung ke (cho predicted_px)
    range: RangeConfig = field(default_factory=RangeConfig)


@dataclass
class TrackerStats:
    """Bo dem loi dau vao / tu phuc hoi, doc duoc tu ngoai (tracker.stats)."""
    bad_detections: int = 0        # Detection co truong khong huu han / qua lon bi bo
    own_bad: int = 0               # OwnState co t hoac quaternion khong hop le bi bo
    own_future_dropped: int = 0    # OwnState co t > t_now + own_future_s bi bo
    own_clock_resets: int = 0      # so lan dong ho lui > own_back_jump_s (xoa bo dem, reset track)
    bad_t_now: int = 0             # t_now khong huu han
    filter_resets: int = 0         # trang thai loc huong thanh NaN/inf va bi khoi tao lai
    no_attitude: int = 0           # phat hien bi bo vi chua co tu the hop le nao


class SingleTargetTracker:
    def __init__(self, camera: Optional[CameraModel] = None,
                 config: Optional[TrackerConfig] = None):
        self.cam = camera or CameraModel()
        self.cfg = config or TrackerConfig()
        self.range = RangeEstimator(0.5 * (self.cam.fx + self.cam.fy), self.cfg.range,
                                    (self.cam.width, self.cam.height))
        self.stats = TrackerStats()
        self._own: List[OwnState] = []
        self._own_t: List[float] = []
        self._lost_t: Optional[float] = None
        self._reset_track()

    # ------------------------------------------------------------------
    def _reset_track(self) -> None:
        self._x: Optional[np.ndarray] = None
        self._P: Optional[np.ndarray] = None
        self._t_f = 0.0                 # thoi diem cua trang thai loc
        self._t_hit = 0.0               # t_capture cua do cuoi duoc dung
        self._hits = 0
        self._confirmed = False
        self._pending: Optional[Tuple[float, np.ndarray]] = None
        self._size_wh: Optional[Tuple[float, float]] = None   # (w, h) cua lan khop khong bi cat gan nhat
        self.range.reset()

    @property
    def _sigma_rad(self) -> float:
        px_rad = self.cfg.meas_sigma_px / (0.5 * (self.cam.fx + self.cam.fy))
        return math.hypot(px_rad, self.cfg.attitude_sigma_rad)

    # ---- bo dem tu the ----
    @staticmethod
    def _own_ok(own: OwnState) -> bool:
        if not math.isfinite(own.t):
            return False
        n2 = 0.0
        for c in own.q_world_body:
            if not math.isfinite(c):
                return False
            n2 += c * c
        n = math.sqrt(n2)
        return math.isfinite(n) and 1e-6 <= n <= 1e6

    def _push_own(self, own: OwnState, t_now: float) -> bool:
        """Nhan OwnState vao bo dem. Tra True neu mau duoc nhan (hoac thay mau cung t)."""
        if not self._own_ok(own):
            self.stats.own_bad += 1
            return False
        if own.t > t_now + self.cfg.own_future_s:
            self.stats.own_future_dropped += 1
            return False
        if self._own_t and own.t < self._own_t[-1] - self.cfg.own_back_jump_s:
            # dong ho lui (FC khoi dong lai / dong bo lai): bo dem cu vo nghia, track cu cung vay
            self._own.clear()
            self._own_t.clear()
            self._reset_track()
            self._lost_t = None
            self.stats.own_clock_resets += 1
        if self._own_t and own.t <= self._own_t[-1]:
            if own.t == self._own_t[-1]:
                self._own[-1] = own
                return True
            return False  # mau cu hon bi bo
        self._own.append(own)
        self._own_t.append(own.t)
        cut = bisect.bisect_left(self._own_t, own.t - self.cfg.own_buffer_s)
        cut = min(cut, len(self._own) - 2) if len(self._own) > 1 else 0
        if cut > 0:
            del self._own[:cut]
            del self._own_t[:cut]
        return True

    def _attitude_at(self, t: float) -> Sequence[float]:
        ts = self._own_t
        i = bisect.bisect_left(ts, t)
        if i <= 0:
            return self._own[0].q_world_body
        if i >= len(ts):
            return self._own[-1].q_world_body
        a, b = self._own[i - 1], self._own[i]
        s = (t - a.t) / (b.t - a.t)
        return quat_slerp(a.q_world_body, b.q_world_body, s)

    # ---- loc ----
    def _propagate(self, x: np.ndarray, P: np.ndarray, dt: float):
        dt = max(dt, 0.0)
        u, v = x[:3], x[3:]
        w = np.cross(u, v)
        wn = float(np.linalg.norm(w))
        if wn * dt < 1e-12:
            u2 = u + v * dt
        else:
            k = w / wn
            th = wn * dt
            u2 = u * math.cos(th) + np.cross(k, u) * math.sin(th)
        u2 = u2 / np.linalg.norm(u2)
        v2 = np.cross(w, u2)
        F = np.eye(6)
        F[:3, 3:] = np.eye(3) * dt
        q = self.cfg.accel_psd
        Q = np.zeros((6, 6))
        Q[:3, :3] = np.eye(3) * q * dt ** 3 / 3.0
        Q[:3, 3:] = Q[3:, :3] = np.eye(3) * q * dt ** 2 / 2.0
        Q[3:, 3:] = np.eye(3) * q * dt
        return np.concatenate([u2, v2]), F @ P @ F.T + Q

    def _innovation(self, z: np.ndarray, t: float):
        x, P = self._propagate(self._x, self._P, t - self._t_f)
        S = P[:3, :3] + np.eye(3) * self._sigma_rad ** 2
        nu = z - x[:3]
        d2 = float(nu @ np.linalg.solve(S, nu))
        return x, P, S, nu, d2

    def _init_filter(self, z: np.ndarray, t: float) -> None:
        s = self._sigma_rad
        self._x = np.concatenate([z, np.zeros(3)])
        self._P = np.diag([s * s] * 3 + [self.cfg.init_rate_sigma_rad_s ** 2] * 3)
        self._t_f = self._t_hit = t
        self._hits = 1
        self._confirmed = False
        self._pending = None

    def _apply(self, z: np.ndarray, t: float, d: Detection) -> None:
        R = np.eye(3) * self._sigma_rad ** 2
        mw, mh = self._size_wh if self._size_wh else (None, None)
        sx = self._rebuild_axis(d.cx, d.w, self.cam.width, mw)
        sy = self._rebuild_axis(d.cy, d.h, self.cam.height, mh)
        if sx[1] is not None or sy[1] is not None:
            # bbox bi cat: tam do khong phai tam that. Dung lai tam theo truc bi cat (canh con thay +
            # co nho), tang nhieu do theo huong truc pixel do tuy phan bi cat.
            q = self._attitude_at(d.t_capture)
            f = 0.5 * (self.cam.fx + self.cam.fy)
            z0 = pixel_to_los_ned(self.cam, q, d.cx, d.cy)
            z = pixel_to_los_ned(self.cam, q, sx[0], sy[0])
            for (c, sig), (dx, dy) in ((sx, (1.0, 0.0)), (sy, (0.0, 1.0))):
                if sig is not None:
                    e = pixel_to_los_ned(self.cam, q, d.cx + dx, d.cy + dy) - z0
                    e = e / np.linalg.norm(e)
                    R = R + (sig / f) ** 2 * np.outer(e, e)
        x, P, S, nu, _ = self._innovation(z, t)
        if sx[1] is not None or sy[1] is not None:
            S = P[:3, :3] + R
        K = P[:, :3] @ np.linalg.inv(S)
        x = x + K @ nu
        H = np.hstack([np.eye(3), np.zeros((3, 3))])
        I_KH = np.eye(6) - K @ H
        P = I_KH @ P @ I_KH.T + K @ R @ K.T
        u = x[:3] / np.linalg.norm(x[:3])
        v = x[3:] - np.dot(x[3:], u) * u
        self._x, self._P = np.concatenate([u, v]), P
        self._t_f = self._t_hit = t
        self._hits += 1
        self._note_size(d)
        self.range.update(t, d.w, d.h, d.cx, d.cy)

    # ---- API ----
    def update(self, detections: List[Detection], own: OwnState, t_now: float) -> TrackState:
        cfg = self.cfg
        if not math.isfinite(t_now):
            self.stats.bad_t_now += 1
            return TrackState(t=t_now, status=TrackStatus.SEARCH)
        own_ok = self._push_own(own, t_now)
        if self._x is not None and t_now < self._t_hit - cfg.own_back_jump_s:
            self._reset_track()                  # t_now lui xa: track cu khong con y nghia
            self.stats.own_clock_resets += 1
        if self._x is not None and not self._state_finite():
            self._reset_track()
            self.stats.filter_resets += 1

        # 1) Qua han khong do -> LOST
        if self._x is not None and self._confirmed and t_now - self._t_hit > cfg.coast_timeout_s:
            self._reset_track()
            self._lost_t = t_now
        elif self._x is not None and not self._confirmed and t_now - self._t_hit > cfg.coast_after_s:
            self._reset_track()  # ung vien chua xac nhan bi mat do: bo

        # 2) Doi phat hien sang NED
        cands = []
        for d in detections:
            if not self._det_ok(d, t_now):
                self.stats.bad_detections += 1
                continue
            if d.conf < cfg.min_conf:
                continue
            if not self._own:                       # chua co tu the hop le nao
                self.stats.no_attitude += 1
                continue
            q = self._attitude_at(d.t_capture)
            z = pixel_to_los_ned(self.cam, q, d.cx, d.cy)
            if not (np.all(np.isfinite(z)) and abs(float(np.linalg.norm(z)) - 1.0) < 1e-6):
                self.stats.bad_detections += 1
                continue
            cands.append((d, z))

        # 3) Lien ket
        if self._x is None:
            if cands:
                d, z = max(cands, key=lambda c: c[0].conf)
                self._init_filter(z, d.t_capture)
                self._note_size(d)
                self.range.update(d.t_capture, d.w, d.h, d.cx, d.cy)
        elif cands:
            best = None
            for d, z in cands:
                if d.t_capture <= self._t_f:
                    continue
                d2 = self._innovation(z, d.t_capture)[4]
                if d2 <= cfg.gate_chi2 and (best is None or d2 < best[2]):
                    best = (d, z, d2)
            coasting = self._confirmed and (t_now - self._t_hit > cfg.coast_after_s)
            if best is None:
                self._pending = None
                if not self._confirmed:           # ung vien hut khung: bat dau lai
                    d, z = max(cands, key=lambda c: c[0].conf)
                    self._reset_track()
                    self._init_filter(z, d.t_capture)
                    self._note_size(d)
                    self.range.update(d.t_capture, d.w, d.h, d.cx, d.cy)
            else:
                d, z, _ = best
                accept = True
                if coasting and not self._size_ok(d):
                    self._pending = None
                    accept = False
                elif coasting and cfg.reacquire_hits > 1:
                    p = self._pending
                    accept = (p is not None and d.t_capture > p[0] and
                              angle_between(p[1], z) <= cfg.max_los_rate_rad_s * (d.t_capture - p[0])
                              + 4.0 * self._sigma_rad)
                    self._pending = None if accept else (d.t_capture, z)
                if accept:
                    self._apply(z, d.t_capture, d)
                    if not self._confirmed and self._hits >= cfg.confirm_hits:
                        self._confirmed = True
        # update goi nhanh hon detector: goi khong co phat hien khong duoc xoa ung vien tai bat;
        # chi het han khi qua coast_after_s (cung nghia "lien tiep" cua confirm_hits).
        if not cands and self._pending is not None and t_now - self._pending[0] > cfg.coast_after_s:
            self._pending = None

        if self._x is not None and not self._state_finite():
            self._reset_track()                     # tu bao ve: trang thai loc hong -> khoi tao lai
            self.stats.filter_resets += 1
        return self._output(t_now, own if own_ok else (self._own[-1] if self._own else None))

    def _clipped_axes(self, d: Detection) -> Tuple[bool, bool]:
        """(cat theo x, cat theo y): bbox cham mep khung (cung nguong voi range estimator)."""
        W, H, m = self.cam.width, self.cam.height, self.range.cfg.edge_margin_px
        return (d.cx - d.w / 2 <= m or d.cx + d.w / 2 >= W - m,
                d.cy - d.h / 2 <= m or d.cy + d.h / 2 >= H - m)

    def _note_size(self, d: Detection) -> None:
        """Nho co bbox cua lan khop hop le gan nhat (bo qua bbox bi cat: co khong dang tin)."""
        if not any(self._clipped_axes(d)):
            self._size_wh = (d.w, d.h)

    def _rebuild_axis(self, c: float, dim: float, lim: float,
                      mem: Optional[float]) -> Tuple[float, Optional[float]]:
        """Mot truc pixel: (tam dung lai, sigma px them) hoac (c, None) neu khong bi cat.
        Chi mot mep bi cat va co co nho: tam that = canh con thay -/+ nua co nho (dung max(dim, mem));
        sigma = rel * phan bi cat / 2 (co nho co the cu). Khong co co nho hoac cat ca hai mep: sigma lon."""
        m = self.range.cfg.edge_margin_px
        lo, hi = c - dim / 2 <= m, c + dim / 2 >= lim - m
        if not (lo or hi):
            return c, None
        if mem is None or (lo and hi):
            return c, self.cfg.edge_clip_sigma_px
        use = max(dim, mem)
        c2 = c + dim / 2 - use / 2 if lo else c - dim / 2 + use / 2
        return c2, 0.5 * self.cfg.edge_rebuild_rel_sigma * (use - dim)

    def _size_ok(self, d: Detection) -> bool:
        """Dang COAST: co bbox phai trong [1/size_ratio_max, size_ratio_max] lan co bbox nho cuoi
        (bbox cham mep bi cat nen chi chan tren). Chua nho co nao -> khong chan."""
        if self._size_wh is None:
            return True
        ref = max(self._size_wh)
        s = max(d.w, d.h)
        if s > self.cfg.size_ratio_max * ref:
            return False
        return s >= ref / self.cfg.size_ratio_max or any(self._clipped_axes(d))

    def _state_finite(self) -> bool:
        return bool(np.all(np.isfinite(self._x)) and np.all(np.isfinite(self._P))
                    and math.isfinite(self._t_f) and math.isfinite(self._t_hit))

    def _det_ok(self, d: Detection, t_now: float) -> bool:
        """Moi truong cua Detection phai huu han va trong gioi han hop ly."""
        vals = (d.t_capture, d.cx, d.cy, d.w, d.h, d.conf)
        if not all(math.isfinite(v) for v in vals):
            return False
        if max(abs(d.cx), abs(d.cy), abs(d.w), abs(d.h)) > self.cfg.max_abs_px:
            return False
        return d.t_capture <= t_now + self.cfg.own_future_s

    def _output(self, t_now: float, own: Optional[OwnState]) -> TrackState:
        cfg = self.cfg
        if self._x is None or not self._confirmed:
            lost = self._lost_t is not None and t_now - self._lost_t <= cfg.lost_hold_s
            return TrackState(t=t_now, status=TrackStatus.LOST if lost else TrackStatus.SEARCH,
                              range_valid=False, age_s=(t_now - self._lost_t) if lost else 0.0)
        age = t_now - self._t_hit
        status = TrackStatus.COAST if age > cfg.coast_after_s else TrackStatus.TRACK
        x, _ = self._propagate(self._x, self._P, t_now - self._t_f)
        u, v = x[:3], x[3:]
        xn, _ = self._propagate(self._x, self._P, t_now + cfg.next_frame_dt_s - self._t_f)
        px = (project_los_ned(self.cam, own.q_world_body, xn[:3], require_in_frame=False)
              if own is not None else None)
        est = self.range.estimate(t_now)
        return TrackState(
            t=t_now, status=status,
            los_ned=tuple(float(c) for c in u),
            los_rate_ned=tuple(float(c) for c in np.cross(u, v)),
            range_m=est.range_m if est else None,
            range_sigma_m=est.range_sigma_m if est else None,
            range_rate_mps=est.range_rate_mps if est else None,
            range_valid=bool(est.valid) if est else False,
            predicted_px=px, age_s=age)
