"""Uoc luong khoang cach tu kich thuoc bbox + loc Kalman 1 chieu.

Do: r_m = f * S / s  (f: tieu cu px, S: kich thuoc that m, s: kich thuoc bbox px).
Chon s: bbox cua drone nhin tu nhieu goc; canh LON la nhip canh (khoang cach
giua hai canh quat) it doi theo goc nhin hon canh nho (nhin ngang thi chieu cao
rat mong). Nhung max(w,h) lech len khi nhieu do (E[max] cua hai bien ngau
nhien ~ +0.56 sigma, ~4% o 50 m). Nen: neu |w-h| nho hon nhieu thi coi bbox la
vuong va lay TRUNG BINH hai canh (khong lech, nhieu giam sqrt(2) lan); nguoc
lai (bbox ro ret dai) lay canh lon.

bbox cham mep anh (T9c): canh bi cat chi la can duoi cua kich thuoc that nen dung no se
bao XA hon thuc te. Neu biet kich thuoc khung: canh nao cham mep thi bi loai; con mot canh
khong bi cat thi chi dung canh do (neu canh bi cat con DAI hon han canh kia thi canh kia la
canh ngan, khong do duoc -> bo); ca hai bi cat -> khong cap nhat (chi du doan).

Nhieu do tang theo khoang cach: sigma_r = r^2 * sigma_s / (f * S).
Trang thai loc: [r, dr/dt], mo hinh van toc hang + nhieu gia toc trang. Muc tieu co the
dong/mo xa toi +-100 m/s nen toc do ban dau va nhieu gia toc duoc chon cho dai do.

`RangeEstimate.valid` chi True khi loc da hoi tu (du so lan cap nhat, sigma/r nho), mau do
cuoi du moi, va trang thai huu han.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class RangeConfig:
    target_size_m: float = 0.30        # m, kich thuoc that cua muc tieu (nhip canh)
    size_sigma_px: float = 1.0         # px, nhieu do moi canh bbox (1 sigma)
    square_tol_sigma: float = 2.0      # |w-h| < tol*sqrt(2)*sigma -> coi bbox vuong
    min_size_px: float = 2.0           # px, bbox nho hon bi bo
    accel_psd: float = 4.0             # (m/s^2)^2 * s, cuong do nhieu gia toc cua khoang cach
    init_rate_sigma_mps: float = 50.0  # m/s, bat dinh ban dau cua toc do doi khoang cach (dai +-100 m/s)
    innov_gate_sigma: float = 5.0      # sigma, vuot thi bo mau do (outlier)
    max_rejects: int = 15              # so mau bi bo lien tiep thi khoi tao lai loc
    size_rel_sigma: float = 0.25       # ty le, bat dinh kich thuoc that (cong vao sigma bao cao)
    edge_margin_px: float = 2.0        # px, canh bbox cach mep anh <= gia tri nay thi coi la bi cat
    min_updates_valid: int = 8         # so lan cap nhat toi thieu sau khi khoi tao de range_valid
    max_rel_sigma_valid: float = 0.2   # sigma_loc / r toi da de range_valid (khong tinh size_rel_sigma)
    max_update_age_s: float = 0.5      # s, mau do cuoi cu hon nguong nay -> range_valid = False
    max_abs_px: float = 1e6            # px, gia tri bbox ngoai (-max, max) bi coi la hong


@dataclass(frozen=True)
class RangeEstimate:
    range_m: float
    range_sigma_m: float
    range_rate_mps: float
    valid: bool = False


def _all_finite(*vals) -> bool:
    return all(v is not None and math.isfinite(v) for v in vals)


class RangeEstimator:
    def __init__(self, focal_px: float, config: Optional[RangeConfig] = None,
                 frame_size: Optional[Tuple[float, float]] = None):
        """frame_size = (rong, cao) px cua khung day du; None = khong kiem bbox cham mep."""
        self.cfg = config or RangeConfig()
        self.f = float(focal_px)
        self.frame_size = frame_size
        self.rejected_nonfinite = 0
        self.skipped_clipped = 0
        self.filter_resets = 0
        self.reset()

    def reset(self) -> None:
        self._x: Optional[np.ndarray] = None   # [r, rdot]
        self._P: Optional[np.ndarray] = None
        self._t = 0.0
        self._rejects = 0
        self._n_upd = 0

    def _state_ok(self) -> bool:
        """Trang thai loc huu han va hiep phuong sai hop le; neu khong thi khoi tao lai."""
        if self._x is None:
            return True
        ok = (bool(np.all(np.isfinite(self._x))) and bool(np.all(np.isfinite(self._P)))
              and self._P[0, 0] >= 0.0 and self._P[1, 1] >= 0.0 and self._x[0] > 0.0
              and math.isfinite(self._t))
        if not ok:
            self.filter_resets += 1
            self.reset()
        return ok

    # ---- do ----
    def measure_size_px(self, w: float, h: float) -> tuple[float, float]:
        """(kich thuoc dung de do, sigma cua no) theo logic trung binh/canh lon."""
        c = self.cfg
        s = c.size_sigma_px
        if abs(w - h) < c.square_tol_sigma * math.sqrt(2.0) * s:
            return 0.5 * (w + h), s / math.sqrt(2.0)
        return max(w, h), s

    def _measure_bbox(self, w: float, h: float, cx: Optional[float],
                      cy: Optional[float]) -> Optional[tuple[float, float]]:
        """Nhu measure_size_px nhung xet bbox bi cat o mep. None = khong do duoc."""
        if self.frame_size is None or cx is None or cy is None:
            return self.measure_size_px(w, h)
        W, H = self.frame_size
        m = self.cfg.edge_margin_px
        clip_w = (cx - 0.5 * w <= m) or (cx + 0.5 * w >= W - m)
        clip_h = (cy - 0.5 * h <= m) or (cy + 0.5 * h >= H - m)
        if not clip_w and not clip_h:
            return self.measure_size_px(w, h)
        if clip_w and clip_h:
            return None
        s = self.cfg.size_sigma_px
        free, cut = (h, w) if clip_w else (w, h)
        if cut > free + self.cfg.square_tol_sigma * math.sqrt(2.0) * s:
            return None   # canh bi cat da dai hon canh con lai: canh con lai la canh ngan
        return free, s

    def _sigma_r(self, r: float, size_sigma_px: float) -> float:
        return r * r * size_sigma_px / (self.f * self.cfg.target_size_m)

    # ---- loc ----
    def _predict(self, x: np.ndarray, P: np.ndarray, dt: float):
        dt = max(dt, 0.0)
        F = np.array([[1.0, dt], [0.0, 1.0]])
        q = self.cfg.accel_psd
        Q = q * np.array([[dt ** 3 / 3.0, dt ** 2 / 2.0], [dt ** 2 / 2.0, dt]])
        return F @ x, F @ P @ F.T + Q

    def update(self, t: float, w: float, h: float,
               cx: Optional[float] = None, cy: Optional[float] = None) -> bool:
        """Them mot do bbox (w,h px; tam cx,cy px de kiem tra cham mep) chup luc t.
        Tra True neu duoc dung. Mau khong huu han / bi cat o mep thi bi bo."""
        c = self.cfg
        if not _all_finite(t, w, h) or (cx is not None and not _all_finite(cx)) \
                or (cy is not None and not _all_finite(cy)) \
                or max(abs(w), abs(h), abs(cx or 0.0), abs(cy or 0.0)) > c.max_abs_px:
            self.rejected_nonfinite += 1
            return False
        self._state_ok()
        m = self._measure_bbox(w, h, cx, cy)
        if m is None:
            self.skipped_clipped += 1
            return False
        s, s_sig = m
        if s < c.min_size_px:
            return False
        r_m = self.f * c.target_size_m / s
        if self._x is None:
            sr = self._sigma_r(r_m, s_sig)
            self._x = np.array([r_m, 0.0])
            self._P = np.diag([sr * sr, c.init_rate_sigma_mps ** 2])
            self._t = t
            self._n_upd = 1
            return True
        x, P = self._predict(self._x, self._P, t - self._t)
        # sigma do tinh theo khoang cach DU DOAN (khong theo r_m nhieu) de tranh lech.
        sr = self._sigma_r(max(x[0], c.target_size_m), s_sig)
        S = P[0, 0] + sr * sr
        nu = r_m - x[0]
        if abs(nu) > c.innov_gate_sigma * math.sqrt(S):
            self._rejects += 1
            if self._rejects >= c.max_rejects:
                self.reset()
                self.update(t, w, h, cx, cy)
            return False
        self._rejects = 0
        K = P[:, 0] / S
        x = x + K * nu
        I_KH = np.eye(2) - np.outer(K, [1.0, 0.0])
        P = I_KH @ P @ I_KH.T + np.outer(K, K) * sr * sr
        self._x, self._P, self._t = x, P, t
        self._n_upd += 1
        self._state_ok()
        return True

    def estimate(self, t: float) -> Optional[RangeEstimate]:
        """Uoc luong du doan toi thoi diem t (khong doi trang thai)."""
        if self._x is None or not _all_finite(t) or not self._state_ok():
            return None
        c = self.cfg
        x, P = self._predict(self._x, self._P, t - self._t)
        # Sai so he thong cua kich thuoc that la thanh phan ty le voi r, cong TUYEN TINH
        # (cong thang, thu bao thu) vao sigma cua loc; khong dua vao P nen khong lam loc tu tin hon.
        s_filter = math.sqrt(max(P[0, 0], 0.0))
        sigma = s_filter + c.size_rel_sigma * abs(float(x[0]))
        # hoi tu: tinh tren hiep phuong sai cua loc DA cap nhat toi mau cuoi (khong tinh doan dai)
        s_upd = math.sqrt(max(self._P[0, 0], 0.0))
        valid = (x[0] > 0.0 and self._n_upd >= c.min_updates_valid
                 and s_upd <= c.max_rel_sigma_valid * float(self._x[0])
                 and (t - self._t) <= c.max_update_age_s)
        return RangeEstimate(float(x[0]), sigma, float(x[1]), valid)
