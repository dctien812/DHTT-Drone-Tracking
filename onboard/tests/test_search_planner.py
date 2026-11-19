"""Test PHA DO cho tri_sweep va SearchPlanner (dtrack/search.py, MOI) - .office/design-search.md (a), (c), (e) E6 va S-3.

Chu ky gia dinh: tri_sweep(s, start, lo, hi, first_dir) -> float (s = quang duong da di >= 0, first_dir = +1 / -1);
SearchPlanner(cfg, delta_min_rad, delta_max_rad); begin(t, own, yaw0, delta0, p_stop_ned|None);
step(t, own, phase) -> SearchOutput(vel_ned, yaw_rad, scan_delta_rad, climb_m, reason).
Quy uoc tu chot:
- vel_ned cua planner la bo ba NED; chi vz (vel_ned[2], am = len) co y nghia (vx, vy do guidance.step_hover cua supervisor);
  pha 1 -> vz == 0; pha 2 -> vz <= 0 (leo) hoac 0;
- climb_m trong SearchOutput = do cao da tang luy ke (m);
- yaw_amp_deg = 0 -> yaw_rad == yaw0 (hoac None);
- sau khi KHONG goi step mot luc (supervisor tam ngung vi TRACK, S-3) roi goi lai: quet tiep tu delta cuoi cua planner,
  khong nhay ve diem dau, khong "bat kip" theo dong ho (dt dau tien sau khoang nghi bi kep).
Import dtrack.search ben TRONG ham.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.types import OwnState

DT = 1.0 / 30
D = math.radians
DMIN, DMAX = D(10.0), D(110.0)


def own_at(pos=(0.0, 0.0, -30.0), t=0.0):
    return OwnState(t=t, pos_ned=pos, vel_ned=(0.0, 0.0, 0.0), q_world_body=(1.0, 0.0, 0.0, 0.0),
                    armed=True, mode="GUIDED")


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def mk(**kw):
    from dtrack.search import SearchPlanner
    from dtrack.config import SearchConfig
    cfg = SearchConfig(**kw)
    return SearchPlanner(cfg, DMIN, DMAX)


def run(pl, n, phase=1, t0=0.0, own=None):
    """Goi step n lan, moi lan DT; tra danh sach SearchOutput."""
    outs = []
    for k in range(1, n + 1):
        outs.append(pl.step(t0 + k * DT, own or own_at(), phase))
    return outs


# ---------------- tri_sweep ----------------
def test_tri_sweep_starts_at_start_and_goes_first_dir_up():
    from dtrack.search import tri_sweep
    assert tri_sweep(0.0, 50.0, 10.0, 110.0, +1) == pytest.approx(50.0)
    assert tri_sweep(10.0, 50.0, 10.0, 110.0, +1) == pytest.approx(60.0)


def test_tri_sweep_first_dir_down():
    from dtrack.search import tri_sweep
    assert tri_sweep(10.0, 50.0, 10.0, 110.0, -1) == pytest.approx(40.0)


def test_tri_sweep_reflects_at_hi_and_lo():
    from dtrack.search import tri_sweep
    assert tri_sweep(60.0, 50.0, 10.0, 110.0, +1) == pytest.approx(110.0)    # cham hi
    assert tri_sweep(70.0, 50.0, 10.0, 110.0, +1) == pytest.approx(100.0)    # phan xa
    assert tri_sweep(60.0 + 100.0, 50.0, 10.0, 110.0, +1) == pytest.approx(10.0)  # cham lo
    assert tri_sweep(60.0 + 100.0 + 25.0, 50.0, 10.0, 110.0, +1) == pytest.approx(35.0)
    assert tri_sweep(60.0 + 200.0, 50.0, 10.0, 110.0, +1) == pytest.approx(110.0)  # chu ky 2*(hi-lo)


def test_tri_sweep_reflects_going_down_first():
    from dtrack.search import tri_sweep
    assert tri_sweep(40.0, 50.0, 10.0, 110.0, -1) == pytest.approx(10.0)
    assert tri_sweep(50.0, 50.0, 10.0, 110.0, -1) == pytest.approx(20.0)


def test_tri_sweep_stays_in_bounds_and_is_continuous():
    from dtrack.search import tri_sweep
    prev = tri_sweep(0.0, 30.0, 10.0, 110.0, +1)
    for k in range(1, 3000):
        s = k * 0.37
        v = tri_sweep(s, 30.0, 10.0, 110.0, +1)
        assert 10.0 - 1e-9 <= v <= 110.0 + 1e-9
        assert abs(v - prev) <= 0.37 + 1e-9          # lipschitz 1 theo quang duong
        prev = v


# ---------------- SearchOutput ----------------
def test_search_output_has_spec_fields():
    import dataclasses
    from dtrack.search import SearchOutput
    names = {f.name for f in dataclasses.fields(SearchOutput)}
    assert {"vel_ned", "yaw_rad", "scan_delta_rad", "climb_m", "reason"} <= names


# ---------------- quet khop ----------------
def test_scan_starts_from_delta0_and_goes_to_hi_first():
    pl = mk()
    pl.begin(0.0, own_at(), 0.5, D(60.0), None)
    outs = run(pl, 60)
    assert abs(outs[0].scan_delta_rad - D(60.0)) <= D(60.0) * DT * 1.5 + 1e-9
    assert outs[10].scan_delta_rad > outs[0].scan_delta_rad > D(60.0) - 1e-9    # tang truoc (ve hi)
    assert max(o.scan_delta_rad for o in outs[:25]) > D(105.0)                  # toi hi truoc khi xuong lo


@pytest.mark.parametrize("rate", [60.0, 30.0])
def test_scan_angle_within_limits_and_rate(rate):
    pl = mk(scan_rate_dps=rate)
    pl.begin(0.0, own_at(), 0.5, D(60.0), None)
    outs = run(pl, 30 * 12)
    ds = [o.scan_delta_rad for o in outs]
    assert all(D(10.0) - 1e-9 <= d <= D(110.0) + 1e-9 for d in ds)
    prev = D(60.0)
    for d in ds:
        assert abs(d - prev) <= D(rate) * DT * (1 + 1e-6) + 1e-9
        prev = d
    assert max(ds) >= D(110.0) - D(rate) * DT - 1e-9           # thuc su quet het dai
    assert min(ds) <= D(10.0) + D(rate) * DT + 1e-9


def test_scan_respects_narrower_config_range():
    pl = mk(scan_lo_deg=20.0, scan_hi_deg=80.0, climb_scan_lo_deg=40.0)
    pl.begin(0.0, own_at(), 0.5, D(50.0), None)
    ds = [o.scan_delta_rad for o in run(pl, 30 * 10)]
    assert min(ds) >= D(20.0) - 1e-9 and max(ds) <= D(80.0) + 1e-9
    assert max(ds) >= D(80.0) - D(60.0) * DT - 1e-9 and min(ds) <= D(20.0) + D(60.0) * DT + 1e-9


def test_phase1_has_no_vertical_command():
    pl = mk(climb_m=5.0)
    pl.begin(0.0, own_at(), 0.5, D(60.0), (100.0, 0.0, -30.0))
    for o in run(pl, 300, phase=1):
        assert abs(o.vel_ned[2]) < 1e-9


# ---------------- quet yaw ----------------
def test_yaw_sweeps_around_yaw0_within_amplitude_and_rate():
    yaw0 = 0.5
    pl = mk()
    pl.begin(0.0, own_at(), yaw0, D(60.0), None)
    outs = run(pl, 30 * 20)
    devs = [wrap(o.yaw_rad - yaw0) for o in outs]
    assert all(abs(d) <= D(45.0) + 1e-6 for d in devs)
    assert max(devs) >= D(43.0) and min(devs) <= -D(43.0)           # quet ca hai phia
    assert devs[10] > 0.0                                            # bat dau ve phia +
    prev = 0.0
    for d in devs:
        assert abs(d - prev) <= D(20.0) * DT * (1 + 1e-6) + 1e-9
        prev = d


def test_yaw_amplitude_zero_means_no_yaw_sweep():
    yaw0 = 0.5
    pl = mk(yaw_amp_deg=0.0)
    pl.begin(0.0, own_at(), yaw0, D(60.0), None)
    for o in run(pl, 300):
        assert o.yaw_rad is None or abs(wrap(o.yaw_rad - yaw0)) < 1e-9
    # khop van quet
    pl.begin(0.0, own_at(), yaw0, D(60.0), None)
    ds = [o.scan_delta_rad for o in run(pl, 60)]
    assert max(ds) - min(ds) > D(20.0)


def test_yaw_rate_limit_from_config():
    pl = mk(yaw_rate_dps=10.0, yaw_amp_deg=30.0)
    pl.begin(0.0, own_at(), 0.0, D(60.0), None)
    prev = 0.0
    devs = []
    for o in run(pl, 30 * 20):
        d = wrap(o.yaw_rad)
        assert abs(d - prev) <= D(10.0) * DT * (1 + 1e-6) + 1e-9
        prev = d
        devs.append(d)
    assert max(abs(d) for d in devs) <= D(30.0) + 1e-6


# ---------------- pha 2: leo ----------------
def _simulate_climb(climb_m, p_stop, gain=1.0, lag_s=0.0, own_xy=(0.0, 0.0), seconds=30.0, **kw):
    """Drone ly tuong (hoac tre + vot gain) theo vz cua planner; tra (tang_do_cao_toi_da, tang_cuoi, ds_outputs)."""
    pl = mk(climb_m=climb_m, **kw)
    z0 = -30.0
    z, vz_act = z0, 0.0
    pl.begin(0.0, own_at((own_xy[0], own_xy[1], z)), 0.0, D(100.0), p_stop)
    outs, gains = [], []
    for k in range(1, int(seconds / DT) + 1):
        t = k * DT
        o = pl.step(t, own_at((own_xy[0], own_xy[1], z), t), 2)
        outs.append(o)
        cmd = gain * o.vel_ned[2]
        if lag_s > 0:
            vz_act += (cmd - vz_act) * min(1.0, DT / lag_s)
        else:
            vz_act = cmd
        z += vz_act * DT
        gains.append(z0 - z)
    return max(gains), gains[-1], outs


def test_climb_reaches_target_and_never_exceeds_it_ideal_drone():
    mx, fin, outs = _simulate_climb(6.0, (100.0, 0.0, -30.0))
    assert fin >= 6.0 - 0.5            # dung khi con <= 0,25 m
    assert mx <= 6.0 + 1e-6
    assert max(o.climb_m for o in outs) <= 6.0 + 1e-6
    assert abs(outs[-1].climb_m - fin) <= 0.2


def test_climb_within_climb_m_plus_one_even_with_overshoot_and_lag():
    mx, fin, outs = _simulate_climb(6.0, (100.0, 0.0, -30.0), gain=1.3, lag_s=0.5)
    assert mx <= 6.0 + 1.0
    assert fin >= 3.0                  # co leo that
    assert max(o.climb_m for o in outs) <= 6.0 + 1.0


def test_climb_speed_not_above_climb_rate_and_never_down():
    _, _, outs = _simulate_climb(6.0, (100.0, 0.0, -30.0), climb_rate_mps=2.0)
    ups = [-o.vel_ned[2] for o in outs]
    assert max(ups) > 0.5              # co lenh len
    assert max(ups) <= 2.0 + 1e-9
    assert min(ups) >= -1e-9           # khong co lenh xuong


def test_climb_speed_limit_follows_config():
    _, _, outs = _simulate_climb(6.0, (100.0, 0.0, -30.0), climb_rate_mps=1.0)
    assert max(-o.vel_ned[2] for o in outs) <= 1.0 + 1e-9


def test_no_climb_without_p_stop():
    _, fin, outs = _simulate_climb(6.0, None)
    assert fin == pytest.approx(0.0, abs=1e-9)
    assert all(abs(o.vel_ned[2]) < 1e-9 for o in outs)


@pytest.mark.parametrize("px", [0.0, 5.0, 7.9])
def test_no_climb_when_p_stop_closer_than_8m_horizontally(px):
    _, fin, outs = _simulate_climb(6.0, (px, 0.0, -30.0))
    assert fin == pytest.approx(0.0, abs=1e-9)
    assert all(abs(o.vel_ned[2]) < 1e-9 for o in outs)


def test_no_climb_when_p_stop_close_horizontally_even_if_far_in_altitude():
    """chi tinh theo phuong ngang: (3, 4) cach 5 m ngang, cao hon 100 m van khong leo."""
    _, fin, _ = _simulate_climb(6.0, (3.0, 4.0, -130.0))
    assert fin == pytest.approx(0.0, abs=1e-9)


def test_climbs_when_p_stop_beyond_8m_horizontally():
    _, fin, _ = _simulate_climb(6.0, (8.5, 0.0, -30.0))
    assert fin > 3.0


def test_climb_m_zero_never_commands_up():
    mx, fin, outs = _simulate_climb(0.0, (100.0, 0.0, -30.0))
    assert fin == pytest.approx(0.0, abs=1e-9)
    assert all(o.vel_ned[2] >= -1e-9 for o in outs)
    assert all(o.climb_m == pytest.approx(0.0, abs=1e-9) for o in outs)


def test_phase2_scans_low_band_from_climb_scan_lo():
    pl = mk(climb_m=6.0, climb_scan_lo_deg=70.0)
    pl.begin(0.0, own_at(), 0.0, D(100.0), (100.0, 0.0, -30.0))
    ds = [o.scan_delta_rad for o in run(pl, 30 * 12, phase=2)]
    assert min(ds) >= D(70.0) - 1e-9 and max(ds) <= D(110.0) + 1e-9
    assert min(ds) <= D(70.0) + D(60.0) * DT + 1e-9 and max(ds) >= D(110.0) - D(60.0) * DT - 1e-9


def test_phase1_to_phase2_scan_is_continuous_and_enters_low_band():
    pl = mk(climb_m=6.0, climb_scan_lo_deg=70.0)
    pl.begin(0.0, own_at(), 0.0, D(20.0), (100.0, 0.0, -30.0))
    p1 = run(pl, 30, phase=1)                         # 1 s: tu 20 do len khoang 80
    # gui lai dung dau 20 do thap hon dai 70: chuyen pha khi dang o nhanh thap (cho ca hai kha nang)
    p2 = run(pl, 30 * 6, phase=2, t0=30 * DT)
    seq = [o.scan_delta_rad for o in p1 + p2]
    for a, b in zip(seq, seq[1:]):
        assert abs(b - a) <= D(60.0) * DT * (1 + 1e-6) + 1e-9      # khong nhay
    tail = [o.scan_delta_rad for o in p2[30 * 3:]]               # sau 3 s o pha 2
    assert min(tail) >= D(70.0) - 1e-9 and max(tail) <= D(110.0) + 1e-9


# ---------------- S-3: tam ngung quet roi quet lai ----------------
def test_resume_after_pause_continues_from_current_delta_not_from_start():
    pl = mk()
    delta0 = D(20.0)
    pl.begin(0.0, own_at(), 0.0, delta0, None)
    before = run(pl, 30)[-1].scan_delta_rad                # ~1 s: khoang 80 do
    assert before > D(70.0)
    t_resume = 30 * DT + 0.7                               # nghi 0,7 s (supervisor khong goi step)
    after = pl.step(t_resume, own_at(), 1).scan_delta_rad
    assert abs(after - before) <= D(15.0)                  # khong nhay ve delta0 (cach >= 60 do), khong bat kip dong ho (42 do)
    assert abs(after - delta0) > D(40.0)


def test_resume_after_pause_keeps_sweeping_in_limits():
    pl = mk()
    pl.begin(0.0, own_at(), 0.0, D(20.0), None)
    run(pl, 30)
    outs = run(pl, 30 * 6, t0=30 * DT + 0.7)
    ds = [o.scan_delta_rad for o in outs]
    assert all(D(10.0) - 1e-9 <= d <= D(110.0) + 1e-9 for d in ds)
    assert max(ds) - min(ds) > D(40.0)                     # van quet


def test_begin_starts_from_given_delta_each_time():
    pl = mk()
    for d0 in (D(30.0), D(95.0)):
        pl.begin(0.0, own_at(), 0.0, d0, None)
        first = pl.step(DT, own_at(), 1).scan_delta_rad
        assert abs(first - d0) <= D(60.0) * DT * 1.5 + 1e-9
