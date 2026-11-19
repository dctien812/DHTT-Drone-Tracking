"""Ca TICH HOP khoi tim lai (design-search.md S-3, S-4): quet khop 60 do/s voi nguon phat hien + bo bam THAT.

Ma THAT: SyntheticDetector (cau hinh realdet cua ho so), SingleTargetTracker, GimbalController, Supervisor
(ho so search_plane_r15), ServoModel/SimGimbalPort (simtools), camera_attitude.
Gia lap: drone DUNG YEN tuyet doi o (0, 0, -30) (khong co mo hinh dong luc); yaw than theo lenh yaw cua supervisor voi
toc do toi da 60 do/s; muc tieu dung yen o 74 m; mat hinh nhan tao [T_BLACK, T_RESUME) (loc ca phat hien co
t_capture trong khoang do) roi co hinh lai.

Day la CA BAO VE: tren ma luc viet (08 do 36/36 voi cung kieu dung) du kien XANH ngay. Ca 'do lech 0,06 s' chi DO, khong assert.
Do lech thoi gian: own dua cho bo bam co t = t - lag nhung tu the camera lay luc t (nhu app.py gan angle(now) cho own.t).
"""
import dataclasses
import math
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DT = 1.0 / 30
T_BLACK = 6.0
T_RESUME = 11.5
WINDOW_S = 8.0           # tu luc co hinh lai: phai len TRACK va dong dot trong chung nay
AZ_DEG = (0.0, 20.0, -20.0)
SEEDS = (0, 1, 2, 3)
DIST_M = 74.0
DELTA_DEG = 85.0           # huong muc tieu luc dau (goc khop ma bo bam bat duoc)


def run_case(seed, az_deg, lag, delta_post=DELTA_DEG):
    """Tra dict(first_track, closed, rtl) tinh bang giay tu T_RESUME (None = khong xay ra trong WINDOW_S)."""
    import numpy as np
    from dtrack.config import _fill, load_profile, profile_dict
    from dtrack.gimbal import camera_attitude
    from dtrack.gimbal_control import GimbalController
    from dtrack.range_estimator import RangeConfig
    from dtrack.supervisor import Supervisor, SupervisorInput
    from dtrack.synthetic import SyntheticDetector
    from dtrack.tracker import SingleTargetTracker, TrackerConfig
    from dtrack.types import OwnState, TrackStatus
    from simtools.servo_model import ServoModel, SimGimbalPort

    cfg = load_profile("search_plane_r15")
    _fill(cfg.synthetic, profile_dict("realdet")["synthetic"], "synthetic")
    cfg.synthetic.seed = seed
    cfg.search.scan_rate_dps = 60.0
    cam = cfg.camera.to_model()
    tracker = SingleTargetTracker(cam, TrackerConfig(range=RangeConfig(target_size_m=cfg.target_shape.span_m)))
    det = SyntheticDetector(cam, cfg.synthetic, cfg.target_shape)
    sup = Supervisor(cfg.supervisor, cfg.guidance, cfg.search, cfg.gimbal)
    port = SimGimbalPort(ServoModel.from_config(cfg.gimbal))
    gc = GimbalController(cfg.gimbal)
    pos = np.array([0.0, 0.0, -30.0])
    az = math.radians(az_deg)
    def tgt_at(delta_deg):
        dep = math.radians(delta_deg - 90.0)
        return pos + DIST_M * np.array([math.cos(dep) * math.cos(az), math.cos(dep) * math.sin(az), math.sin(dep)])
    yaw = 0.0
    first_track = closed = rtl = None
    for k in range(int((T_RESUME + WINDOW_S) / DT) + 1):
        t = k * DT
        tgt = tgt_at(DELTA_DEG if t < T_BLACK else delta_post)
        delta_act = port.angle(t)
        q = (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2))
        qc = tuple(float(c) for c in camera_attitude(q, delta_act))
        cap_own = OwnState(t=t, pos_ned=tuple(pos), vel_ned=(0, 0, 0), q_world_body=qc, armed=True, mode="GUIDED")
        dets = det.process(t, tgt, cap_own, heading=None, target_vel_ned=None)
        dets = [d for d in dets if not (T_BLACK <= d.t_capture < T_RESUME)] if t >= T_BLACK else dets
        if T_BLACK <= t < T_RESUME:
            dets = []
        own_cam = dataclasses.replace(cap_own, t=t - lag)
        own = OwnState(t=t - lag, pos_ned=tuple(pos), vel_ned=(0, 0, 0), q_world_body=q, armed=True, mode="GUIDED")
        tr = tracker.update(dets, own_cam, t)
        out = sup.step(SupervisorInput(t=t, track=tr, own=own, engage=True, heartbeat_age_s=0.1, pose_age_s=0.02,
                                       loop_dt_s=DT, gimbal_delta_rad=delta_act))
        sc = None if out.search is None else out.search.scan_delta_rad
        g = gc.step(t, q, tr, scan_delta_rad=sc)
        port.command(t, g.delta_cmd_rad)
        if out.cmd is not None and out.cmd.yaw_rad is not None:
            e = (out.cmd.yaw_rad - yaw + math.pi) % (2 * math.pi) - math.pi
            yaw += max(-math.radians(60) * DT, min(math.radians(60) * DT, e))
        if out.request_rtl and rtl is None:
            rtl = t - T_RESUME
        if t >= T_RESUME:
            if tr.status == TrackStatus.TRACK and first_track is None:
                first_track = t - T_RESUME
            if out.search is not None and out.search.closed and closed is None:
                closed = t - T_RESUME
        if closed is not None or rtl is not None:
            break
    return {"first_track": first_track, "closed": closed, "rtl": rtl}


