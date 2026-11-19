"""PHA DO: lien tuc cua lenh yaw / vz o moi buoc chuyen trong mot dot tim lai, va r_hat het han (T-yaw, T-rhat).

Supervisor + Guidance THAT, ho so search_plane_r15 (khop bat), drone dung yen o (0, 0, -30), 30 Hz; than may quay theo
lenh yaw voi toc do toi da 60 do/s (de supervisor/guidance doc yaw_own that). Mat hinh: TRACK (25 m) toi t=1,
roi COAST 1,5 s, roi LOST. Pha 1 bat dau o ep_s > coast_follow_s (4 s) -> t > 5.
Moc chuyen (kich ban A, bo nho con han): cua so TRACK ngan 6,0-6,4 s (< 1 s hold, tam ngung quet), TRACK lien tuc tu 7,5 s
(dong dot 8,5 s), roi bam thuong toi 11 s. Kich ban B (bo nho het han): TRACK lien tuc tu 11,0 s (dong dot 12,0 s).
Gioi han: |d yaw| moi chu ky <= yaw_rate_max_dps * dt + 0,5 do; |d vz| <= a_max_z * dt + 1e-6.
"""
import dataclasses
import functools
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DT = 1.0 / 30
YAW_TOL_DEG = 0.5
T_END = 13.0


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def status_fn(kind):
    from dtrack.types import TrackStatus

    def f(t):
        if t < 1.0:
            return TrackStatus.TRACK, 25.0
        if kind == "A":
            if 6.0 <= t < 6.4:
                return TrackStatus.TRACK, 60.0
            if t >= 7.5:
                return TrackStatus.TRACK, 60.0
        else:
            if t >= 11.0:
                return TrackStatus.TRACK, 60.0
        if t < 2.5:
            return TrackStatus.COAST, 25.0
        return TrackStatus.LOST, 25.0
    return f


@functools.lru_cache(maxsize=None)
def run_trip(kind="A", climb_m=0.0, t_end=13.0):
    """Tra tuple [(t, out, yaw_cmd, vz_cmd)] cho ca chuyen."""
    from dtrack.config import load_profile
    from dtrack.guidance import yaw_from_quat
    from dtrack.supervisor import Supervisor, SupervisorInput
    from dtrack.types import OwnState, TrackState, TrackStatus

    cfg = load_profile("search_plane_r15")
    cfg.search.climb_m = climb_m
    cfg.search.climb_start_s = 6.0
    sup = Supervisor(cfg.supervisor, cfg.guidance, cfg.search, cfg.gimbal)
    fn = status_fn(kind)
    yaw = 0.0
    delta = math.radians(85.0)
    rows = []
    for k in range(int(round(t_end / DT))):
        t = k * DT
        st, r = fn(t)
        if st in (TrackStatus.SEARCH, TrackStatus.LOST):
            trk = TrackState(t=t, status=st)
        else:
            trk = TrackState(t=t, status=st, los_ned=(1.0, 0.0, 0.0), los_rate_ned=(0.0, 0.0, 0.0), range_m=r,
                             range_sigma_m=1.0, range_rate_mps=0.0, range_valid=True)
        own = OwnState(t=t, pos_ned=(0.0, 0.0, -30.0), vel_ned=(0.0, 0.0, 0.0),
                       q_world_body=(math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)), armed=True, mode="GUIDED")
        out = sup.step(SupervisorInput(t=t, track=trk, own=own, engage=True, heartbeat_age_s=0.1, pose_age_s=0.02,
                                       loop_dt_s=DT, gimbal_delta_rad=delta))
        if out.search is not None and out.search.scan_delta_rad is not None:
            delta = out.search.scan_delta_rad
        yc = out.cmd.yaw_rad if out.cmd is not None else None
        vz = out.cmd.vel_ned[2] if out.cmd is not None else None
        if yc is not None:
            e = wrap(yc - yaw)
            yaw = wrap(yaw + max(-math.radians(60) * DT, min(math.radians(60) * DT, e)))
        rows.append((t, out, yc, vz))
    return tuple(rows)


def max_yaw_step_deg(rows, t_lo, t_hi):
    """(buoc yaw lon nhat [do], t) giua cac chu ky lien tiep co t trong [t_lo, t_hi]."""
    best = (0.0, None)
    for (t0, _, y0, _), (t1, _, y1, _) in zip(rows, rows[1:]):
        if y0 is None or y1 is None or not (t_lo <= t1 <= t_hi):
            continue
        d = abs(math.degrees(wrap(y1 - y0)))
        if d > best[0]:
            best = (d, t1)
    return best


def yaw_limit_deg():
    from dtrack.config import GuidanceConfig
    return GuidanceConfig().yaw_rate_max_dps * DT + YAW_TOL_DEG


