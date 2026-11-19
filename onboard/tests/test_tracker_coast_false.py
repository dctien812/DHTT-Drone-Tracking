"""Pha do (TDD) cho hai loi cua SingleTargetTracker:
(A) phat hien gia lot vao bo bam khi COAST (cong d2 phinh rong, khong xet co bbox);
(C) bbox bi cat o mep khung sinh toc do LOS gia (tam do chay cham bang nua tam that).
Cung ca bao ve G1..G4 (phai pass ca truoc va sau khi sua).
Chi dung API cong khai: SingleTargetTracker.update -> TrackState.
"""
import math

import numpy as np
import pytest

from dtrack.config import make_camera
from dtrack.geometry import project_ned_point
from dtrack.gimbal import camera_attitude
from dtrack.range_estimator import RangeConfig
from dtrack.synthetic import SyntheticConfig, SyntheticDetector
from dtrack.tracker import SingleTargetTracker, TrackerConfig
from dtrack.types import Detection, OwnState, TrackStatus

CAM = make_camera(0.0, 1739.0, None, 1456, 1088)
DT = 1.0 / 30.0
LAT = 2 * DT


def _tracker(cam=CAM):
    return SingleTargetTracker(cam, TrackerConfig(range=RangeConfig(target_size_m=2.16)))


def _q(delta_rad=math.radians(90.0)):
    return tuple(float(c) for c in camera_attitude((1.0, 0.0, 0.0, 0.0), delta_rad))


def _own(t, q):
    return OwnState(t=t, pos_ned=(0, 0, 0), vel_ned=(0, 0, 0), q_world_body=q,
                    armed=True, mode='GUIDED')


def _elev_deg(st):
    return math.degrees(math.asin(-st.los_ned[2]))


def _run(dets, t_end, lat=LAT, q_of_t=lambda t: _q(), cam=CAM):
    """Mo phong khung 30 Hz; moi phat hien toi tracker sau `lat` giay. Tra list (t, TrackState)."""
    trk = _tracker(cam)
    pend = sorted(dets, key=lambda d: d.t_capture)
    out = []
    j = 0
    while j * DT <= t_end + 1e-9:
        t = j * DT
        j += 1
        now = [d for d in pend if d.t_capture + lat <= t + 1e-9]
        pend = [d for d in pend if d.t_capture + lat > t + 1e-9]
        out.append((t, trk.update(now, _own(t, q_of_t(t)), t)))
    return out


def _hits(t0, t1, cx=728.0, cy=1000.0, w=190.0, h=88.0, conf=0.85):
    n = int(round((t1 - t0) / DT))
    return [Detection(t_capture=t0 + k * DT, cx=cx, cy=cy, w=w, h=h, conf=conf) for k in range(n + 1)]


# ---------------------------------------------------------------- (A)
FALSE_DETS = [
    Detection(t_capture=4.033, cx=893.0, cy=253.0, w=12.0, h=23.0, conf=0.35),
    Detection(t_capture=4.167, cx=771.0, cy=177.0, w=21.0, h=15.0, conf=0.65),
]


@pytest.fixture(scope='module')
def coast_pair():
    base = _hits(0.0, 3.0)
    with_false = _run(base + FALSE_DETS, 7.0)
    without = _run(base, 7.0)
    return with_false, without


def test_A_false_pair_does_not_shift_elev_los(coast_pair):
    a, b = coast_pair
    diffs = [(t, abs(_elev_deg(s) - _elev_deg(s0))) for (t, s), (_, s0) in zip(a, b)
             if 4.033 <= t <= 7.033 and s.los_ned and s0.los_ned]
    assert diffs, 'khong co mau so sanh'
    tmax, dmax = max(diffs, key=lambda x: x[1])
    assert dmax <= 1.0, 'max |d elev_los| = %.2f deg tai t=%.3f (nguong 1.0)' % (dmax, tmax)


def test_A_false_pair_does_not_switch_to_track(coast_pair):
    a, _ = coast_pair
    tr = [t for t, s in a if t > 3.5 and s.status == TrackStatus.TRACK]
    assert not tr, 'chuyen TRACK do phat hien gia, lan dau luc t=%.3f' % tr[0]


