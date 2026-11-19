"""PHA DO: ho so search_plane_r15 voi "gia dinh muc tieu ham" TAT (blind_floor_m = 0, blind_v_cap_mps = 0), cap Supervisor.

Supervisor + Guidance THAT. Muc tieu bay deu 10 m/s theo +x; drone bay cung huong, ban dau cach 15 m va 10 m/s;
van toc drone theo lenh voi tre bac nhat 0,5 s (gia lap FC), 30 Hz. TRACK toi t=6; mat hinh 3 s (COAST 1,5 s roi LOST);
co hinh lai tu t=9. Do khoang cach drone-muc tieu 8 s sau khi co hinh lai (t=17), ky vong 15 +- 3 m.
Ca nay DO tren ho so dung nhu duoc nap (khong ghi de hai khoa): do lai khi hai khoa = 0 de dat nguong.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DT = 1.0 / 30
T_LOSS = 6.0
T_BACK = 9.0
T_MEASURE = T_BACK + 8.0
V_T = 10.0
TAU = 0.5


def run(overrides=None, t_end=T_MEASURE + DT):
    from dtrack.config import load_profile
    from dtrack.supervisor import Supervisor, SupervisorInput
    from dtrack.types import OwnState, TrackState, TrackStatus

    cfg = load_profile("search_plane_r15")
    for k, v in (overrides or {}).items():
        setattr(cfg.guidance, k, v)
    sup = Supervisor(cfg.supervisor, cfg.guidance, cfg.search, cfg.gimbal)
    px, vx = 0.0, V_T
    rows = []
    for k in range(int(round(t_end / DT))):
        t = k * DT
        tx = 15.0 + V_T * t
        r = tx - px
        if t < T_LOSS or t >= T_BACK:
            trk = TrackState(t=t, status=TrackStatus.TRACK, los_ned=(1.0, 0.0, 0.0), los_rate_ned=(0.0, 0.0, 0.0),
                             range_m=r, range_sigma_m=0.5, range_rate_mps=V_T - vx, range_valid=True)
        elif t < T_LOSS + 1.5:
            trk = TrackState(t=t, status=TrackStatus.COAST, los_ned=(1.0, 0.0, 0.0), los_rate_ned=(0.0, 0.0, 0.0),
                             range_m=r, range_rate_mps=0.0, range_valid=True)
        else:
            trk = TrackState(t=t, status=TrackStatus.LOST)
        own = OwnState(t=t, pos_ned=(px, 0.0, -30.0), vel_ned=(vx, 0.0, 0.0), q_world_body=(1.0, 0.0, 0.0, 0.0),
                       armed=True, mode="GUIDED")
        out = sup.step(SupervisorInput(t=t, track=trk, own=own, engage=True, heartbeat_age_s=0.1, pose_age_s=0.02,
                                       loop_dt_s=DT, gimbal_delta_rad=math.radians(90.0)))
        rows.append((t, r, out))
        vc = out.cmd.vel_ned[0] if out.cmd is not None else 0.0
        vx += (vc - vx) * (1.0 - math.exp(-DT / TAU))
        px += vx * DT
    return rows


def test_range_8s_after_reacquire_is_15_pm_3():
    rows = run()
    t, r, _ = rows[-1]
    assert abs(t - T_MEASURE) < DT
    print("khoang cach 8 s sau khi co hinh lai: %.2f m" % r)
    assert 12.0 <= r <= 18.0, "khoang cach %.2f m ngoai 15 +- 3" % r


def test_no_min_range_reason_in_first_4s_of_blind_with_steady_target():
    rows = run()
    bad = [(round(t, 2), o.reason) for t, _, o in rows if T_LOSS <= t < T_LOSS + 3.0 and "min_range" in o.reason]
    # mat hinh keo dai 3 s trong kich ban nay (< 4 s); lenh trong luc do khong duoc lui phong
    bad += [(round(t, 2), o.cmd.reason) for t, _, o in rows
            if T_LOSS <= t < T_LOSS + 3.0 and o.cmd is not None and "min_range" in o.cmd.reason]
    assert not bad, "co min_range trong luc mat hinh: %s" % bad[:3]