def run_grid(lag, delta_post=DELTA_DEG):
    res = [run_case(s, az, lag, delta_post) for az in AZ_DEG for s in SEEDS]
    ok = sum(1 for r in res if r["closed"] is not None and r["closed"] <= WINDOW_S)
    rtls = sum(1 for r in res if r["rtl"] is not None)
    return res, ok, rtls


@pytest.mark.parametrize("lag", [0.0, 0.03])
def test_scan_60dps_real_tracker_reacquires_and_closes_episode(lag, record_property):
    t0 = time.time()
    res, ok, rtls = run_grid(lag)
    closed = sorted(r["closed"] for r in res if r["closed"] is not None)
    record_property("closed_ok_of_12", ok)
    print("lag=%.2f: dong dot trong %.0f s: %d/12; RTL %d; closed(s)=%s; %.1f s chay"
          % (lag, WINDOW_S, ok, rtls, [round(c, 2) for c in closed], time.time() - t0))
    assert rtls == 0, "yeu cau bay ve (RTL) trong cua so %.0f s: %d/12 ca" % (WINDOW_S, rtls)
    assert ok >= 10, "chi %d/12 ca len TRACK va dong dot trong %.0f s (can >= 10)" % (ok, WINDOW_S)


def test_measure_scan_60dps_at_pose_lag_0p06(record_property):
    """CA DO, khong assert nguong: in so ca dong dot / so lan RTL / trung vi thoi diem dong o lech 0,06 s."""
    res, ok, rtls = run_grid(0.06)
    closed = sorted(r["closed"] for r in res if r["closed"] is not None)
    med = closed[len(closed) // 2] if closed else None
    record_property("lag0p06_closed_ok_of_12", ok)
    record_property("lag0p06_rtl_of_12", rtls)
    record_property("lag0p06_closed_median_s", med)
    print("DO lag=0.06: dong dot trong %.0f s: %d/12; RTL %d; trung vi dong %s s" % (WINDOW_S, ok, rtls, med))


def test_scan_needed_target_moved_while_hidden_reacquired_at_lag_0():
    """Ca CHAN dung quet: trong luc mat hinh muc tieu doi huong den goc khop 30 do (cach goc khop luc mat hinh ~55 do, ngoai tam nhin camera);
    sau do dung yen. Neu khop khong quet thi khong bat lai duoc (da thu tren ban sao hong, xem bao cao)."""
    res, ok, rtls = run_grid(0.0, delta_post=30.0)
    print("muc tieu doi huong: dong dot %d/12, RTL %d" % (ok, rtls))
    assert rtls == 0
    assert ok >= 10
