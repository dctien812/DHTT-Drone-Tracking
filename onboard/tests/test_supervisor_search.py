"""Test PHA DO noi khoi tim lai vao Supervisor (.office/design-search.md (a), (d) va S-3/S-4).

Chu ky gia dinh: Supervisor(cfg, gcfg, scfg=None, gimbal_cfg=None); SupervisorInput(..., gimbal_delta_rad=None);
SupervisorOutput.search: Optional[SearchInfo] (ep_id, ep_s, phase, run_s, closed, climb_m, scan_delta_rad, r_hat).
Quy uoc tu chot (thiet ke mo ho):
- search.enabled=False -> out.search is None; SupervisorOutput khong doi (ca bao ve ghim bang hash chuoi dau ra
  ghi tu MA HIEN TAI tren cung dau vao, + RTL ~15,1 s = coast 5,0 s + lost_rtl 10 s);
- SearchInfo.ep_s = giay tu COAST dau (mo dot o chu ky dau khong TRACK); run_s = do dai chuoi TRACK hien tai (0.0 khi
  khong TRACK); closed True dung tai tick TRACK lien tuc >= reacquire_hold_s (1,0 s);
- RTL luc enabled: o ep_s > total_s (20 s), bat ke tracker, dung MOT lan; chua tung thay muc tieu: nhu cu (lost_rtl_s tu engage);
- S-3: pha >= 1 + TRACK chua du hold: lenh = treo (van toc ngang ~ 0 du muc tieu xa 60 m), scan_delta_rad None, yaw giu;
  TRACK rot -> scan_delta_rad lai la so thuc, gan delta hien tai (gimbal_delta_rad dau vao = delta quet cuoi).
Kich ban 30 Hz; muc tieu bay thang phia truoc 25 m (xem trk), drone dung yen o (0, 0, -30).
"""
import hashlib
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.config import GuidanceConfig, SupervisorConfig
from dtrack.supervisor import SupState, Supervisor, SupervisorInput
from dtrack.types import OwnState, TrackState, TrackStatus

GC = GuidanceConfig(cam_tilt_up_deg=0.0)
DT = 1.0 / 30
D = math.radians


def own(t=0.0):
    return OwnState(t=t, pos_ned=(0.0, 0.0, -30.0), vel_ned=(0.0, 0.0, 0.0), q_world_body=(1.0, 0.0, 0.0, 0.0),
                    armed=True, mode="GUIDED")


def trk(status, t, r=25.0):
    if status in (TrackStatus.SEARCH, TrackStatus.LOST):
        return TrackState(t=t, status=status)
    return TrackState(t=t, status=status, los_ned=(1.0, 0.0, 0.0), los_rate_ned=(0.0, 0.0, 0.0),
                      range_m=r, range_sigma_m=1.0, range_rate_mps=0.0, range_valid=True)


def make_sup(enabled=True, search_kw=None, **sup_kw):
    from dtrack.config import GimbalConfig, SearchConfig
    return Supervisor(SupervisorConfig(**sup_kw), GC, SearchConfig(enabled=enabled, **(search_kw or {})),
                      GimbalConfig(enabled=True))


def mk_inp(t, status, r=25.0, delta=None, engage=True, hb=0.1):
    kw = {} if delta is None else {"gimbal_delta_rad": delta}
    return SupervisorInput(t=t, track=trk(status, t, r), own=own(t), engage=engage, heartbeat_age_s=hb,
                           pose_age_s=0.02, loop_dt_s=DT, **kw)


def scenario(t_loss=1.0, coast_s=1.5, windows=(), t_reacq=None):
    """status_fn(t) -> (status, range): TRACK truoc t_loss; sau do COAST coast_s roi LOST; windows = cac cua so TRACK (a, b)
    (r = 60 m); t_reacq: TRACK lien tuc tu moc nay."""
    def f(t):
        if t < t_loss:
            return TrackStatus.TRACK, 25.0
        if t_reacq is not None and t >= t_reacq:
            return TrackStatus.TRACK, 25.0
        for a, b in windows:
            if a <= t < b:
                return TrackStatus.TRACK, 60.0
        if t < t_loss + coast_s:
            return TrackStatus.COAST, 25.0
        return TrackStatus.LOST, 25.0
    return f


