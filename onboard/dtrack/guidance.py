"""Dan duong THUAN (khong I/O): (TrackState, OwnState, cau hinh, lenh truoc) -> GuidanceCommand.

Luat (he NED, u = vector don vi duong ngam tu drone bam toi muc tieu, r = khoang cach):
  van toc muc tieu uoc luong   v_t = v_own + r_dot*u + r*(los_rate x u)       (chi khi range_valid)
  lenh                          v   = v_t + clip(Kp*(r - r_dat)) * u + thanh phan dung giu muc tieu o giua anh
  yaw                           huong mui theo duong ngam (gioi han toc do doi yaw)

An toan (uu tien tu tren xuong):
  1. Dau vao khong huu han -> lenh phanh (van toc 0), reason "brake:nan_input".
  2. Khong co muc tieu (SEARCH/LOST) -> phanh (van toc 0, giu vi tri).
  3. r < range_back_m (co tre hysteresis) -> lui theo duong ngam voi back_speed so voi muc tieu.
  4. range_valid = False hoac COAST -> KHONG tien lai gan: thanh phan doc duong ngam cua lenh
     khong vuot thanh phan "khop" (chi khop van toc ban than + thanh phan ngang theo los_rate,
     giam dan thanh phan tien lai gan), co the lui; ket qua duoc cat tuc thi (khong qua bo gioi han gia toc).
  5. Gioi han toc do ngang / len / xuong, gia toc, jerk; do cao toi thieu.
"""
from __future__ import annotations

import dataclasses
import math
from typing import Optional, Tuple

import numpy as np

from .config import GuidanceConfig, make_camera
from .elev_ramp import ElevRefRamp
from .types import GuidanceCommand, OwnState, TrackState, TrackStatus, Vec3

ZERO: Vec3 = (0.0, 0.0, 0.0)
_EPS = 1e-9


def _finite_vec(v) -> bool:
    try:
        return all(math.isfinite(float(c)) for c in v)
    except (TypeError, ValueError):
        return False


def _brake(t: float, reason: str, yaw: Optional[float] = None) -> GuidanceCommand:
    # yaw: giu huong mui hien tai (neu khong, FC tu quay mui theo huong bay)
    return GuidanceCommand(t=t if math.isfinite(t) else 0.0, vel_ned=ZERO, yaw_rad=yaw,
                           valid=True, reason="brake:" + reason)


def yaw_from_quat(q) -> float:
    w, x, y, z = q
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _rot(q) -> np.ndarray:
    from .geometry import quat_to_matrix
    return quat_to_matrix(q)


def vertical_image_error_rad(u: np.ndarray, own: OwnState, tilt_up_deg: float) -> float:
    """Goc (rad) muc tieu lech khoi tam anh theo phuong dung; duong = muc tieu nam DUOI tam anh.

    Tinh trong khung da BU pitch/roll (chi giu yaw, nhu khi than may nam ngang): pitch tam thoi luc
    tang/giam toc khong bi doi thanh lenh do cao (truoc day gay lech do cao 9-10 m).
    """
    R_bc = np.asarray(make_camera(tilt_up_deg).R_body_cam, float)
    yaw = yaw_from_quat(own.q_world_body)
    c, s = math.cos(yaw), math.sin(yaw)
    R_level = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    ray = (R_level @ R_bc).T @ u
    return math.atan2(float(ray[1]), float(ray[2])) if ray[2] > _EPS else 0.0