def test_A_false_pair_does_not_change_range(coast_pair):
    a, b = coast_pair
    worst = 0.0
    for (t, s), (_, s0) in zip(a, b):
        if t < 4.033:
            continue
        if s.range_m is not None and s0.range_m is not None:
            worst = max(worst, abs(s.range_m - s0.range_m))
    assert worst <= 0.5, 'max |d range| = %.1f m (nguong 0.5)' % worst


# ---------------------------------------------------------------- (C)
R_TGT = 19.4
EL0 = math.radians(-15.5)
TGT = (R_TGT * math.cos(EL0), 0.0, -R_TGT * math.sin(EL0))
RATE = 0.233


def _delta(t):
    return math.radians(92.4) - RATE * max(0.0, t - 3.0)


def _clip_scene(clip):
    """Muc tieu dung yen, khop gat quay -> muc tieu truot xuong mep duoi. Tra (states, t_clip_dau)."""
    clipper = SyntheticDetector(CAM, SyntheticConfig(clip_to_frame=True))
    dets, first_clipped = [], None
    for j in range(200):
        t = j * DT
        px = project_ned_point(CAM, _q(_delta(t)), (0, 0, 0), TGT)
        if px is None:
            continue
        box = clipper._clip_box(px[0], px[1], 190.0, 85.0) if clip else (px[0], px[1], 190.0, 85.0)
        if box is None:
            continue
        if clip and first_clipped is None and abs(box[1] - px[1]) > 1e-6:
            first_clipped = t
        dets.append(Detection(t_capture=t, cx=box[0], cy=box[1], w=box[2], h=box[3], conf=0.9))
    states = _run(dets, 199 * DT, q_of_t=lambda t: _q(_delta(t)))
    _clip_scene.t_last = dets[-1].t_capture + LAT
    return states, first_clipped


def _vz_and_el(st):
    u = np.array(st.los_ned)
    w = np.array(st.los_rate_ned)
    return R_TGT * float(np.cross(w, u)[2]), _elev_deg(st)


@pytest.fixture(scope='module')
def clipped():
    states, first = _clip_scene(True)
    assert first is not None, 'dung canh khong co khung nao bi cat'
    return states, first


def test_C_clipped_bbox_no_fake_vertical_velocity(clipped):
    states, first = clipped
    vals = [(t, abs(_vz_and_el(s)[0])) for t, s in states
            if t >= first + LAT and s.status == TrackStatus.TRACK]
    assert vals
    tmax, vmax = max(vals, key=lambda x: x[1])
    assert vmax <= 0.2, 'max |r*(w x u)_z| = %.2f m/s tai t=%.3f (nguong 0.2)' % (vmax, tmax)


def test_C_clipped_bbox_elev_matches_truth(clipped):
    states, first = clipped
    vals = [(t, abs(_vz_and_el(s)[1] - math.degrees(EL0))) for t, s in states
            if t >= first + LAT and s.status == TrackStatus.TRACK]
    assert vals
    tmax, emax = max(vals, key=lambda x: x[1])
    assert emax <= 0.3, 'max |elev - that| = %.2f deg tai t=%.3f (nguong 0.3)' % (emax, tmax)


def test_C_control_unclipped_bbox_has_no_fake_velocity():
    states, _ = _clip_scene(False)
    vals = [abs(_vz_and_el(s)[0]) for t, s in states if t >= 3.2 and s.status == TrackStatus.TRACK]
    assert vals and max(vals) <= 0.2


# ---------------------------------------------------------------- G (bao ve)
def _reacq_dets(scale, sizes=((188.0, 52.0), (189.0, 72.0)), t_first=4.5):
    dets = _hits(0.0, 3.0)
    for k, (w, h) in enumerate(sizes):
        dets.append(Detection(t_capture=t_first + k * DT, cx=730.0 + k, cy=1000.0 + k,
                              w=w * scale, h=h * scale, conf=0.8))
    return dets


def _first_track_after(states, t0):
    for t, s in states:
        if t > t0 and s.status == TrackStatus.TRACK:
            return t
    return None


def test_G1_true_reacquire_after_coast_with_consistent_size():
    st = _run(_reacq_dets(1.0), 5.2)
    t_trk = _first_track_after(st, 4.5)
    assert t_trk is not None, 'khong bat lai duoc'
    assert t_trk <= 4.5 + DT + LAT + 2 * DT + 1e-9, 'bat lai qua cham: %.3f' % t_trk