def run(sup, fn, t_end, feedback_delta=True, delta0=D(90.0)):
    """Chay 30 Hz tu t=0 toi t_end; tra [(t, out)]. gimbal_delta_rad dau vao (chi cho kich ban bat) = delta quet cuoi."""
    res = []
    delta = delta0
    for k in range(int(round(t_end / DT))):
        t = k * DT
        st, r = fn(t)
        out = sup.step(mk_inp(t, st, r, delta=delta if feedback_delta else None))
        res.append((t, out))
        info = getattr(out, "search", None)
        if info is not None and info.scan_delta_rad is not None:
            delta = info.scan_delta_rad
    return res


def run_disabled_2arg(fn, t_end):
    sup = Supervisor(SupervisorConfig(), GC)
    res = []
    for k in range(int(round(t_end / DT))):
        t = k * DT
        st, r = fn(t)
        res.append((t, sup.step(mk_inp(t, st, r))))
    return res


def rtl_times(res):
    return [t for t, o in res if o.request_rtl]


def sig(out):
    def r(v):
        return None if v is None else round(float(v), 6) + 0.0
    vel = None if out.cmd is None else tuple(r(c) for c in out.cmd.vel_ned)
    yaw = None if out.cmd is None else r(out.cmd.yaw_rad)
    return (out.state.value, out.send, out.request_rtl, out.reason, vel, yaw, out.engaged)


def hspeed(out):
    return math.hypot(out.cmd.vel_ned[0], out.cmd.vel_ned[1])


# =====================================================================
# search.enabled = False : ca bao ve (PASS ngay)
# =====================================================================
GOLDEN_SHA256 = "544bc2b3bf78db6d48cf10f4ef56ca083db6d157ca24fe60fc516863b69f040d"


def test_guard_disabled_sequence_matches_recorded_current_behaviour():
    res = run_disabled_2arg(scenario(), 17.0)
    digest = hashlib.sha256(repr([sig(o) for _, o in res]).encode()).hexdigest()
    assert digest == GOLDEN_SHA256


def test_guard_disabled_rtl_once_at_lost_rtl_s_after_lost_starts():
    res = run_disabled_2arg(scenario(), 25.0)
    ts = rtl_times(res)
    assert len(ts) == 1 and 15.0 < ts[0] < 15.2      # COAST (1,0-5,0 s, ke ca tracker bao LOST) + 10 s


def test_guard_supervisor_states_unchanged_enum():
    assert {s.name for s in SupState} == {"IDLE", "SEARCH", "TRACK", "COAST", "LOST", "ABORT"}


def test_disabled_explicit_scfg_identical_to_default_sequence():
    sup = make_sup(enabled=False)
    res = run(sup, scenario(), 17.0, feedback_delta=False)
    ref = run_disabled_2arg(scenario(), 17.0)
    assert [sig(o) for _, o in res] == [sig(o) for _, o in ref]


def test_disabled_output_search_is_none():
    res = run_disabled_2arg(scenario(), 6.0)
    assert all(o.search is None for _, o in res)


# =====================================================================
# bat: RTL o 20 +- 0,5 s tu COAST dau
# =====================================================================
def test_enabled_rtl_at_20s_after_first_coast_sent_once():
    res = run(make_sup(), scenario(t_loss=1.0), 40.0)
    ts = rtl_times(res)
    assert len(ts) == 1
    assert abs((ts[0] - 1.0) - 20.0) <= 0.5


def test_enabled_does_not_rtl_at_old_lost_rtl_s():
    res = run(make_sup(), scenario(t_loss=1.0), 40.0)
    assert not any(o.request_rtl for t, o in res if t < 20.0)


def test_enabled_rtl_uses_first_coast_not_tracker_lost_time():
    res = run(make_sup(), scenario(t_loss=3.0, coast_s=0.5), 40.0)
    ts = rtl_times(res)
    assert len(ts) == 1 and abs((ts[0] - 3.0) - 20.0) <= 0.5