def compute_guidance_ex(track: TrackState, own: OwnState, cfg: GuidanceConfig,
                        prev: Optional[GuidanceCommand] = None,
                        prev_accel: Optional[Vec3] = None,
                        v_t_hold: Optional[Vec3] = None,
                        info: Optional[dict] = None,
                        elev_ref_deg: Optional[float] = None,
                        target_seen: bool = False) -> Tuple[GuidanceCommand, Vec3]:
    """Nhu compute_guidance nhung tra them gia toc lenh (de gioi han jerk o chu ky ke).

    v_t_hold: van toc muc tieu NHO duoc (NED); khi COAST thi dung no thay cho uoc luong hien tai.
    info: neu la dict, duoc dien v_t / u / r khi TRACK hop le (de bo nho cua Guidance cap nhat)."""
    t = track.t
    if not (math.isfinite(t) and _finite_vec(own.vel_ned) and _finite_vec(own.pos_ned)
            and _finite_vec(own.q_world_body) and math.isfinite(own.t)):
        return _brake(t, "nan_input"), ZERO
    if track.status not in (TrackStatus.TRACK, TrackStatus.COAST) or track.los_ned is None:
        return _brake(t, "no_track:" + track.status.value), ZERO
    u = np.asarray(track.los_ned, float)
    if track.range_m is not None and not math.isfinite(track.range_m):
        return _brake(t, "nan_input"), ZERO
    if track.range_rate_mps is not None and not math.isfinite(track.range_rate_mps):
        return _brake(t, "nan_input"), ZERO
    nu = float(np.linalg.norm(u)) if _finite_vec(u) else float("nan")
    if not math.isfinite(nu) or nu < 0.5:
        return _brake(t, "nan_input"), ZERO
    u = u / nu
    omega = np.asarray(track.los_rate_ned if track.los_rate_ned is not None else ZERO, float)
    if not _finite_vec(omega):
        return _brake(t, "nan_input"), ZERO
    wn = float(np.linalg.norm(omega))
    if wn > cfg.los_rate_max_rad_s:
        omega = omega * (cfg.los_rate_max_rad_s / wn)

    v_own = np.asarray(own.vel_ned, float)
    speed_own = float(np.linalg.norm(v_own))
    r_set = max(cfg.range_set_m, cfg.range_tau_s * speed_own)
    r_known = track.range_m if (track.range_m is not None and math.isfinite(track.range_m)
                                and track.range_m > 0.0) else None
    valid = bool(track.range_valid) and r_known is not None
    coasting = track.status == TrackStatus.COAST
    no_view = coasting and not target_seen         # that su khong thay muc tieu (target_seen: TRACK bi step() doi sang duong nho)
    in_min_prev = prev is not None and prev.reason.startswith("min_range")

    # dt va diem xuat phat cua bo gioi han
    if prev is not None and prev.valid and _finite_vec(prev.vel_ned) and math.isfinite(prev.t):
        dt = min(max(t - prev.t, 1e-3), cfg.dt_max_s)
        v_prev = np.asarray(prev.vel_ned, float)
    else:
        dt = cfg.dt_default_s
        v_prev = v_own

    r_est = r_known if r_known is not None else r_set
    lateral = r_est * np.cross(omega, u)           # thanh phan ngang cua van toc muc tieu so voi minh
    rad_own = float(v_own @ u)
    reasons = []
    radial_cap: Optional[float] = None             # neu dat: thanh phan doc u cua lenh bi cat tuc thi toi gia tri nay
    min_range = False

    if valid:
        rdot = 0.0 if track.range_rate_mps is None or not math.isfinite(track.range_rate_mps) \
            else max(-cfg.range_rate_max_mps, min(cfg.range_rate_max_mps, track.range_rate_mps))
        v_t = v_own + rdot * u + lateral
        if coasting and v_t_hold is not None and _finite_vec(v_t_hold):
            v_t = np.asarray(v_t_hold, float)
        elif info is not None and not coasting:
            info.update(v_t=v_t.copy(), u=u.copy(), r=float(r_known))
        if no_view and v_t[2] < 0.0:               # khong thay muc tieu: khong leo theo van toc dung nho/ngoai suy (NED: am = len)
            v_t = v_t.copy()
            v_t[2] = 0.0
        e = r_known - r_set
        u_p = max(-cfg.open_speed_max_mps, min(cfg.close_speed_max_mps, cfg.kp_range * e))
        # toc do tien lai gan (so voi muc tieu) khong vuot toc do con phanh kip truoc range_min
        u_p = min(u_p, math.sqrt(2.0 * cfg.a_decel_mps2 * max(r_known - cfg.range_min_m, 0.0)))
        min_range = r_known < cfg.range_back_m or (in_min_prev and r_known < cfg.range_back_m + cfg.range_min_hyst_m)
        if min_range:
            u_back = u
            uh_n = math.hypot(float(u[0]), float(u[1]))
            if no_view:                            # lui chi tren mat ngang, do lon ~ thanh phan ngang cua LOS (0 khi thang dung)
                u_back = np.array([u[0], u[1], 0.0]) / max(uh_n, 1e-9) * min(1.0, uh_n / 0.2)
            v_des = v_t - cfg.back_speed_mps * u_back
            radial_cap = float(v_des @ u)
            reasons.append("min_range")
        elif coasting:
            u_p = min(u_p, 0.0)
            v_des = v_t + u_p * u
            radial_cap = float(v_t @ u)            # khong tien lai gan hon toc do khop
            reasons.append("coast")
        else:
            v_des = v_t + u_p * u
            reasons.append("track")
    else:
        # khong tin khoang cach: khop van toc ban than + thanh phan ngang, khong tien lai gan
        prev_rad = float(v_prev @ u) if prev is not None else rad_own
        if rad_own > 0.0:
            rad_cmd = min(rad_own, max(0.0, prev_rad - cfg.invalid_decel_mps2 * dt))
        else:
            rad_cmd = rad_own
        if r_known is not None:
            min_range = r_known < cfg.range_back_m or (in_min_prev and r_known < cfg.range_back_m + cfg.range_min_hyst_m)
            if min_range:
                rad_cmd = min(rad_cmd, -cfg.back_speed_mps)
                reasons.append("min_range")
            elif r_known < r_set:
                rad_cmd = min(rad_cmd, cfg.kp_range * (r_known - r_set))
        v_des = v_own - rad_own * u + lateral + rad_cmd * u
        radial_cap = float(v_des @ u)
        reasons.append("range_invalid")

    # giu muc tieu o giua anh theo phuong dung
    err = vertical_image_error_rad(u, own, cfg.cam_tilt_up_deg)
    # vi tri mong muon trong anh bu truoc mui chui/ngang len theo GIA TOC LENH truoc (khong theo tu the do,
    # nen pitch tam thoi khong bi doi thanh lech do cao): tang toc -> muc tieu mong muon thap hon (drone cao hon)
    a_al = 0.0
    sp_p = float(np.linalg.norm(v_prev[:2]))
    if sp_p > 1.0 and prev_accel is not None and _finite_vec(prev_accel):
        a_al = float(np.asarray(prev_accel, float)[:2] @ (v_prev[:2] / sp_p))
    e_ref = max(-cfg.elev_ref_max_deg, min(cfg.elev_ref_max_deg,
                                           cfg.target_elev_ref_deg - cfg.elev_accel_comp * math.degrees(math.atan2(a_al, 9.81))))
    if elev_ref_deg is not None:                   # doc chuyen tiep: dung thang, khong cat, khong bu gia toc
        e_ref = elev_ref_deg
    err = max(-0.5, min(0.5, err - math.radians(cfg.cam_tilt_up_deg - e_ref)))
    vc = max(-cfg.vert_center_max_mps, min(cfg.vert_center_max_mps, cfg.kp_vert_center * r_est * math.tan(err)))
    if no_view:                                    # LOS ngoai suy: khong chay vong giu giua anh theo phuong dung
        vc = 0.0
    w = np.array([0.0, 0.0, vc])
    v_des = v_des + (w - float(w @ u) * u)      # chi thanh phan vuong goc duong ngam: khong doi thanh phan tien/lui
    if no_view and v_des[2] < 0.0:                 # khong thay muc tieu: lenh mong muon khong di len (low_alt ben duoi van thang)
        v_des[2] = 0.0
    # do cao toi thieu (z NED am = len)
    alt = -own.pos_ned[2]
    if alt < cfg.min_alt_m:
        v_des[2] = min(v_des[2], -min(cfg.climb_max_mps, 1.0 + 0.5 * (cfg.min_alt_m - alt)))
        reasons.append("low_alt")
    elif alt < cfg.min_alt_m + 3.0:
        v_des[2] = min(v_des[2], 0.0)

    v_des = _limit_speed(v_des, cfg)

    # gioi han gia toc va jerk quanh v_prev (dang lui do duoi khoang cach toi thieu: gia toc lon hon)
    a_des = (v_des - v_prev) / dt
    a_h = float(np.linalg.norm(a_des[:2]))
    braking = float(np.dot((v_des - v_prev)[:2], v_prev[:2])) < 0.0
    jerk = cfg.jerk_back_mps3 if min_range else cfg.jerk_max_mps3     # lui khan: lenh duoc phep doi gia toc rat nhanh (FC tre ~1 s)
    a_lim = cfg.a_back_mps2 if min_range else (cfg.a_decel_mps2 if braking else cfg.a_max_mps2)
    # khong de gia toc lon hon muc con dung lai kip (jerk huu han): a <= sqrt(2*J*|dv|), tranh vot lo van toc dat
    dvh = float(np.linalg.norm((v_des - v_prev)[:2]))
    a_lim = min(a_lim, max(math.sqrt(2.0 * jerk * dvh), 0.05))
    sp_prev = float(np.linalg.norm(v_prev[:2]))
    if sp_prev > 1.0 and not min_range:
        # tach gia toc ngang: doc huong bay (gioi han a_max / a_decel) va vuong goc (re, gioi han a_lat)
        e = v_prev[:2] / sp_prev
        a_l = float(a_des[:2] @ e)
        a_t = a_des[:2] - a_l * e
        cap = max(math.sqrt(2.0 * jerk * dvh), 0.05)      # khong vot lo van toc dat
        a_l = max(-min(cfg.a_decel_mps2, cap), min(cfg.a_max_mps2, cap, a_l))
        nt = float(np.linalg.norm(a_t))
        if nt > min(cfg.a_lat_mps2, cap):
            a_t = a_t * (min(cfg.a_lat_mps2, cap) / nt)
        a_des[:2] = a_l * e + a_t
    elif a_h > a_lim:
        a_des[:2] *= a_lim / a_h
    a_des[2] = max(-cfg.a_max_z_mps2, min(cfg.a_max_z_mps2, a_des[2]))
    if prev_accel is not None and _finite_vec(prev_accel):
        da = a_des - np.asarray(prev_accel, float)
        dn = float(np.linalg.norm(da))
        lim = jerk * dt
        if dn > lim:
            a_des = np.asarray(prev_accel, float) + da * (lim / dn)
    v_cmd = v_prev + a_des * dt
    # cat tuc thi thanh phan tien lai gan trong che do an toan (khong cho bo gioi han gia toc giu lai)
    # che do khong-tien-lai-gan: khong lenh nhanh hon van toc hien tai doc duong ngam (giam toc thi theo gioi han gia toc)
    if radial_cap is not None:
        radial_cap = None if min_range else max(radial_cap, rad_own)
    for _ in range(3):
        if radial_cap is not None:
            excess = float(v_cmd @ u) - radial_cap
            if excess > 0.0:
                uh2c = float(u[0] * u[0] + u[1] * u[1])
                if no_view and uh2c > 1e-3:        # khong thay muc tieu: cat phan thua chi theo phuong ngang (khong sinh z len)
                    v_cmd = v_cmd.copy()
                    v_cmd[:2] -= excess * u[:2] / uh2c
                else:
                    v_cmd = v_cmd - excess * u
        v_cmd = _limit_speed(v_cmd, cfg)
    if radial_cap is not None:
        excess = float(v_cmd @ u) - radial_cap
        uh2 = float(u[0] * u[0] + u[1] * u[1])
        if excess > 1e-6 and uh2 > 1e-3:
            # gioi han dung (len/xuong) chan viec cat theo u: bu bang thanh phan ngang
            v_cmd = v_cmd.copy()
            v_cmd[:2] -= excess * u[:2] / uh2
            v_cmd = _limit_speed(v_cmd, cfg)
    if not _finite_vec(v_cmd):
        return _brake(t, "nan_output"), ZERO
    # gia toc luu cho chu ky ke = gia toc DA gioi han (khong tinh buoc cat tuc thi an toan, neu khong jerk se tu khuech dai)
    a_out = a_des

    # yaw: mui huong theo duong ngam ngang, gioi han toc do doi
    yaw_own = yaw_from_quat(own.q_world_body)
    yaw_prev = prev.yaw_rad if (prev is not None and prev.yaw_rad is not None and math.isfinite(prev.yaw_rad)) \
        else yaw_own
    hn = math.hypot(u[0], u[1])
    if hn > 0.2:
        yaw_t = math.atan2(u[1], u[0])
        # toc do quay ngang cua duong ngam = thanh phan 'xuong' cua los_rate (vector quay), cat +-0.6 rad bu
        yaw_t = _wrap(yaw_t + max(-0.6, min(0.6, float(omega[2]) * cfg.yaw_lead_s)))
        step = math.radians(cfg.yaw_rate_max_dps) * dt
        yaw_cmd = _wrap(yaw_prev + max(-step, min(step, _wrap(yaw_t - yaw_prev))))
    else:
        yaw_cmd = yaw_prev
    cmd = GuidanceCommand(t=t, vel_ned=(float(v_cmd[0]), float(v_cmd[1]), float(v_cmd[2])),
                          yaw_rad=yaw_cmd, valid=True, reason="+".join(reasons))
    return cmd, (float(a_out[0]), float(a_out[1]), float(a_out[2]))