@pytest.mark.parametrize('k', [0.6, 1.6])
def test_G2_true_reacquire_with_moderate_size_change(k):
    sizes = ((190.0, 88.0), (190.0, 88.0))
    st = _run(_reacq_dets(k, sizes), 5.2)
    assert _first_track_after(st, 4.5) is not None, 'bat lai that voi co bbox x%.1f bi chan' % k


def test_G3_edge_clipped_bbox_keeps_tracking_and_updates_position(clipped):
    states, first = clipped
    after = [(t, s) for t, s in states if first + LAT <= t <= _clip_scene.t_last and s.los_ned]
    assert after
    assert all(s.status == TrackStatus.TRACK for t, s in after), 'roi COAST/LOST khi cham mep'
    t, s = after[-1]
    assert s.age_s <= 0.25, 'vi tri goc khong duoc cap nhat, age=%.3f' % s.age_s
    assert abs(_elev_deg(s) - math.degrees(EL0)) <= 2.0


# GHI CHU: G4 la "rao chan" (guard), KHONG tinh la bang chung: chua dung duoc canh nao lam no fail
# tren ma that (chi fail tren ban sao bi pha co chu y, va ban pha do chi la mo phong).
@pytest.mark.parametrize('w,h', [(12.0, 23.0), (190.0, 88.0), (500.0, 400.0)])
def test_G4_initial_acquire_not_blocked_by_size_gate(w, h):
    st = _run(_hits(0.0, 0.2, w=w, h=h), 0.5)
    assert any(s.status == TrackStatus.TRACK for _, s in st), 'khoi tao ban dau bi chan'



def test_G3_persistent_edge_clipped_bbox_keeps_track_and_age_fresh():
    # bbox cat o mep duoi (h=60, tam thay 1058) keo dai 1 s: phai van TRACK, age nho (vi tri van duoc cap nhat)
    dets = _hits(0.0, 1.0, cy=1000.0, h=88.0) + _hits(1.0 + DT, 2.0, cy=1058.0, h=60.0)
    st = _run(dets, 2.0)
    late = [s for t, s in st if t >= 1.3]
    assert all(s.status == TrackStatus.TRACK for s in late), 'roi TRACK khi bbox cham mep'
    assert max(s.age_s for s in late) <= 0.25


# ================================================================ vong sua lan 1
WCAM = make_camera(0.0, 933.0, None, 2304, 1296)      # camera rong: 15 m ~ 134 px
WCX, WCY = WCAM.width / 2, WCAM.height / 2
W0, H0 = 134.0, 60.0


def _wrun(dets, t_end):
    return _run(dets, t_end, cam=WCAM)


def _first_track(st, t0):
    for t, s in st:
        if t > t0 and s.status == TrackStatus.TRACK:
            return t
    return None


# ---- T1: bat lai that sau blackout ngan, co bbox doi truoc khi mat hinh
def test_T1_reacquire_after_shrinking_then_2s_blackout():
    # bbox 134 -> 92 trong 0,5 s (2,5..3,0), mat hinh 2 s, hinh ve dung co 92 tai vi tri cu
    dets = _hits(0.0, 2.5, WCX, WCY, W0, H0)
    n = int(round(0.5 / DT))
    for k in range(1, n + 1):
        s = 1.0 - (1.0 - 92.0 / 134.0) * k / n
        dets.append(Detection(t_capture=2.5 + k * DT, cx=WCX, cy=WCY, w=W0 * s, h=H0 * s, conf=0.85))
    t0 = 3.0 + 2.0
    k92 = 92.0 / 134.0
    dets += _hits(t0, t0 + 0.5, WCX, WCY, W0 * k92, H0 * k92)
    st = _wrun(dets, t0 + 0.7)
    t_trk = _first_track(st, t0)
    assert t_trk is not None, 'khong TRACK lai sau blackout 2 s khi hinh ve dung co 92 (bi chan?)'
    assert t_trk <= t0 + DT + LAT + 2 * DT + 1e-9, 'bat lai qua cham: %.3f (han %.3f)' % (t_trk, t0 + DT + LAT + 2 * DT)


@pytest.mark.parametrize('T', [1.0, 2.0])
def test_T1_reacquire_receding_target_ratio_0_6(T):
    t0 = 3.0 + T
    dets = _hits(0.0, 3.0, WCX, WCY, W0, H0) + _hits(t0, t0 + 0.5, WCX, WCY, W0 * 0.6, H0 * 0.6)
    st = _wrun(dets, t0 + 0.7)
    t_trk = _first_track(st, t0)
    assert t_trk is not None, 'ra xa x0,6 sau COAST %.1f s bi chan' % T
    assert t_trk <= t0 + DT + LAT + 2 * DT + 1e-9