def test_enabled_rtl_not_repeated_later():
    res = run(make_sup(), scenario(), 60.0)
    assert len(rtl_times(res)) == 1


def test_enabled_never_seen_target_keeps_old_lost_rtl_s_from_engage():
    res = run(make_sup(), lambda t: (TrackStatus.SEARCH, 25.0), 25.0)
    ts = rtl_times(res)
    assert len(ts) == 1 and 10.0 < ts[0] < 10.2
    assert all(o.search is None or o.search.ep_s is None for _, o in res)


def test_single_detection_blips_do_not_move_rtl_mark():
    blips = ((6.0, 6.02), (12.0, 12.02), (18.0, 18.02), (19.5, 19.7))
    res = run(make_sup(), scenario(windows=blips), 40.0)
    ts = rtl_times(res)
    assert len(ts) == 1 and abs((ts[0] - 1.0) - 20.0) <= 0.5


def test_track_blips_below_hold_do_not_move_rtl_mark():
    blips = ((5.0, 5.8), (9.0, 9.9), (14.0, 14.9))
    res = run(make_sup(), scenario(windows=blips), 40.0)
    ts = rtl_times(res)
    assert len(ts) == 1 and abs((ts[0] - 1.0) - 20.0) <= 0.5


def test_rtl_still_requested_when_blinking_track_at_expiry():
    res = run(make_sup(), scenario(windows=((20.8, 21.4),)), 40.0)     # ep_s 19,8..20,4: chop TRACK < hold
    ts = rtl_times(res)
    assert len(ts) == 1 and 21.0 < ts[0] <= 21.5
    out_at = [o for t, o in res if t == ts[0]][0]
    assert out_at.state == SupState.TRACK or out_at.request_rtl      # bat ke trang thai tracker


@pytest.mark.parametrize("t_reacq", [8.0, 18.0])
def test_reacquire_at_least_one_second_before_20s_prevents_rtl(t_reacq):
    res = run(make_sup(), scenario(t_reacq=t_reacq), 40.0)
    assert rtl_times(res) == []


def test_reacquire_closes_episode_after_hold_and_returns_to_normal_tracking():
    res = run(make_sup(), scenario(t_reacq=8.0), 14.0)
    closed_ts = [t for t, o in res if o.search is not None and o.search.closed]
    assert len(closed_ts) == 1
    assert 9.0 - 1e-6 <= closed_ts[0] <= 9.0 + 2 * DT
    last = res[-1][1]
    assert last.state == SupState.TRACK
    assert last.search is None or last.search.ep_s is None


def test_second_loss_opens_new_episode_with_own_clock_and_rtl():
    fn = scenario(t_loss=1.0, coast_s=1.5)
    base = fn

    def two_losses(t):
        if 8.0 <= t < 12.0:
            return TrackStatus.TRACK, 25.0
        if t >= 12.0:
            return (TrackStatus.COAST, 25.0) if t < 13.5 else (TrackStatus.LOST, 25.0)
        return base(t)
    res = run(make_sup(), two_losses, 50.0)
    ids = sorted({o.search.ep_id for _, o in res if o.search is not None and o.search.ep_s is not None})
    assert len(ids) == 2 and ids[1] > ids[0]
    ts = rtl_times(res)
    assert len(ts) == 1 and abs((ts[0] - 12.0) - 20.0) <= 0.5


# =====================================================================
# SearchInfo
# =====================================================================
def test_search_info_has_all_fields():
    import dataclasses
    from dtrack.search import SearchInfo
    names = {f.name for f in dataclasses.fields(SearchInfo)}
    assert {"ep_id", "ep_s", "phase", "run_s", "closed", "climb_m", "scan_delta_rad", "r_hat"} <= names