def closing_t(rows):
    ts = [t for t, o, _, _ in rows if o.search is not None and o.search.closed]
    assert len(ts) == 1, "kich ban phai co dung mot tick dong dot, co %s" % ts
    return ts[0]


def check_yaw(rows, lo, hi, what):
    d, at = max_yaw_step_deg(rows, lo, hi)
    assert d <= yaw_limit_deg(), "%s: yaw lenh nhay %.2f do trong 1 chu ky tai t=%s (gioi han %.2f do)" % (
        what, d, at, yaw_limit_deg())


# ---------------- T-yaw ----------------
@pytest.mark.parametrize("kind", ["A", "B"])
def test_yaw_continuous_when_entering_phase1(kind):
    rows = run_trip(kind)
    t_enter = next(t for t, o, _, _ in rows if o.search is not None and o.search.phase == 1)
    check_yaw(rows, t_enter - 0.3, t_enter + 0.5, "vao pha 1")


def test_yaw_continuous_when_scan_paused_for_short_track():
    rows = run_trip("A")
    check_yaw(rows, 5.9, 7.4, "tam ngung quet vi TRACK < 1 s va quet lai")


@pytest.mark.parametrize("kind", ["A", "B"])
def test_yaw_continuous_when_episode_closes(kind):
    rows = run_trip(kind)
    tc = closing_t(rows)
    # truoc dong dot yaw phai khac 0 (neu khong ca nay khong chung minh gi)
    yaw_before = next(y for t, _, y, _ in rows if abs(t - (tc - DT)) < 1e-6)
    assert abs(math.degrees(yaw_before)) > 5.0, "dat gia: yaw quet luc dong dot phai > 5 do, la %.2f" % math.degrees(yaw_before)
    check_yaw(rows, tc - 0.3, tc + 0.5, "dong dot (t=%.2f)" % tc)


@pytest.mark.parametrize("kind", ["A", "B"])
def test_yaw_continuous_through_whole_trip(kind):
    rows = run_trip(kind)
    check_yaw(rows, 0.0, 13.0, "ca chuyen")


def test_vz_no_jump_when_episode_closes_climb_off():
    from dtrack.config import GuidanceConfig
    rows = run_trip("A")
    tc = closing_t(rows)
    lim = GuidanceConfig().a_max_z_mps2 * DT + 1e-6
    for (t0, _, _, v0), (t1, _, _, v1) in zip(rows, rows[1:]):
        if tc - 0.3 <= t1 <= tc + 0.5:
            assert abs(v1 - v0) <= lim, "vz nhay %.3f m/s trong 1 chu ky tai t=%.2f (gioi han %.3f)" % (v1 - v0, t1, lim)


def test_vz_no_jump_through_trip_with_climb_on_extra():
    """Phan 'Nho' cua 08: pha leo ghi de vz truc tiep, bo qua gioi han gia toc (0 -> -2 m/s trong mot chu ky)."""
    from dtrack.config import GuidanceConfig
    rows = run_trip("A", climb_m=10.0)
    assert min(v for _, _, _, v in rows) < -1.0, "dat gia: pha leo phai xuat hien (vz < -1 m/s)"
    lim = GuidanceConfig().a_max_z_mps2 * DT + 1e-6
    worst = max((abs(v1 - v0), t1) for (t0, _, _, v0), (t1, _, _, v1) in zip(rows, rows[1:]))
    assert worst[0] <= lim, "vz nhay %.3f m/s trong 1 chu ky tai t=%.2f (gioi han %.3f)" % (worst[0], worst[1], lim)


# ---------------- T-rhat ----------------
def test_r_hat_is_none_when_memory_expired_inside_episode():
    from dtrack.config import GuidanceConfig
    mem_max = GuidanceConfig().blind_mem_max_s
    rows = run_trip("B")
    t_last_track = 1.0 - DT      # tick TRACK cuoi truoc khi mat hinh
    expired = [(t, o) for t, o, _, _ in rows
               if t - t_last_track > mem_max + 0.1 and o.search is not None and o.search.ep_s is not None
               and not o.search.closed and o.search.run_s == 0.0]
    assert expired, "dat gia: phai co chu ky trong dot sau khi bo nho het han"
    stale = [(round(t, 2), o.search.r_hat) for t, o in expired if o.search.r_hat is not None]
    assert not stale, "r_hat con so cu sau khi bo nho het han: %s ... (%d chu ky)" % (stale[:3], len(stale))


def test_r_hat_is_set_while_memory_valid_guard():
    rows = run_trip("B")
    live = [o.search.r_hat for t, o, _, _ in rows if 5.5 < t < 7.0 and o.search is not None]
    assert live and all(r is not None and r > 0 for r in live)


def test_r_hat_is_none_outside_episode():
    rows = run_trip("A")
    tc = closing_t(rows)
    after = [o.search.r_hat for t, o, _, _ in rows if t > tc + DT / 2]
    assert after and all(r is None for r in after)