# ---- T2: cham gia van bi chan (gom ca phat hien gia TO)
def test_T2_big_false_pair_far_from_prediction_is_rejected():
    base = _hits(0.0, 3.0)                               # co nho 190 x 88
    big = [Detection(t_capture=4.033, cx=893.0, cy=420.0, w=600.0, h=300.0, conf=0.6),
           Detection(t_capture=4.167, cx=700.0, cy=380.0, w=620.0, h=310.0, conf=0.7)]
    a = _run(base + big, 7.0)
    b = _run(base, 7.0)
    tr = [t for t, s in a if t > 3.5 and s.status == TrackStatus.TRACK]
    assert not tr, 'phat hien gia to cho TRACK luc t=%.3f' % tr[0]
    diffs = [abs(_elev_deg(s) - _elev_deg(s0)) for (t, s), (_, s0) in zip(a, b)
             if 4.033 <= t <= 7.033 and s.los_ned and s0.los_ned]
    assert diffs and max(diffs) <= 1.0, 'max |d elev| = %.2f deg' % max(diffs)


# ---- T3: cham mep keo dai nhung co chuyen dong that: chi truc bi cat moi bi giam tin cay
def _edge_motion_scene():
    from dtrack.geometry import project_ned_point
    det = SyntheticDetector(CAM, SyntheticConfig(clip_to_frame=True))
    q = _q()
    p0 = np.array([15.0, -4.0, 4.4])
    vel = np.array([0.0, 2.0, 0.0])
    dets, truth, clipped = [], {}, []
    for j in range(int(4.5 / DT) + 1):
        t = j * DT
        p = p0 + vel * t
        truth[j] = p / np.linalg.norm(p)
        px = project_ned_point(CAM, q, (0, 0, 0), tuple(p))
        if px is None:
            continue
        b = det._clip_box(px[0], px[1], 250.0, 110.0) if t >= 1.5 else (px[0], px[1], 250.0, 110.0)
        if b is None:
            continue
        if abs(b[1] - px[1]) > 1e-6:
            clipped.append(t)
        dets.append(Detection(t_capture=t, cx=b[0], cy=b[1], w=b[2], h=b[3], conf=0.9))
    return _run(dets, 4.5), truth, clipped


def test_T3_persistent_edge_clip_keeps_unclipped_axis_rate_and_angle():
    st, truth, clipped = _edge_motion_scene()
    assert len(clipped) >= int(3.0 / DT), 'canh khong cat bbox du lau: %d khung' % len(clipped)
    ratios, errs = [], []
    for j, (t, s) in enumerate(st):
        if t < 2.5 or not s.los_ned:
            continue
        ut = truth[j]
        dut = (truth[min(j + 1, len(truth) - 1)] - truth[max(j - 1, 0)]) / (2 * DT)
        wt = np.cross(ut, dut)
        w = np.array(s.los_rate_ned)
        ratios.append(float(w @ wt) / float(wt @ wt) ** 0.5 / float(wt @ wt) ** 0.5)
        errs.append(math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(ut, s.los_ned)))))))
    assert ratios
    assert min(ratios) >= 0.7, 'toc do goc uoc luong chi dat %.0f%% gia tri that (can >=70%%)' % (100 * min(ratios))
    assert max(errs) <= 0.5, 'sai so goc toi da %.2f deg (can <=0,5)' % max(errs)


# ---- T4: blackout dai -> tim lai (khoa ket luan cho khoi tim lai)
@pytest.mark.parametrize('T', [3.2, 4.0, 8.0, 12.0])
@pytest.mark.parametrize('ratio', [0.2, 1.0])
def test_T4_long_blackout_reacquires_within_3_hits(T, ratio):
    t0 = 3.0 + T
    dets = _hits(0.0, 3.0, WCX, WCY, W0, H0) + _hits(t0, t0 + 1.0, WCX, WCY, W0 * ratio, H0 * ratio)
    st = _wrun(dets, t0 + 1.2)
    t_trk = _first_track(st, t0)
    assert t_trk is not None, 'khong TRACK lai'
    assert t_trk <= t0 + 3 * DT + LAT + 1e-9, 'TRACK lai qua cham: %.3f (han %.3f)' % (t_trk, t0 + 3 * DT + LAT)