def test_search_info_values_during_episode():
    res = run(make_sup(), scenario(t_loss=1.0), 10.0)
    by_t = {round(t, 4): o for t, o in res}
    first = by_t[1.0]
    assert first.search is not None and first.search.ep_s == pytest.approx(0.0, abs=DT)
    assert first.search.phase == 0 and first.search.closed is False
    mid = by_t[round(3.0, 4)]
    assert mid.search.ep_s == pytest.approx(2.0, abs=0.05) and mid.search.phase == 0
    p1 = by_t[round(7.0, 4)]
    assert p1.search.ep_s == pytest.approx(6.0, abs=0.05) and p1.search.phase == 1
    assert p1.search.run_s == pytest.approx(0.0, abs=1e-9)
    assert p1.search.climb_m == pytest.approx(0.0, abs=1e-9)
    assert p1.search.ep_id == first.search.ep_id
    assert p1.state == SupState.LOST


SS = {"scan_start_s": 4.01}    # S-16: sat coast_follow_s (4,0) => pha 1 quet ngay, giu dong thoi gian cu cua cac ca duoi


def test_phase0_has_no_scan_and_phase1_scans():
    res = run(make_sup(search_kw=SS), scenario(t_loss=1.0), 10.0)
    for t, o in res:
        if o.search is None or o.search.ep_s is None:
            continue
        if o.search.phase == 0:
            assert o.search.scan_delta_rad is None
        elif o.search.phase == 1 and o.search.ep_s >= SS["scan_start_s"]:     # ep_s 4,0..4,01: chua toi moc
            assert o.search.scan_delta_rad is not None
            assert D(10.0) - 1e-9 <= o.search.scan_delta_rad <= D(110.0) + 1e-9


def test_phase1_command_is_hover_with_swept_yaw():
    res = run(make_sup(search_kw=SS), scenario(t_loss=1.0), 12.0)
    p1 = [o for t, o in res if o.search is not None and o.search.phase == 1]
    assert p1 and all(o.send and o.cmd is not None for o in p1)
    assert all(hspeed(o) < 0.5 for o in p1)
    yaws = [o.cmd.yaw_rad for o in p1]
    assert all(y is not None for y in yaws)
    assert max(yaws) - min(yaws) > D(20.0)


def test_abort_recovery_closes_episode():
    # mat luc 1,0; ABORT 3,0-3,3 (mat HEARTBEAT); hoi phuc ~4,3 s -> SEARCH, _had_target False
    def fn(t):
        return scenario(t_loss=1.0)(t)
    sup = make_sup()
    res = []
    delta = D(90.0)
    for k in range(int(round(40.0 / DT))):
        t = k * DT
        st, r = fn(t)
        hb = 5.0 if 3.0 <= t < 3.3 else 0.1
        out = sup.step(mk_inp(t, st, r, delta=delta, hb=hb))
        res.append((t, out))
    assert any(o.state == SupState.ABORT for _, o in res)
    after = [o for t, o in res if t >= 4.6 and t < 8.0]
    assert all(o.search is None or o.search.ep_s is None for o in after)
    ts = rtl_times(res)
    assert len(ts) == 1
    assert 13.5 < ts[0] < 16.5        # lost_rtl_s tu luc hoi phuc, khong phai moc 21 s cua dot cu


def test_disengage_closes_episode_and_new_one_gets_new_clock():
    sup = make_sup()
    res = []
    delta = D(90.0)
    for k in range(int(round(60.0 / DT))):
        t = k * DT
        engage = not (8.0 <= t < 9.0)
        if t < 1.0:
            st = TrackStatus.TRACK
        elif t < 8.0:
            st = TrackStatus.LOST
        elif t < 10.0:
            st = TrackStatus.TRACK          # tai engage, TRACK 1 s truoc khi mat lai
        elif t < 11.0:
            st = TrackStatus.COAST
        else:
            st = TrackStatus.LOST
        out = sup.step(mk_inp(t, st, 25.0, delta=delta, engage=engage))
        res.append((t, out))
    ts = rtl_times(res)
    assert len(ts) == 1
    assert abs((ts[0] - 10.0) - 20.0) <= 0.5       # dot moi mo luc ~10,0 s


