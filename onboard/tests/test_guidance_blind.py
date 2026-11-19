"""An toan LUC MU cua dan duong (.office/design-search.md muc (e) + SUA THEO PHAN BIEN CUA 08: S-1, S-4). PHA DO TDD.

Giao dien test khoa (dtrack.guidance.Guidance, dtrack.config.GuidanceConfig):
  - GuidanceConfig: blind_floor_m (0 = tat), blind_back_margin_m (2.0), blind_target_decel_mps2 (3.0 theo TIEU CHI C6 MOI cua nguoi
    dung, thay 8.0 cua S-1), blind_v_cap_mps (0 = tat). Mac dinh do test_search_config.py ghim; o day chi dung (rieng decel: co ca ghim).
  - TIEU CHI C6 MOI (nguoi dung chot): muc tieu bay deu -> d3 min >= 8 m; ham toi 3 m/s^2 (1.5, 3.0) -> >= 6 m; phanh gap 8 m/s^2 ->
    CHI DO va ghi so (khong cham dat). Dinh nghia v_tien (tuyet doi hay tuong doi) CHUA ghim: cac ca dung duoc voi ca hai.
  - Guidance.step_hover(track, own) -> GuidanceCommand: nhu step_blind nhung v_t_hold = 0 (treo; van lui neu r_hat < floor+margin).
  - Guidance.predicted_rel(t, own) -> Optional[Vec3]: vector TUONG DOI (muc tieu - own.pos_ned that), lay mo hinh cho
    KHOANG CACH NHO NHAT trong hai mo hinh (S-1): (A) muc tieu ham blind_target_decel ngay luc mat, (B) giu nguyen van toc nho.
    Khong co bo nho hop le (chua co / qua blind_mem_max_s) -> None.
  - Guidance.stopped_target_ned(t, own) -> Optional[Vec3]: vi tri muc tieu khi dung han (mo hinh A), NED tuyet doi.
  - Guidance.last_r_hat: khoang cach du doan (m) dung o chu ky gan nhat cua step_blind/step_hover.
  - Phanh = lenh vel_ned == (0,0,0) va reason bat dau bang "brake".
Quyet dinh tu chot cho cho thiet ke mo ho (xem bao cao): (1) pos_ned nhay (ca 50 m trong mot chu ky 30 Hz) -> phanh o chu ky nhay VA cac chu ky
sau (bo nho vi tri cu khong con dung duoc); (2) vong kin dung drone bac nhat tau = 1 s, gia toc ngang bi cat o a_back_mps2
cua cau hinh; muc tieu 15 m phia truoc, cung toc do 10 m/s; 4 s dau step_blind (pha 0), sau do step_hover (pha 1).
Ca bao ve (PASS ngay tren ma hien tai): (i) khong bo nho -> phanh o step_blind, (x) cau hinh mac dinh giong het cu.
Quyet dinh truong phong (bo sung): blind_react_s (mac dinh 1.0, 0..5). Khi blind_floor_m > 0, nguong lui = floor + margin + d_dung,
  d_dung = v_tien*blind_react_s + v_tien^2/(2*a_back_mps2), v_tien >= 0 (dinh nghia chua chot); v_tien ~ 0 -> nguong = floor + margin.
SO DO "TRUOC" (ma hien tai, cau hinh mac dinh, 4 s step_blind roi phanh `Guidance.step` LOST, do 3 lan giong het nhau vi mo phong
  xac dinh): khoang cach 3D nho nhat trong 20 s sau khi mat hinh = 1.020 m (muc tieu phanh 8 m/s^2, tai 2.17 s) va 3.233 m
  (muc tieu ham 1.5 m/s^2, tai 20.0 s). Cach do: simulate(GuidanceConfig(cam_tilt_up_deg=0), v_brake(a), use_hover=False) cua file nay
  (bay on dinh 10 s cach 15 m, ca hai 10 m/s; drone bac nhat tau 1 s, gia toc ngang cat o a_back_mps2 = 12).
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dtrack.config import GuidanceConfig  # noqa: E402
from dtrack.guidance import Guidance  # noqa: E402
from dtrack.types import OwnState, TrackState, TrackStatus  # noqa: E402

Q0 = (1.0, 0.0, 0.0, 0.0)
DT = 1.0 / 30.0
ALT = 30.0
TAU_FC = 1.0                       # s, tre bac nhat cua FC (theo ban giao viec)
FLOOR = 8.0
SIN4, COS4 = math.sin(math.radians(4.0)), math.cos(math.radians(4.0))     # muc tieu o goc nang 4 do = target_elev_ref_deg
NEW_KEYS = ("blind_floor_m", "blind_back_margin_m", "blind_target_decel_mps2", "blind_v_cap_mps")


def make_cfg(**kw):
    """GuidanceConfig voi khoa moi; thieu khoa -> fail co thong bao (khong phai loi TypeError mo ho)."""
    base = GuidanceConfig(cam_tilt_up_deg=0.0)
    missing = [k for k in kw if not hasattr(base, k)]
    assert not missing, "GuidanceConfig thieu khoa cau hinh moi: %s" % missing
    return GuidanceConfig(cam_tilt_up_deg=0.0, **kw)


def make_cfg0(**kw):
    """Nhu make_cfg nhung dat TUONG MINH blind_grace_model_s = 0 (hanh vi cu: luon lay min hai mo hinh) neu khoa da co;
    chua co khoa (ma truoc khi them) thi bo qua: hanh vi hien tai chinh la grace = 0."""
    if hasattr(GuidanceConfig(), "blind_grace_model_s"):
        kw = dict(kw, blind_grace_model_s=0.0)
    return make_cfg(**kw)


def own_at(pos, vel, t):
    return OwnState(t=t, pos_ned=tuple(float(c) for c in pos), vel_ned=tuple(float(c) for c in vel),
                    q_world_body=Q0, armed=True, mode="GUIDED")


def track_at(t, rel, vt=(0.0, 0.0, 0.0), vown=(0.0, 0.0, 0.0)):
    rel = np.asarray(rel, float)
    r = float(np.linalg.norm(rel))
    u = rel / r
    rdot = float((np.asarray(vt, float) - np.asarray(vown, float)) @ u)
    return TrackState(t=t, status=TrackStatus.TRACK, los_ned=tuple(float(c) for c in u), los_rate_ned=(0.0, 0.0, 0.0),
                      range_m=r, range_sigma_m=1.0, range_rate_mps=rdot, range_valid=True)


def lost_at(t):
    return TrackState(t=t, status=TrackStatus.LOST)


def hspeed(cmd):
    return math.hypot(cmd.vel_ned[0], cmd.vel_ned[1])


def is_brake(cmd):
    return tuple(cmd.vel_ned) == (0.0, 0.0, 0.0) and cmd.reason.startswith("brake")


# ======================================================================= vong kin diem khoi
class Plant:
    """Drone: dv/dt = (v_lenh - v)/TAU_FC, cat gia toc ngang o a_back_mps2 va doc o a_max_z_mps2 cua cau hinh."""

    def __init__(self, cfg, pos, vel):
        self.cfg, self.pos, self.vel = cfg, np.array(pos, float), np.array(vel, float)

    def step(self, cmd_vel, dt=DT):
        a = (np.asarray(cmd_vel, float) - self.vel) / TAU_FC
        ah = float(np.hypot(a[0], a[1]))
        if ah > self.cfg.a_back_mps2:
            a[:2] *= self.cfg.a_back_mps2 / ah
        a[2] = max(-self.cfg.a_max_z_mps2, min(self.cfg.a_max_z_mps2, a[2]))
        self.vel = self.vel + a * dt
        self.pos = self.pos + self.vel * dt


def v_brake(decel, v0=10.0):
    return lambda tau: np.array([max(0.0, v0 - decel * tau), 0.0, 0.0])


def v_const(v0=10.0):
    return lambda tau: np.array([v0, 0.0, 0.0])


def v_turn_back(decel=8.0, v_back=5.0, v0=10.0):
    """Phanh `decel` roi quay dau tien lai ve phia drone voi v_back."""
    return lambda tau: np.array([max(-v_back, v0 - decel * tau), 0.0, 0.0])


def simulate(cfg, target_v, t_total=20.0, warm_s=10.0, r0=15.0, v0=10.0, hover_from=4.0, use_hover=True, policy=None,
             probe=None):
    """Bam on dinh warm_s giay (TRACK hop le), roi mat hinh. Tra ve (d3_min, t_min, speeds_h).
    policy(tau) -> lenh van toc NED thay cho guidance (de kiem chung chinh vong mo phong); use_hover=False -> dung
    Guidance.step (LOST -> phanh), la hanh vi hien tai cua supervisor sau coast_follow_s."""
    g = Guidance(cfg)
    tgt = np.array([r0 * COS4, 0.0, -(ALT + r0 * SIN4)])
    tv = np.array([v0, 0.0, 0.0])
    plant = Plant(cfg, (0.0, 0.0, -ALT), (v0, 0.0, 0.0))
    t = 100.0
    for _ in range(int(round(warm_s / DT))):
        own = own_at(plant.pos, plant.vel, t)
        cmd = g.step(track_at(t, tgt - plant.pos, tv, plant.vel), own)
        plant.step(cmd.vel_ned)
        tgt = tgt + tv * DT
        t += DT
    t_lose = t
    d_min, t_min, speeds = float(np.linalg.norm(tgt - plant.pos)), 0.0, []
    for _ in range(int(round(t_total / DT))):
        tau = t - t_lose
        if probe is not None:                # khoang cach toi muc tieu that tai tau = 4 s va 8 s (do muc bi bo lai)
            for tp in (4.0, 8.0):
                if tp not in probe and tau >= tp - 1e-9:
                    probe[tp] = float(np.linalg.norm(tgt - plant.pos))
        own = own_at(plant.pos, plant.vel, t)
        if policy is not None:
            vel = policy(tau)
        else:
            trk = lost_at(t)
            if tau < hover_from:
                cmd = g.step_blind(trk, own)
            elif use_hover:
                cmd = g.step_hover(trk, own)
            else:
                cmd = g.step(trk, own)
            vel = cmd.vel_ned
            speeds.append(math.hypot(vel[0], vel[1]))
        plant.step(vel)
        tv = target_v(tau)
        tgt = tgt + tv * DT
        t += DT
        d = float(np.linalg.norm(tgt - plant.pos))
        if d < d_min:
            d_min, t_min = d, t - t_lose
    return d_min, t_min, speeds


def simulate_seq(cfg, target_v, t_total=20.0, warm_s=10.0, r0=15.0, v0=10.0, coast_s=3.0, blind_until=4.0,
                 regain_at=None, probe=None, use_hover=True, info=None):
    """TRINH TU THAT cua supervisor (supervisor.py, coast_follow_s = 4): mat hinh -> `step()` voi track COAST (bo bam ngoai suy
    van toc hang, toi coast_s = 3 s, tracker coast_timeout) -> `step_blind` (toi blind_until = 4 s) -> `step_hover`.
    regain_at: tu tau do TRACK that tro lai (0.3 s dau range_valid=False, nhu vua bat lai), moi chu ky dung `step()`.
    info (dict, tuy chon) duoc dien: cmds (vel_ned moi chu ky), vx_pre (lenh vx cuoi truoc khi mat), vx_min_loss (lenh vx nho nhat
    luc chua co hinh lai), d_after {2, 4, 8: khoang cach toi muc tieu that sau regain_at + so do}.
    Tra (d3_min, t_min, [reason moi chu ky])."""
    g = Guidance(cfg)
    tgt = np.array([r0 * COS4, 0.0, -(ALT + r0 * SIN4)])
    tv = np.array([v0, 0.0, 0.0])
    plant = Plant(cfg, (0.0, 0.0, -ALT), (v0, 0.0, 0.0))
    t = 100.0
    cmd = None
    for _ in range(int(round(warm_s / DT))):
        cmd = g.step(track_at(t, tgt - plant.pos, tv, plant.vel), own_at(plant.pos, plant.vel, t))
        plant.step(cmd.vel_ned)
        tgt = tgt + tv * DT
        t += DT
    t_lose, p_last = t, tgt.copy()
    if info is not None:
        info.update(cmds=[], vx_pre=float(cmd.vel_ned[0]), vx_min_loss=float(cmd.vel_ned[0]), d_after={})
    d_min, t_min, reasons = float(np.linalg.norm(tgt - plant.pos)), 0.0, []
    for _ in range(int(round(t_total / DT))):
        tau = t - t_lose
        if probe is not None:
            for tp in (4.0, 8.0):
                if tp not in probe and tau >= tp - 1e-9:
                    probe[tp] = float(np.linalg.norm(tgt - plant.pos))
        own = own_at(plant.pos, plant.vel, t)
        if info is not None and regain_at is not None:
            for tp in (2.0, 4.0, 8.0):
                if tp not in info["d_after"] and tau >= regain_at + tp - 1e-9:
                    info["d_after"][tp] = float(np.linalg.norm(tgt - plant.pos))
        if regain_at is not None and tau >= regain_at:
            rel = tgt - plant.pos
            if tau >= regain_at + 0.3:
                trk = track_at(t, rel, tv, plant.vel)
            else:
                u = rel / float(np.linalg.norm(rel))
                trk = TrackState(t=t, status=TrackStatus.TRACK, los_ned=tuple(float(c) for c in u),
                                 los_rate_ned=(0.0, 0.0, 0.0), range_m=None, range_valid=False)
            cmd = g.step(trk, own)
        elif tau < coast_s:
            rel = p_last + np.array([v0, 0.0, 0.0]) * tau - plant.pos         # ngoai suy van toc hang cua bo bam
            r = float(np.linalg.norm(rel))
            u = rel / r
            trk = TrackState(t=t, status=TrackStatus.COAST, los_ned=tuple(float(c) for c in u), los_rate_ned=(0.0, 0.0, 0.0),
                             range_m=r, range_sigma_m=1.0, range_rate_mps=float((np.array([v0, 0.0, 0.0]) - plant.vel) @ u),
                             range_valid=True, age_s=tau)
            cmd = g.step(trk, own)
        elif tau < blind_until:
            cmd = g.step_blind(lost_at(t), own)
        elif use_hover:
            cmd = g.step_hover(lost_at(t), own)
        else:
            cmd = g.step(lost_at(t), own)
        reasons.append(cmd.reason)
        if info is not None:
            info["cmds"].append(tuple(float(x) for x in cmd.vel_ned))
            if regain_at is None or tau < regain_at:
                info["vx_min_loss"] = min(info["vx_min_loss"], float(cmd.vel_ned[0]))
        plant.step(cmd.vel_ned)
        tgt = tgt + target_v(tau) * DT
        tv = target_v(tau)
        t += DT
        d = float(np.linalg.norm(tgt - plant.pos))
        if d < d_min:
            d_min, t_min = d, t - t_lose
    return d_min, t_min, reasons


# ---- kiem chung chinh vong mo phong (khong dung ma san pham): khong co ca "du de" lan "bat kha thi" ----
def test_harness_oracle_policy_braking_target_is_feasible():
    """Chinh sach lenh 0 ngay luc mat: drone troi ~10 m (tau 1 s), muc tieu dung o +21.25 m -> d >= 11 m: ca 8 m/s^2 kha thi."""
    d, _, _ = simulate(make_cfg(), v_brake(8.0), policy=lambda tau: (0.0, 0.0, 0.0))
    assert d >= 10.9, d


def test_harness_keep_flying_policy_hits_the_target():
    """Chinh sach 'bay tiep 10 m/s' (nhu chua co an toan): phai vi pham san 8 m, neu khong ca (ii) vo nghia."""
    d, _, _ = simulate(make_cfg(), v_brake(8.0), policy=lambda tau: (10.0, 0.0, 0.0))
    assert d < FLOOR, d


# ======================================================================= (i) khong bo nho -> phanh
def test_step_blind_without_memory_brakes():
    g = Guidance(GuidanceConfig(cam_tilt_up_deg=0.0))
    c = g.step_blind(lost_at(50.0), own_at((0.0, 0.0, -ALT), (10.0, 0.0, 0.0), 50.0))
    assert is_brake(c), c


def test_step_blind_memory_not_written_by_invalid_range_track():
    """TRACK nhung range_valid=False khong ghi _mem (E1: chi ghi o nhanh valid) -> mat hinh la phanh."""
    g = Guidance(GuidanceConfig(cam_tilt_up_deg=0.0))
    o = own_at((0.0, 0.0, -ALT), (10.0, 0.0, 0.0), 10.0)
    for k in range(30):
        g.step(TrackState(t=10.0 + k * DT, status=TrackStatus.TRACK, los_ned=(1.0, 0.0, 0.0), los_rate_ned=(0, 0, 0),
                          range_m=None, range_valid=False), o)
    c = g.step_blind(lost_at(11.5), o)
    assert is_brake(c), c


def test_step_hover_without_memory_brakes():
    g = Guidance(make_cfg(blind_floor_m=FLOOR))
    c = g.step_hover(lost_at(50.0), own_at((0.0, 0.0, -ALT), (10.0, 0.0, 0.0), 50.0))
    assert is_brake(c), c


# ======================================================================= (ii)-(v) vong kin C6
C6_STEADY_M = 8.0       # tieu chi C6 (nguoi dung chot): muc tieu bay deu -> d3 min >= 8 m
C6_GENTLE_M = 6.0       # muc tieu ham toi 3 m/s^2 -> d3 min >= 6 m; phanh 8 m/s^2: CHI DO, khong cham dat/khong


def test_blind_target_decel_default_is_3():
    assert getattr(GuidanceConfig(), "blind_target_decel_mps2", None) == 3.0


@pytest.mark.parametrize("decel", [1.5, 3.0])
def test_blind_min_distance_when_target_brakes_gently(decel):
    """(iii) muc tieu ham 1.5 va 3.0 m/s^2: d3 nho nhat trong 20 s sau khi mat hinh >= 6 m (C6)."""
    probe = {}
    d, t_min, _ = simulate(make_cfg0(blind_floor_m=FLOOR), v_brake(decel), probe=probe)
    print("DO ham %.1f: d3 min = %.2f m tai %.2f s; d(4 s) = %.2f m; d(8 s) = %.2f m" % (decel, d, t_min, probe[4.0], probe[8.0]))
    assert d >= C6_GENTLE_M, "d3 min = %.2f m tai tau = %.2f s (decel muc tieu %.1f m/s^2)" % (d, t_min, decel)


def test_blind_min_distance_when_target_keeps_velocity():
    """(iv) muc tieu giu nguyen 10 m/s: d3 >= 8 m."""
    probe = {}
    d, t_min, _ = simulate(make_cfg0(blind_floor_m=FLOOR), v_const(), probe=probe)
    print("DO bay deu: d3 min = %.2f m tai %.2f s; d(4 s) = %.2f m; d(8 s) = %.2f m" % (d, t_min, probe[4.0], probe[8.0]))
    assert d >= C6_STEADY_M, "d3 min = %.2f m tai tau = %.2f s" % (d, t_min)


def test_blind_measure_only_when_target_brakes_hard_8(record_property):
    """(ii) muc tieu phanh gap 8 m/s^2: CHI DO va ghi so (nguoi dung khong yeu cau dat): xem `pytest -rA` (stdout) hoac
    record_property d3_min_m / d_4s_m / d_8s_m. Khong assert nguong."""
    probe = {}
    d, t_min, _ = simulate(make_cfg0(blind_floor_m=FLOOR), v_brake(8.0), probe=probe)
    record_property("d3_min_m", round(d, 3))
    record_property("d_4s_m", round(probe[4.0], 3))
    record_property("d_8s_m", round(probe[8.0], 3))
    print("DO phanh 8: d3 min = %.2f m tai %.2f s; d(4 s) = %.2f m; d(8 s) = %.2f m" % (d, t_min, probe[4.0], probe[8.0]))
    assert d > 0.0


@pytest.mark.xfail(strict=False, reason=(
    "RUI RO DA BIET, THIET KE KHONG PHU. (v) ca hai mo hinh du doan (ham / giu van toc) deu cho muc tieu di XA hoac dung; muc tieu quay dau "
    "tien lai 5 m/s khong nam trong mo hinh nao (r_hat song theo diem dung cu), nen hover 16 s khong tranh duoc. "
    "Chi ghi nhan d3 min; khong dat nguong rieng."))
def test_blind_min_distance_when_target_turns_back_toward_drone():
    d, t_min, _ = simulate(make_cfg0(blind_floor_m=FLOOR), v_turn_back())
    print("DO (v): d3 min = %.2f m tai tau = %.2f s" % (d, t_min))
    assert d >= FLOOR, "d3 min = %.2f m tai tau = %.2f s" % (d, t_min)


# ======================================================================= (vi) tran van toc ngang
def _blind_speeds(cfg, v=20.0, seconds=3.6):
    g = Guidance(cfg)
    o = own_at((0.0, 0.0, -ALT), (v, 0.0, 0.0), 10.0)
    t = 10.0
    for _ in range(60):
        g.step(track_at(t, (15.0, 0.0, 0.0), (v, 0.0, 0.0), (v, 0.0, 0.0)), o)
        t += DT
    out = []
    for k in range(1, int(seconds / DT) + 1):
        out.append((k * DT, hspeed(g.step_blind(lost_at(t + k * DT), o))))
    return out


def test_blind_speed_capped_at_blind_v_cap():
    """Van toc nho 20 m/s, tran 12: lenh bi ha toc theo a_decel (3 m/s^2: 20 -> 12 mat 2.7 s); sau 3.0 s phai <= 12.
    Doi chung khong tran (0): cung thoi diem van > 12 (chung to chinh tran gay ra)."""
    capped = [s for tt, s in _blind_speeds(make_cfg(blind_v_cap_mps=12.0)) if tt >= 3.0]
    free = [s for tt, s in _blind_speeds(make_cfg(blind_v_cap_mps=0.0)) if tt >= 3.0]
    assert max(capped) <= 12.0 + 0.05, max(capped)         # dung sai 0.05 m/s cho bo gioi han gia toc/jerk
    assert min(free) > 12.0, min(free)


# ======================================================================= (vii) step_hover
def _hover_setup(cfg, r=40.0, v_own=(10.0, 0.0, 0.0)):
    g = Guidance(cfg)
    o = own_at((0.0, 0.0, -ALT), v_own, 10.0)
    t = 10.0
    for _ in range(60):
        g.step(track_at(t, (r, 0.0, 0.0), v_own, v_own), o)
        t += DT
    return g, o, t


def test_step_hover_horizontal_command_decays_to_zero_within_accel_limit():
    cfg = make_cfg(blind_floor_m=FLOOR)
    g, o, t = _hover_setup(cfg)
    prev = hspeed(g.step_hover(lost_at(t), o))        # chu ky dau bi cat ve toc do own (10): khong ghim toc do giam
    assert prev > 5.0, prev
    for k in range(1, int(7.0 / DT) + 1):
        c = g.step_hover(lost_at(t + k * DT), o)
        s = hspeed(c)
        if prev > 0.2:                                  # gan 0: bo qua dao dong nho
            assert s <= prev + 1e-9, (k, s, prev)       # khong tang
        assert prev - s <= cfg.a_decel_mps2 * DT + 1e-6, (k, s, prev)      # giam khong nhanh hon a_decel
        prev = s
    assert prev <= 0.1, prev


def _still_mem(cfg, own_x, r):
    """Drone dung yen o x = own_x, muc tieu dung yen cach r phia truoc (nho bang TRACK hop le 2 s) -> P0 = own_x + r."""
    g = Guidance(cfg)
    o = own_at((own_x, 0.0, -ALT), (0.0, 0.0, 0.0), 10.0)
    t = 10.0
    for _ in range(60):
        g.step(track_at(t, (r, 0.0, 0.0)), o)
        t += DT
    return g, o, t


def test_step_hover_backs_off_when_predicted_range_below_floor_plus_margin():
    """Muc tieu dung yen cach 8 m < floor + margin = 10 -> lui (lenh x < 0, ly do min_range)."""
    g, o, t = _still_mem(make_cfg(blind_floor_m=FLOOR), 12.0, 8.0)
    for k in range(1, 16):
        c = g.step_hover(lost_at(t + k * DT), o)
    assert c.vel_ned[0] < -1.0, c
    assert "min_range" in c.reason, c.reason


def test_step_hover_does_not_back_off_when_far_enough():
    g, o, t = _still_mem(make_cfg(blind_floor_m=FLOOR), 0.0, 20.0)
    for k in range(1, 16):
        c = g.step_hover(lost_at(t + k * DT), o)          # r_hat = 20 m
    assert c.vel_ned[0] >= -1e-6, c
    assert "min_range" not in c.reason, c.reason


def test_step_hover_does_not_back_off_for_stationary_target_11m_away_when_hovering():
    """v_tien = 0 (dang treo): nguong lui = floor + margin = 10 m; muc tieu dung yen cach 11 m -> khong lui."""
    g, o, t = _still_mem(make_cfg(blind_floor_m=FLOOR), 0.0, 11.0)
    for k in range(1, 16):
        c = g.step_hover(lost_at(t + k * DT), o)
    assert "min_range" not in c.reason, c.reason      # (lenh x co the am do chu ky TRACK truoc: khong ghim)


def test_step_hover_backs_off_earlier_when_closing_fast():
    """Doi chung: drone tien 10 m/s ve muc tieu DUNG YEN cach 20 m (hai dinh nghia v_tien trung nhau = 10) -> nguong
    > 20 m (floor + margin = 10 chua du) -> lui; khong ghim con so nguong."""
    cfg = make_cfg(blind_floor_m=FLOOR)
    g = Guidance(cfg)
    v = (10.0, 0.0, 0.0)
    o = own_at((0.0, 0.0, -ALT), v, 10.0)
    t = 10.0
    for _ in range(60):
        g.step(track_at(t, (20.0, 0.0, 0.0), (0.0, 0.0, 0.0), v), o)
        t += DT
    for k in range(1, 6):
        c = g.step_hover(lost_at(t + k * DT), o)
    assert "min_range" in c.reason, c.reason


def test_blind_react_s_default_and_validation():
    from dtrack.config import AppConfig, GuidanceConfig, validate
    assert getattr(GuidanceConfig(), "blind_react_s", None) == 1.0
    for ok in (0.0, 1.0, 5.0):
        validate(AppConfig(guidance=make_cfg(blind_react_s=ok)))
    for bad in (-0.1, 5.1):
        with pytest.raises(ValueError):
            validate(AppConfig(guidance=make_cfg(blind_react_s=bad)))


def test_step_hover_after_memory_expiry_only_holds_position():
    """Qua blind_mem_max_s (8 s): khong con r_hat -> chi treo (phanh), khong lui du r_hat cu la 8 m < 10 m."""
    cfg = make_cfg(blind_floor_m=FLOOR)
    g, o, t = _still_mem(cfg, 12.0, 8.0)
    c = g.step_hover(lost_at(t + cfg.blind_mem_max_s + 1.0), o)
    assert is_brake(c), c
    assert "min_range" not in c.reason


# ======================================================================= (viii) mo hinh du doan, tinh tay
def _mem_guidance(decel, v0=10.0):
    """Mem: own (0,0,-30), v_t = (v0,0,0), u = +x, r = 20 -> P0 = (20,0,-30) tai t_m."""
    cfg = make_cfg0(blind_floor_m=FLOOR, blind_target_decel_mps2=decel)
    g = Guidance(cfg)
    t_m = 50.0
    g.step(track_at(t_m, (20.0, 0.0, 0.0), (v0, 0.0, 0.0), (v0, 0.0, 0.0)), own_at((0.0, 0.0, -ALT), (v0, 0.0, 0.0), t_m))
    return g, t_m


@pytest.mark.parametrize("decel,dt,own_x,expect_rel_x", [
    (8.0, 0.5, 3.0, 21.0),     # A: s = 5 - 0.5*8*0.25 = 4 -> P = 24; B: P = 25 -> min = A: 24 - 3
    (8.0, 2.0, 5.0, 21.25),    # A dung han o 20 + 6.25 = 26.25 (10^2/16); B: 40 -> min = A: 26.25 - 5
    (3.0, 2.0, 5.0, 29.0),     # A: s = 20 - 0.5*3*4 = 14 (< v0^2/2a = 16.67: chua dung) -> P = 34; B: 40 -> A: 34 - 5
    (8.0, 0.0, 0.0, 20.0),     # dt = 0: ca hai = P0
])
def test_predicted_rel_takes_nearer_of_two_models_hand_values(decel, dt, own_x, expect_rel_x):
    g, t_m = _mem_guidance(decel)
    rel = g.predicted_rel(t_m + dt, own_at((own_x, 0.0, -ALT), (0.0, 0.0, 0.0), t_m + dt))
    assert rel is not None
    assert tuple(rel) == pytest.approx((expect_rel_x, 0.0, 0.0), abs=1e-6)


def test_predicted_rel_uses_constant_velocity_model_when_it_is_nearer():
    """Drone da o x = 45 (vuot ca hai diem): A dung o 26.25 (cach 18.75), B o 20 + 10*2 = 40 (cach 5) -> chon B: rel = -5."""
    g, t_m = _mem_guidance(8.0)
    rel = g.predicted_rel(t_m + 2.0, own_at((45.0, 0.0, -ALT), (0.0, 0.0, 0.0), t_m + 2.0))
    assert tuple(rel) == pytest.approx((-5.0, 0.0, 0.0), abs=1e-6)


def test_predicted_rel_is_relative_to_real_own_position_not_to_memorised_one():
    g, t_m = _mem_guidance(8.0)
    rel = g.predicted_rel(t_m, own_at((4.0, 3.0, -ALT + 2.0), (0.0, 0.0, 0.0), t_m))
    assert tuple(rel) == pytest.approx((20.0 - 4.0, -3.0, -2.0), abs=1e-6)       # P0 = (20, 0, -30)


@pytest.mark.parametrize("decel,expect_x", [(8.0, 26.25), (3.0, 20.0 + 100.0 / 6.0)])
def test_stopped_target_ned_hand_values(decel, expect_x):
    g, t_m = _mem_guidance(decel)
    p = g.stopped_target_ned(t_m + 1.0, own_at((2.0, 0.0, -ALT), (0.0, 0.0, 0.0), t_m + 1.0))
    assert tuple(p) == pytest.approx((expect_x, 0.0, -ALT), abs=1e-6)


def test_predicted_rel_none_without_memory_or_after_expiry():
    cfg = make_cfg()
    o = own_at((0.0, 0.0, -ALT), (0.0, 0.0, 0.0), 50.0)
    assert Guidance(cfg).predicted_rel(50.0, o) is None
    assert Guidance(cfg).stopped_target_ned(50.0, o) is None
    g, t_m = _mem_guidance(8.0)
    assert g.predicted_rel(t_m + cfg.blind_mem_max_s + 1.0, o) is None


def test_last_r_hat_matches_norm_of_predicted_rel():
    g, t_m = _mem_guidance(8.0)
    o = own_at((3.0, 0.0, -ALT), (0.0, 0.0, 0.0), t_m + 0.5)
    g.step_blind(lost_at(t_m + 0.5), o)
    assert g.last_r_hat == pytest.approx(21.0, abs=1e-6)


# ======================================================================= (ix) pos_ned nhay
def _run_blind_with_pos_jump(jump_m):
    cfg = make_cfg(blind_floor_m=FLOOR)
    g = Guidance(cfg)
    v = (10.0, 0.0, 0.0)
    t = 10.0
    for k in range(60):
        g.step(track_at(t, (15.0, 0.0, 0.0), v, v), own_at((10.0 * k * DT, 0.0, -ALT), v, t))
        t += DT
    x = 10.0 * 60 * DT
    cmds = []
    for k in range(6):
        if k == 2:
            x += jump_m                                   # EKF nhay vi tri giua hai chu ky
        cmds.append(g.step_blind(lost_at(t), own_at((x, 0.0, -ALT), v, t)))
        x += 10.0 * DT
        t += DT
    return cmds


def test_pos_ned_jump_brakes_and_does_not_trust_prediction():
    cmds = _run_blind_with_pos_jump(50.0)
    assert all(not is_brake(c) for c in cmds[:2]), [c.reason for c in cmds[:2]]
    assert all(is_brake(c) for c in cmds[2:]), [(c.vel_ned, c.reason) for c in cmds[2:]]


def test_pos_ned_normal_motion_does_not_brake():
    cmds = _run_blind_with_pos_jump(0.0)
    assert all(not is_brake(c) for c in cmds), [(c.vel_ned, c.reason) for c in cmds]


# ======================================================================= (x) mac dinh giong het hien tai
GOLD = {   # chup tu ma TRUOC thay doi (2026-11-19): warm 60 chu ky r = 15, roi 90 chu ky step_blind, own tinh
    ((10.0, 0.0, 0.0), (1.0, 0.0, 0.0)): {
        1: (10.0, 0.0), 5: (10.0, 0.0), 15: (10.0, 0.0), 30: (9.988888888888889, 0.0), 31: (9.966666666666667, 0.0),
        45: (9.483429648776287, 0.0), 60: (8.983333553443414, 0.0), 90: (7.983333333334482, 0.0)},
    ((10.0, 5.0, 0.0), (1.0, 0.5, 0.0)): {
        1: (10.0, 5.0), 5: (10.0, 5.0), 15: (10.0, 5.0), 30: (9.9900619201, 4.99503096005),
        31: (9.970185760300003, 4.985092880150002), 45: (9.537965431801133, 4.768982715900567),
        60: (9.090665886022526, 4.545332943011263), 90: (8.196238498151196, 4.098119249075598)},
}


@pytest.mark.parametrize("v,u", list(GOLD))
def test_defaults_floor_zero_cap_zero_step_blind_output_unchanged(v, u):
    """Phan NGANG (vx, vy) co dinh theo gia tri vang; phan doc khong ghim (vai khac dang doi hanh vi COAST)."""
    cfg = GuidanceConfig(cam_tilt_up_deg=0.0)
    assert getattr(cfg, "blind_floor_m", 0.0) == 0.0 and getattr(cfg, "blind_v_cap_mps", 0.0) == 0.0
    g = Guidance(cfg)
    un = np.asarray(u, float) / np.linalg.norm(u)
    o = own_at((0.0, 0.0, -ALT), v, 10.0)
    t = 10.0
    for _ in range(60):
        g.step(TrackState(t=t, status=TrackStatus.TRACK, los_ned=tuple(float(c) for c in un), los_rate_ned=(0, 0, 0),
                          range_m=15.0, range_sigma_m=1.0, range_rate_mps=0.0, range_valid=True), o)
        t += DT
    for k in range(1, 91):
        c = g.step_blind(lost_at(t + k * DT), o)
        if k in GOLD[(v, u)]:
            assert (c.vel_ned[0], c.vel_ned[1]) == pytest.approx(GOLD[(v, u)][k], rel=1e-9, abs=1e-9), k
            assert "blind" in c.reason


# ======================================================================= trinh tu THAT: COAST (step) -> step_blind -> step_hover
@pytest.mark.parametrize("name,vfn,limit", [
    ("bay deu 10 m/s", v_const(), C6_STEADY_M),
    ("ham 1.5 m/s^2", v_brake(1.5), C6_GENTLE_M),
    ("ham 3.0 m/s^2", v_brake(3.0), C6_GENTLE_M),
])
def test_real_sequence_coast_blind_hover_min_distance(name, vfn, limit):
    """Mat hinh -> step(COAST) 3 s -> step_blind toi 4 s -> step_hover; blind_floor_m = 8 phai bao ve CA quang COAST (khong chi step_blind)."""
    probe = {}
    d, t_min, _ = simulate_seq(make_cfg(blind_floor_m=FLOOR, blind_grace_model_s=1.5), vfn, probe=probe)
    print("DO trinh tu that %s: d3 min = %.2f m tai %.2f s; d(4 s) = %.2f m; d(8 s) = %.2f m" % (name, d, t_min, probe[4.0], probe[8.0]))
    assert d >= limit, "%s: d3 min = %.2f m tai tau = %.2f s (nguong %.1f m)" % (name, d, t_min, limit)


def test_real_sequence_measure_only_when_target_brakes_hard_8(record_property):
    probe = {}
    d, t_min, _ = simulate_seq(make_cfg(blind_floor_m=FLOOR, blind_grace_model_s=1.5), v_brake(8.0), probe=probe)
    record_property("d3_min_m", round(d, 3))
    record_property("d_4s_m", round(probe[4.0], 3))
    record_property("d_8s_m", round(probe[8.0], 3))
    print("DO trinh tu that phanh 8: d3 min = %.2f m tai %.2f s; d(4 s) = %.2f m; d(8 s) = %.2f m" % (d, t_min, probe[4.0], probe[8.0]))
    assert d > 0.0


def test_real_sequence_short_loss_then_regain_keeps_distance_and_returns_to_normal():
    """Mat hinh 1.2 s (chi COAST) luc muc tieu ham 1.6 m/s^2, roi co hinh lai: d3 >= 6 m va ve che do TRACK binh thuong."""
    d, t_min, reasons = simulate_seq(make_cfg(blind_floor_m=FLOOR, blind_grace_model_s=1.5), v_brake(1.6), regain_at=1.2)
    assert d >= C6_GENTLE_M, "d3 min = %.2f m tai tau = %.2f s" % (d, t_min)
    tail = reasons[-30:]
    assert all("blind" not in r and "coast" not in r and "min_range" not in r for r in tail), tail
    assert all("track" in r for r in tail), tail


# ---- ca bao ve: blind_floor_m = 0 -> step() o COAST giong het hien tai (so vang = GOLD o tren; range_m cua bo bam bi dong bang)
@pytest.mark.parametrize("v,u", list(GOLD))
def test_defaults_step_in_coast_output_unchanged(v, u):
    cfg = GuidanceConfig(cam_tilt_up_deg=0.0)
    g = Guidance(cfg)
    un = np.asarray(u, float) / np.linalg.norm(u)
    o = own_at((0.0, 0.0, -ALT), v, 10.0)
    t = 10.0
    for _ in range(60):
        g.step(TrackState(t=t, status=TrackStatus.TRACK, los_ned=tuple(float(c) for c in un), los_rate_ned=(0, 0, 0),
                          range_m=15.0, range_sigma_m=1.0, range_rate_mps=0.0, range_valid=True), o)
        t += DT
    for k in range(1, 91):
        c = g.step(TrackState(t=t + k * DT, status=TrackStatus.COAST, los_ned=tuple(float(c) for c in un),
                              los_rate_ned=(0, 0, 0), range_m=18.0 + 0.1 * k, range_sigma_m=1.0, range_rate_mps=3.0,
                              range_valid=True), o)
        if k in GOLD[(v, u)]:
            assert (c.vel_ned[0], c.vel_ned[1]) == pytest.approx(GOLD[(v, u)][k], rel=1e-9, abs=1e-9), k


# ---- nguong nhay pos_ned: |dpos - v*dt| > 3 m + 0.5*a_back*dt^2; co chi xoa khi co TRACK hop le
@pytest.mark.parametrize("jump,caught", [(2.0, False), (6.0, True)])
def test_pos_ned_jump_threshold(jump, caught):
    cmds = _run_blind_with_pos_jump(jump)
    after = cmds[2:]
    if caught:
        assert all(is_brake(c) for c in after), [(c.vel_ned, c.reason) for c in after]
    else:
        assert all(not is_brake(c) for c in cmds), [(c.vel_ned, c.reason) for c in cmds]


def test_pos_jump_flag_cleared_by_valid_track():
    cfg = make_cfg(blind_floor_m=FLOOR)
    g = Guidance(cfg)
    v = (10.0, 0.0, 0.0)
    t, x = 10.0, 0.0
    for _ in range(60):
        g.step(track_at(t, (15.0, 0.0, 0.0), v, v), own_at((x, 0.0, -ALT), v, t))
        x += 10.0 * DT
        t += DT
    x += 6.0                                                  # nhay 6 m -> bi bat
    c = g.step_blind(lost_at(t), own_at((x, 0.0, -ALT), v, t))
    assert is_brake(c), c
    for _ in range(15):                                       # thay muc tieu hop le tro lai (vi tri lien tuc)
        x += 10.0 * DT
        t += DT
        g.step(track_at(t, (15.0, 0.0, 0.0), v, v), own_at((x, 0.0, -ALT), v, t))
    x += 10.0 * DT
    t += DT
    c = g.step_blind(lost_at(t), own_at((x, 0.0, -ALT), v, t))
    assert not is_brake(c), (c.vel_ned, c.reason)

# ======================================================================= blind_grace_model_s (phuong an dung hoa cua chu du an)
# Khi tuoi bo nho (t - lan thay hop le cuoi) < blind_grace_model_s: r_hat CHI dung mo hinh "muc tieu giu nguyen van toc nho";
# tu do tro di lay min hai mo hinh (mo hinh ham van tinh tu luc mat). 0 = hanh vi cu. Ap cho moi duong lenh luc khong thay muc tieu.
def test_blind_grace_model_default_and_validation():
    from dtrack.config import AppConfig, GuidanceConfig, validate
    assert getattr(GuidanceConfig(), "blind_grace_model_s", None) == 1.5
    for ok in (0.0, 1.5, 3.0):
        validate(AppConfig(guidance=make_cfg(blind_grace_model_s=ok)))
    for bad in (-0.1, 3.1):
        with pytest.raises(ValueError):
            validate(AppConfig(guidance=make_cfg(blind_grace_model_s=bad)))


def _mem_guidance_grace(decel, grace):
    g = Guidance(make_cfg(blind_floor_m=FLOOR, blind_target_decel_mps2=decel, blind_grace_model_s=grace))
    t_m = 50.0
    g.step(track_at(t_m, (20.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 0.0)), own_at((0.0, 0.0, -ALT), (10.0, 0.0, 0.0), t_m))
    return g, t_m


@pytest.mark.parametrize("decel,grace,dt,own_x,expect_rel_x", [
    (8.0, 1.5, 0.5, 3.0, 22.0),    # tuoi 0.5 < 1.5: chi mo hinh giu van toc: 20 + 10*0.5 - 3 (mo hinh ham cho 21)
    (8.0, 1.5, 1.0, 3.0, 27.0),    # B: 20 + 10 - 3 = 27 (A: 20 + 6 - 3 = 23)
    (3.0, 1.5, 2.0, 5.0, 29.0),    # tuoi 2.0 >= 1.5: min hai mo hinh; A: 20 + (20 - 6) = 34 - 5 (B: 40 - 5 = 35)
    (8.0, 0.0, 0.5, 3.0, 21.0),    # grace 0 = cu: min (A = 21)
])
def test_predicted_rel_respects_grace_age(decel, grace, dt, own_x, expect_rel_x):
    g, t_m = _mem_guidance_grace(decel, grace)
    rel = g.predicted_rel(t_m + dt, own_at((own_x, 0.0, -ALT), (0.0, 0.0, 0.0), t_m + dt))
    assert tuple(rel) == pytest.approx((expect_rel_x, 0.0, 0.0), abs=1e-6)


# ---- C6 theo trinh tu that (grace 1.5): bay deu >= 8, ham 1.5 / 3.0 >= 6, phanh 8 chi do: xem test_real_sequence_* o tren.

# ---- mat hinh NGAN roi co hinh lai, muc tieu BAY DEU 10 m/s
@pytest.mark.parametrize("loss_s", [1.0, 1.5])
def test_short_loss_within_grace_keeps_station_with_steady_target(loss_s):
    """Mat hinh trong grace: khong lui (lenh vx khong giam qua 1 m/s so voi truoc luc mat), sau co hinh lai 2 s va 8 s
    khoang cach toi muc tieu that o 15 +- 3 m."""
    info = {}
    d, t_min, _ = simulate_seq(make_cfg(blind_floor_m=FLOOR, blind_grace_model_s=1.5), v_const(), regain_at=loss_s, info=info)
    da = info["d_after"]
    print("DO mat %.1f s bay deu: sau regain 2 s %.2f m, 4 s %.2f m, 8 s %.2f m; vx_pre %.2f, vx_min_loss %.2f" % (
        loss_s, da[2.0], da[4.0], da[8.0], info["vx_pre"], info["vx_min_loss"]))
    assert info["vx_min_loss"] >= info["vx_pre"] - 1.0, (info["vx_pre"], info["vx_min_loss"])
    assert 12.0 <= da[2.0] <= 18.0 and 12.0 <= da[8.0] <= 18.0, da


@pytest.mark.parametrize("loss_s", [2.0, 3.0])
def test_measure_only_long_loss_beyond_grace_with_steady_target(loss_s, record_property):
    """Mat hinh 2.0 / 3.0 s (vuot grace): CHI DO (han che da biet), khong assert nguong."""
    info = {}
    d, t_min, _ = simulate_seq(make_cfg(blind_floor_m=FLOOR, blind_grace_model_s=1.5), v_const(), regain_at=loss_s, info=info)
    da = info["d_after"]
    for k in (2.0, 4.0, 8.0):
        record_property("d_after_%gs_m" % k, round(da[k], 2))
    print("DO mat %.1f s bay deu (vuot grace): sau regain 2 s %.2f m, 4 s %.2f m, 8 s %.2f m" % (loss_s, da[2.0], da[4.0], da[8.0]))
    assert d > 0.0


# ---- ca bao ve: grace = 0 cho dau ra GIONG HET hien tai (so vang chup tu ma truoc khi them khoa; floor 8, trinh tu that)
GOLD_SEQ = {
    "brake3": (None, v_brake(3.0), 10.679731859496211,
               {10: 9.93223591356489, 45: 3.972008119105549, 89: -7.555138779673435, 100: -6.455138779673497,
                119: -4.555138779673605, 130: -3.4551387796736677, 200: 0.0, 300: 0.0, 599: 0.0}),
    "const_regain1.5": (1.5, v_const(), 15.000020459603405,
                        {10: 9.93223591356489, 45: 3.972008119105549, 89: -2.80198008954413, 100: -1.7635440261577209,
                         119: 0.13878261954345156, 130: 1.3779728823335533, 200: 9.544639548999756, 300: 12.987412990787217,
                         599: 12.16496829267398}),
}


@pytest.mark.parametrize("name", list(GOLD_SEQ))
def test_grace_zero_reproduces_current_command_sequence(name):
    regain, vfn, dmin, gold = GOLD_SEQ[name]
    info = {}
    d, _, _ = simulate_seq(make_cfg0(blind_floor_m=FLOOR), vfn, regain_at=regain, info=info)
    assert d == pytest.approx(dmin, abs=1e-6)
    for k, vx in gold.items():
        assert info["cmds"][k][0] == pytest.approx(vx, abs=1e-6), k