# ---- T5: hanh vi cong co (khong ghim diem bien)
@pytest.mark.parametrize('ratio', [0.7, 1.5])
def test_T5_clear_in_range_size_ratio_accepted_in_short_coast(ratio):
    t0 = 3.0 + 1.5
    dets = _hits(0.0, 3.0, WCX, WCY, W0, H0) + _hits(t0, t0 + 0.5, WCX, WCY, W0 * ratio, H0 * ratio)
    st = _wrun(dets, t0 + 0.7)
    assert _first_track(st, t0) is not None, 'ti le co %.1f ro rang hop le nhung bi chan' % ratio


@pytest.mark.parametrize('ratio', [0.2, 4.0])
def test_T5_clear_out_of_range_size_ratio_rejected_in_short_coast(ratio):
    t0 = 3.0 + 1.5
    dets = _hits(0.0, 3.0, WCX, WCY, W0, H0) + _hits(t0, t0 + 0.4, WCX, WCY, W0 * ratio, H0 * ratio)
    st = _wrun(dets, t0 + 0.6)                             # chua toi 3 s COAST (3,0 + 3,0 = 6,0)
    tr = [t for t, s in st if t > t0 and s.status == TrackStatus.TRACK]
    assert not tr, 'ti le co %.1f ro rang vo ly van duoc nhan, TRACK luc t=%.3f' % (ratio, tr[0])


# ================================================================ vong sua lan 2: bbox bi cat khi muc tieu truot ra mep
from dtrack.geometry import project_ned_point as _proj  # noqa: E402

_RANGE_M = 15.0


def _az_el(u):
    return math.degrees(math.atan2(u[1], u[0])), math.degrees(math.asin(-u[2]))


def _solve_start(cam, axis, target_px, p):
    """Tim toa do NED (y hoac z) de pixel (cx hoac cy) = target_px, bang chia doi."""
    q = _q()
    idx = 0 if axis == 'cx' else 1
    lo, hi = -15.0, 15.0

    def f(v):
        pp = list(p)
        pp[1 if axis == 'cx' else 2] = v
        px = _proj(cam, q, (0, 0, 0), tuple(pp), require_in_frame=False)
        return px[idx] - target_px
    flo = f(lo)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _slide(cam, cx0, cy0, vy, vz, t_end=6.0, clip=True):
    """Muc tieu NED chuyen dong deu, camera dung yen; bbox cat nhu SyntheticDetector._clip_box.
    Tra dict: states, truth (u theo khung), dets, win (t trang thai khi bbox con >=50% chieu cao va bi cat),
    t_gone (t_capture khung cuoi co phat hien)."""
    S = cam.fx * 2.16 / _RANGE_M
    w_full, h_full = S, 0.44 * S
    p = [_RANGE_M, 0.0, 0.0]
    p[1] = _solve_start(cam, 'cx', cx0, p)
    p[2] = _solve_start(cam, 'cy', cy0, p)
    det = SyntheticDetector(cam, SyntheticConfig(clip_to_frame=True))
    q = _q()
    dets, truth, clipped_ok = [], [], []
    vel = np.array([0.0, vy, vz])
    n = int(round(t_end / DT)) + 1
    for j in range(n + 2):
        t = j * DT
        pt = np.array(p) + vel * t
        truth.append(pt / np.linalg.norm(pt))
        px = _proj(cam, q, (0, 0, 0), tuple(pt), require_in_frame=False)
        if px is None:
            continue
        b = det._clip_box(px[0], px[1], w_full, h_full) if clip else (px[0], px[1], w_full, h_full)
        if b is None:
            continue
        dets.append(Detection(t_capture=t, cx=b[0], cy=b[1], w=b[2], h=b[3], conf=0.9))
        if clip and (abs(b[1] - px[1]) > 1e-6 or abs(b[0] - px[0]) > 1e-6) and (
                b[3] >= 0.5 * h_full or abs(b[0] - px[0]) > 1e-6):
            clipped_ok.append(t)
    states = _run(dets, t_end, cam=cam)
    return dict(states=states, truth=truth, dets=dets, clip_t=clipped_ok,
                t_gone=dets[-1].t_capture, h_full=h_full)