# =====================================================================
# S-3: TRACK chua du hold trong pha >= 1
# =====================================================================
def _blip_run(enabled=True):
    sup = make_sup(enabled=enabled, search_kw=SS if enabled else None)
    return run(sup, scenario(t_loss=1.0, windows=((6.0, 6.9),)), 9.0)


def test_s3_track_below_hold_in_phase1_hovers_not_pursues():
    res = _blip_run()
    blip = [(t, o) for t, o in res if 6.0 <= t < 6.9]
    assert blip
    last = blip[-1][1]
    assert last.state == SupState.TRACK
    assert last.search is not None and last.search.phase == 1
    assert hspeed(last) <= 0.3
    # ca doi chung: khong co tim kiem (enabled=False) thi cung dau vao do duoi muc tieu
    ref = _blip_run(enabled=False)
    ref_last = [o for t, o in ref if 6.0 <= t < 6.9][-1]
    assert hspeed(ref_last) > 1.0


def test_s3_scan_delta_is_none_during_sub_hold_track_and_resumes_after():
    res = _blip_run()
    # 5.0 < t: tai t = 5.0 thi ep_s dung bang 4.0 = coast_follow_s, van la pha 0 (khong quet)
    before = [o for t, o in res if 5.0 < t < 6.0]
    inside = [o for t, o in res if 6.0 <= t < 6.9]
    after = [o for t, o in res if 7.0 <= t < 8.0]
    assert all(o.search.scan_delta_rad is not None for o in before)
    assert all(o.search.scan_delta_rad is None for o in inside)
    assert all(o.search.scan_delta_rad is not None for o in after)
    # quet tiep tu delta hien tai, khong nhay ve diem dau
    last_before = before[-1].search.scan_delta_rad
    first_after = [o for t, o in res if t >= 6.9 and o.search.scan_delta_rad is not None][0].search.scan_delta_rad
    assert abs(first_after - last_before) <= D(15.0)


def test_s3_yaw_held_during_sub_hold_track():
    res = _blip_run()
    before = [o for t, o in res if 5.0 <= t < 6.0][-1]
    inside = [o for t, o in res if 6.0 <= t < 6.9]
    for o in inside:
        d = (o.cmd.yaw_rad - before.cmd.yaw_rad + math.pi) % (2 * math.pi) - math.pi
        assert abs(d) <= D(1.0)


def test_s3_run_s_counts_current_track_streak():
    res = _blip_run()
    inside = [(t, o) for t, o in res if 6.0 <= t < 6.9]
    t_last, o_last = inside[-1]
    assert o_last.search.run_s == pytest.approx(t_last - inside[0][0], abs=2 * DT)
    assert all(o.search.closed is False for _, o in inside)


def test_s3_after_enough_track_hold_control_returns_to_guidance_pursuit():
    sup = make_sup()
    res = run(sup, scenario(t_loss=1.0, windows=((6.0, 20.0),)), 9.0)
    closed = [t for t, o in res if o.search is not None and o.search.closed]
    assert len(closed) == 1 and 7.0 - 1e-6 <= closed[0] <= 7.0 + 2 * DT
    assert hspeed(res[-1][1]) > 1.0          # muc tieu 60 m phia truoc: guidance.step duoi theo


def test_s16_default_scan_start_pha1_holds_gimbal_and_yaw_until_12s():
    """S-16 mac dinh: trong pha 1 truoc scan_start_s (12 s) khong quet khop (scan_delta_rad None) va lenh yaw khong doi; sau moc: quet."""
    res = run(make_sup(), scenario(t_loss=1.0), 20.0)
    ep = [(o.search.ep_s, o) for t, o in res if o.search is not None and o.search.ep_s is not None and o.search.phase == 1]
    pre = [o for e, o in ep if e < 12.0 - 2 * DT]
    post = [o for e, o in ep if e >= 12.0 + 2 * DT]
    assert pre and post
    assert all(o.search.scan_delta_rad is None for o in pre)
    yaws = [o.cmd.yaw_rad for o in pre]
    assert max(yaws) - min(yaws) < D(1.0)
    assert all(o.search.scan_delta_rad is not None for o in post)