def _limit_speed(v: np.ndarray, cfg: GuidanceConfig) -> np.ndarray:
    v = np.array(v, float)
    sh = float(np.linalg.norm(v[:2]))
    if sh > cfg.v_max_mps:
        v[:2] *= cfg.v_max_mps / sh
    v[2] = max(-cfg.climb_max_mps, min(cfg.descend_max_mps, v[2]))   # NED: am = len
    return v


def compute_guidance(track: TrackState, own: OwnState, cfg: GuidanceConfig,
                     prev: Optional[GuidanceCommand] = None,
                     prev_accel: Optional[Vec3] = None) -> GuidanceCommand:
    return compute_guidance_ex(track, own, cfg, prev, prev_accel)[0]


class Guidance:
    """Boc mong giu trang thai (lenh truoc, gia toc truoc) cho compute_guidance."""

    def __init__(self, cfg: Optional[GuidanceConfig] = None):
        self.cfg = cfg or GuidanceConfig()
        self._ramp: Optional[ElevRefRamp] = (
            ElevRefRamp(self.cfg.target_elev_ref_deg, self.cfg.elev_ramp_dps, self.cfg.dt_max_s)
            if self.cfg.elev_ramp_enabled else None)
        self.reset()

    def reset(self) -> None:
        if self._ramp is not None:
            self._ramp.reset()
        self.last_elev_ref_deg: Optional[float] = None
        self._last_r: Optional[float] = None
        self.prev: Optional[GuidanceCommand] = None
        self.prev_accel: Optional[Vec3] = ZERO
        # bo nho muc tieu luc TRACK hop le cuoi: (t, v_t NED loc EMA, u, r, vi tri own luc ghi)
        self._mem: Optional[Tuple[float, np.ndarray, np.ndarray, float, np.ndarray]] = None
        self.last_r_hat: Optional[float] = None
        self._last_own: Optional[Tuple[float, np.ndarray]] = None
        self._pos_bad = False                      # pos_ned nhay: bo nho vi tri khong con dung duoc toi khi ghi lai _mem

    def _check_pos(self, own: OwnState) -> None:
        """pos_ned nhay giua hai chu ky (lech khoi p_cu + v*dt qua nguong) -> _pos_bad (chi dung khi blind_floor_m > 0).
        Nguong 3 m + 0.5*a_back*dt^2: nhieu EKF thuong < 3 m; dt ngoai (0, 1] s thi khong so duoc."""
        if not (_finite_vec(own.pos_ned) and _finite_vec(own.vel_ned) and math.isfinite(own.t)):
            return
        p = np.asarray(own.pos_ned, float)
        if self._last_own is not None:
            dt = own.t - self._last_own[0]
            if 0.0 < dt <= 1.0:
                resid = float(np.linalg.norm(p - self._last_own[1] - np.asarray(own.vel_ned, float) * dt))
                if resid > 3.0 + 0.5 * self.cfg.a_back_mps2 * dt * dt:
                    self._pos_bad = True
        self._last_own = (own.t, p)

    def _models(self, t: float):
        """(P_A, v_A, P_B, v_B): muc tieu ham blind_target_decel ngay luc mat (dung o v0^2/2a) / giu nguyen van toc nho."""
        t_m, v0, _, r_m, p_own = self._mem
        u_m = self._mem[2]
        p0 = p_own + u_m * r_m
        dt = t - t_m
        a = self.cfg.blind_target_decel_mps2
        sp = float(np.linalg.norm(v0))
        if sp < 1e-9:
            return p0, v0, p0, v0
        vh = v0 / sp
        td = min(dt, sp / a)
        return p0 + vh * (sp * td - 0.5 * a * td * td), vh * max(0.0, sp - a * dt), p0 + v0 * dt, v0

    def _pred(self, t: float, own: OwnState):
        """(vector tuong doi tu own.pos_ned that toi muc tieu du doan, van toc muc tieu theo mo hinh do) cua mo hinh GAN hon."""
        if not self._mem_ok(t) or not _finite_vec(own.pos_ned):
            return None
        p_a, v_a, p_b, v_b = self._models(t)
        pos = np.asarray(own.pos_ned, float)
        if t - self._mem[0] < self.cfg.blind_grace_model_s:      # moi mat hinh: chi mo hinh giu nguyen van toc
            return p_b - pos, v_b
        if float(np.linalg.norm(p_b - pos)) < float(np.linalg.norm(p_a - pos)):
            return p_b - pos, v_b
        return p_a - pos, v_a

    def predicted_rel(self, t: float, own: OwnState) -> Optional[Vec3]:
        pr = self._pred(t, own)
        return None if pr is None else (float(pr[0][0]), float(pr[0][1]), float(pr[0][2]))

    def stopped_target_ned(self, t: float, own: OwnState) -> Optional[Vec3]:
        """Vi tri NED cua muc tieu khi da dung han theo mo hinh ham (None neu khong co bo nho hop le)."""
        if not self._mem_ok(t):
            return None
        p0 = self._mem[4] + self._mem[2] * self._mem[3]
        sp = float(np.linalg.norm(self._mem[1]))
        p = p0 + (self._mem[1] / sp) * (sp * sp / (2.0 * self.cfg.blind_target_decel_mps2)) if sp > 1e-9 else p0
        return (float(p[0]), float(p[1]), float(p[2]))

    def _mem_ok(self, t: float) -> bool:
        return (self._mem is not None and math.isfinite(t)
                and 0.0 <= t - self._mem[0] <= self.cfg.blind_mem_max_s)

    def _hold_velocity(self, t: float) -> Vec3:
        """Van toc muc tieu nho duoc; toc do ngang giam dan sau blind_grace_s (phong muc tieu dung/phanh)."""
        v = self._mem[1].copy()
        sp = math.hypot(float(v[0]), float(v[1]))
        dec = self.cfg.blind_decel_mps2 * max(0.0, (t - self._mem[0]) - self.cfg.blind_grace_s)
        if sp > 1e-6:
            v[:2] *= max(0.0, sp - dec) / sp
        return (float(v[0]), float(v[1]), float(v[2]))

    def _safe_hold(self, hold: Vec3, own: OwnState, t: float) -> Vec3:
        """Bay tiep trong luc khong thay muc tieu: (1) khong nhanh hon toc do ngang hien tai cua minh (uoc luong
        van toc muc tieu o xa rat nhieu). Khong con nhanh 'dang phanh thi phanh tiep' (tu khoa khi COAST)."""
        h = np.array(hold, float)
        so = math.hypot(float(own.vel_ned[0]), float(own.vel_ned[1]))
        sh = math.hypot(float(h[0]), float(h[1]))
        if sh > so and sh > 1e-6:
            h[:2] *= so / sh
            sh = so
        cap = self.cfg.blind_v_cap_mps
        if cap > 0.0 and sh > cap:                 # tran toc do ngang luc mu
            h[:2] *= cap / sh
        return (float(h[0]), float(h[1]), float(h[2]))

    def _update_mem(self, t: float, info: dict, own: OwnState) -> None:
        v_t = info["v_t"]
        if self._mem is not None and 0.0 < t - self._mem[0] <= 1.0:
            a = 1.0 - math.exp(-(t - self._mem[0]) / max(self.cfg.v_t_mem_tau_s, 1e-3))
            v_t = a * v_t + (1.0 - a) * self._mem[1]
        self._mem = (t, v_t, info["u"], info["r"], np.array(own.pos_ned, float))
        self._pos_bad = False

    def step_blind(self, track: TrackState, own: OwnState) -> GuidanceCommand:
        """Tracker khong con huong ngam (LOST/SEARCH) nhung supervisor con trong thoi han bay tiep:
        bay theo van toc muc tieu nho duoc, mui quay ve huong ngam cuoi. Khong co bo nho -> phanh."""
        return self._blind(track, own, False)

    def step_hover(self, track: TrackState, own: OwnState) -> GuidanceCommand:
        """Nhu step_blind nhung van toc giu = 0: lenh ngang ve 0 theo gioi han gia toc, van lui khi r_hat duoi nguong;
        het bo nho thi chi treo (phanh)."""
        return self._blind(track, own, True)

    def _blind_inputs(self, t: float, own: OwnState):
        """(u, r, cfg) cho lenh luc khong thay muc tieu: khi blind_floor_m > 0 dung r_hat du doan va nguong lui
        floor + margin + quang dung theo toc do tiep can tuong doi; neu khong, huong/khoang cach dong bang va cfg goc."""
        cfg = self.cfg
        u, r, cfg_eff = self._mem[2], self._mem[3], cfg
        pr = self._pred(t, own)
        if pr is not None:
            rel, v_tgt = pr
            r_hat = float(np.linalg.norm(rel))
            self.last_r_hat = r_hat
            if cfg.blind_floor_m > 0.0 and r_hat > 1e-6:
                u, r = rel / r_hat, r_hat
                # toc do TIEP CAN TUONG DOI (>= 0) toi muc tieu du doan -> quang dung
                v_close = max(0.0, float((np.asarray(own.vel_ned, float) - v_tgt) @ u))
                d_stop = v_close * cfg.blind_react_s + v_close * v_close / (2.0 * cfg.a_back_mps2)
                cfg_eff = dataclasses.replace(cfg, range_min_m=cfg.blind_floor_m,
                                              range_back_m=cfg.blind_floor_m + cfg.blind_back_margin_m + d_stop)
        return u, r, cfg_eff

    def _blind(self, track: TrackState, own: OwnState, hover: bool) -> GuidanceCommand:
        cfg = self.cfg
        self.last_r_hat = None                      # chi con so khi co khoang cach du doan con han o chu ky nay
        self._check_pos(own)
        if not self._mem_ok(track.t):
            return self.step(track, own)
        if cfg.blind_floor_m > 0.0 and self._pos_bad:      # khong con khoang cach hop le -> phanh
            cmd = _brake(track.t, "pos_jump")
            self.prev, self.prev_accel = cmd, ZERO
            return cmd
        u, r, cfg_eff = self._blind_inputs(track.t, own)
        synth = TrackState(t=track.t, status=TrackStatus.COAST, los_ned=tuple(float(c) for c in u),
                           los_rate_ned=ZERO, range_m=r, range_rate_mps=0.0, range_valid=True)
        er = self._ramp.update(track.t, None) if self._ramp is not None else None
        self.last_elev_ref_deg = er
        hold = ZERO if hover else self._hold_velocity(track.t)
        cmd, acc = compute_guidance_ex(synth, own, cfg_eff, self.prev, self.prev_accel,
                                       v_t_hold=self._safe_hold(hold, own, track.t), elev_ref_deg=er)
        cmd = dataclasses.replace(cmd, reason=cmd.reason + "+blind")
        self.prev, self.prev_accel = cmd, acc
        return cmd

    def step(self, track: TrackState, own: OwnState) -> GuidanceCommand:
        self._check_pos(own)
        # COAST: khoang cach ngoai suy cua tracker troi nhanh (r_dot cu khi chinh minh doi toc do);
        # dung khoang cach hop le cuoi cung, dong bang, va r_dot = 0
        if track.status == TrackStatus.TRACK and track.range_valid and track.range_m is not None \
                and math.isfinite(track.range_m):
            self._last_r = track.range_m
        elif track.status == TrackStatus.COAST and self._last_r is not None:
            track = dataclasses.replace(track, range_m=self._last_r, range_rate_mps=0.0,
                                        range_valid=track.range_valid or self._last_r is not None)
        elif track.status != TrackStatus.COAST:
            self._last_r = None if track.status != TrackStatus.TRACK else self._last_r
        # TRACK nhung khoang cach khong tin (vua bat lai sau khi mat, sat mep anh): dung khoang cach nho duoc
        # va van toc muc tieu nho duoc nhu COAST (khong tien lai gan, khong giat ve van toc ban than)
        mem_ok = self._mem_ok(track.t)
        seen = False                                # TRACK doi sang duong nho: van thay muc tieu, giu hanh vi dung nhu cu
        if (mem_ok and track.status == TrackStatus.TRACK and track.los_ned is not None
                and not (track.range_valid and track.range_m is not None and math.isfinite(track.range_m))):
            seen = True
            track = dataclasses.replace(track, status=TrackStatus.COAST, range_m=self._mem[3],
                                        range_rate_mps=0.0, range_valid=True)
        cfg_run = self.cfg
        if self.cfg.blind_floor_m > 0.0 and mem_ok and not seen and track.status == TrackStatus.COAST:
            # that su khong thay muc tieu: cung r_hat / nguong lui / kiem pos_ned nhu step_blind
            if self._pos_bad:
                cmd = _brake(track.t, "pos_jump")
                self.prev, self.prev_accel = cmd, ZERO
                return cmd
            u_b, r_b, cfg_run = self._blind_inputs(track.t, own)
            track = dataclasses.replace(track, los_ned=tuple(float(c) for c in u_b), los_rate_ned=ZERO,
                                        range_m=r_b, range_rate_mps=0.0, range_valid=True)
        hold = (self._safe_hold(self._hold_velocity(track.t), own, track.t)
                if (mem_ok and track.status == TrackStatus.COAST) else None)
        info: dict = {}
        er = None
        if self._ramp is not None:
            el = None
            if track.status == TrackStatus.TRACK and track.los_ned is not None and _finite_vec(track.los_ned):
                u = np.asarray(track.los_ned, float)
                nu = float(np.linalg.norm(u))
                if nu > _EPS:
                    el = math.asin(max(-1.0, min(1.0, -float(u[2]) / nu)))
            er = self._ramp.update(track.t, el)
        self.last_elev_ref_deg = er
        cmd, acc = compute_guidance_ex(track, own, cfg_run, self.prev, self.prev_accel, hold, info,
                                       elev_ref_deg=er, target_seen=seen)
        if info and math.isfinite(track.t) and _finite_vec(info["v_t"]):
            self._update_mem(track.t, info, own)
        self.prev, self.prev_accel = cmd, acc
        return cmd