def _errs(sc, t_lo, t_hi):
    """Sai so (|d el| deg, |d el_rate| deg/s, |d az| deg, |d az_rate| deg/s) toi da cho t trong [t_lo, t_hi]."""
    out = dict(el=0.0, elr=0.0, az=0.0, azr=0.0)
    truth = sc['truth']
    for j, (t, s) in enumerate(sc['states']):
        if not (t_lo <= t <= t_hi) or not s.los_ned:
            continue
        a1, e1 = _az_el(truth[j + 1])
        a0, e0 = _az_el(truth[j - 1])
        a, e = _az_el(truth[j])
        u = np.array(s.los_ned)
        d = np.cross(np.array(s.los_rate_ned), u)               # du/dt
        ea, ee = _az_el(u)
        ee_rate = math.degrees(-d[2] / math.cos(math.radians(ee)))
        ea_rate = math.degrees((u[0] * d[1] - u[1] * d[0]) / (u[0] ** 2 + u[1] ** 2))
        out['el'] = max(out['el'], abs(ee - e))
        out['elr'] = max(out['elr'], abs(ee_rate - (e1 - e0) / (2 * DT)))
        out['az'] = max(out['az'], abs(ea - a))
        out['azr'] = max(out['azr'], abs(ea_rate - (a1 - a0) / (2 * DT)))
    return out


def _window(sc):
    ct = sc['clip_t']
    assert len(ct) >= 15, 'canh khong cat bbox du lau: %d khung' % len(ct)
    return ct[0] + LAT, ct[-1] + LAT


NARROW = (CAM, 728.0, None)


def _vertical_case(cam, cy0, vz, **kw):
    sc = _slide(cam, cam.width / 2, cy0, 0.0, vz, **kw)
    lo, hi = _window(sc)
    return sc, _errs(sc, lo, hi)


def _check_vertical(e, tag):
    bad = []
    if e['el'] > 0.3:
        bad.append('|elev - that| toi da %.2f deg (can <=0,3)' % e['el'])
    if e['elr'] > 0.4:
        bad.append('sai so toc do LOS doc toi da %.2f deg/s (can <=0,4)' % e['elr'])
    assert not bad, '%s: %s' % (tag, '; '.join(bad))

def test_E1_slide_down_through_bottom_edge():
    sc, e = _vertical_case(CAM, CAM.height - 120.0, 0.5)
    _check_vertical(e, 'E1')


def test_E2_slide_up_through_top_edge():
    sc, e = _vertical_case(CAM, 120.0, -0.5)
    _check_vertical(e, 'E2')


def test_E3_diagonal_vertical_axis_and_horizontal_axis_unaffected():
    sc = _slide(CAM, 300.0, CAM.height - 120.0, 1.5, 0.4)
    lo, hi = _window(sc)
    e = _errs(sc, lo, hi)
    ref = _slide(CAM, 300.0, CAM.height - 120.0, 1.5, 0.4, clip=False)
    r = _errs(ref, lo, hi)
    assert e['az'] <= r['az'] + 0.1, 'E3: sai so phuong vi %.2f deg vs khong cat %.2f' % (e['az'], r['az'])
    assert e['azr'] <= r['azr'] + 0.4, 'E3: sai so toc do ngang %.2f vs khong cat %.2f deg/s' % (e['azr'], r['azr'])
    _check_vertical(e, 'E3')


def test_E4_extrapolated_elev_after_target_leaves_frame():
    sc = _slide(CAM, CAM.width / 2, CAM.height - 120.0, 0.0, 0.5)
    t0 = sc['t_gone'] + LAT
    e = _errs(sc, t0 + 1.0 - DT / 2, t0 + 1.0 + DT / 2)
    assert e['el'] <= 0.8, 'E4: elev ngoai suy sau COAST 1 s lech %.2f deg (can <=0,8)' % e['el']


def test_E5_wide_camera_slide_down():
    sc, e = _vertical_case(WCAM, WCAM.height - 120.0, 0.5)
    _check_vertical(e, 'E5')


def test_E6_track_initialised_at_edge_without_size_memory_stays_finite():
    dets = _hits(0.0, 1.0, cx=728.0, cy=1062.0, w=250.0, h=52.0)      # bbox da bi cat o mep duoi tu khung dau
    st = _run(dets, 1.2)
    last = st[-1][1]
    assert last.status == TrackStatus.TRACK
    assert all(np.all(np.isfinite(s.los_ned)) and np.all(np.isfinite(s.los_rate_ned))
               for _, s in st if s.los_ned)

