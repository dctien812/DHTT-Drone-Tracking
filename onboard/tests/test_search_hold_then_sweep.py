"""Pha DO cua thay doi (A) giai doan 2b, quy tac S-16 (.office/plan-phase2b.md; E1, E3, E4): "GIU ROI MOI QUET".

Quy tac: khoa moi SearchConfig.scan_start_s (mac dinh 12,0; giay tinh tu dau dot tim = COAST dau). Khi thoi gian dot
< scan_start_s: khop gimbal KHONG quet ma giu ngam theo he the gioi (huong du doan khi bo nho con han 8 s, sau do huong
ngam cuoi last_aim, dong bang theo he the gioi, van bu tu the than). Tu scan_start_s: quet ca dai 10-110 nhu hien nay.
Rang buoc khi search.enabled: coast_follow_s < scan_start_s < total_s, huu han. S-3 khong doi.

GIA DINH VE GIAO DIEN: chi (1) khoa SearchConfig.scan_start_s (ten do truong phong chot; cac ca cau hinh o cuoi file),
(2) cac truong co san: out.search.scan_delta_rad/ep_s, tr.status, out.request_rtl, port.angle. Cac ca mo phong chay qua ma that
(SyntheticDetector, SingleTargetTracker, Supervisor ho so search_plane_r15, GimbalController, ServoModel/SimGimbalPort) theo
vong lap cua test_search_scan_real_tracker.py. Cac ca mo phong dung hang SCAN_START = 12.0 (mac dinh cua khoa) chu khong doc khoa.

Dung hinh: drone DUNG YEN o (0, 0, -70); yaw than theo lenh yaw cua supervisor toi da 60 do/s. X ngang -45 do luc mat hinh, roi bay thang deu 4 m/s huong xuong -40 do (van toc luc mat hinh duoc giu: huong ngam cuoi/du doan
con dung); goc ngang that ~-43..-42 do luc 8-11 s, cu ly 62-74 m. LUU Y: so do cua truong phong (-42 do luc 8 s, -34 do luc 11 s,
48-77 m) khong the dung voi van toc khong doi + drone dung yen (se o sau luong drone), nen toi giu goc ngang ~-42 va cu ly
62-74 m; goc khop de thay muc tieu van chi la dai hep >= ~97 do (kiem bang chieu camera that o test hinh hoc).
"Muc tieu trong khung" tinh bang hinh hoc camera that: project_ned_point + camera_attitude (khong dung nguong tu chon).

CA DO (hanh vi/thieu khoa): test_dive_reacquire_latency_*, test_gimbal_aim_follows_world_*, test_gimbal_does_not_sweep_before_scan_start,
test_scan_start_s_* (cau hinh). CA BAO VE (xanh san): test_profile_assumptions, test_dive_geometry_*, test_full_sweep_*,
test_target_moved_*, test_old_profiles_*.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DT = 1.0 / 30
T_BLACK = 6.0                       # luc mat hinh (s)
POS = (0.0, 0.0, -70.0)
MEM_S = 8.0                         # blind_mem_max_s
COAST_S = 4.0                       # supervisor.coast_follow_s
SCAN_START = 12.0                   # mac dinh moi cua scan_start_s
# thoi diem hinh tro lai, giay sau mat hinh: ~deu 4,2..11,5, co 8,0 va hai gia tri > 8 s (9,0 va 11,0)
RESUME_OFFSETS = (4.2, 5.0, 5.8, 6.6, 7.4, 8.0, 8.6, 9.0, 9.8, 10.6, 11.0, 11.5)
OLD_PROFILES = ["accept_gimbal_r25", "accept_plane_r25", "accept_plane_r15", "realdet"]


def _pt(elev_deg, rng):
    e = math.radians(elev_deg)
    return (POS[0] + rng * math.cos(e), POS[1], POS[2] - rng * math.sin(e))


P_LOSS = _pt(-45.0, 45.0)
_V = (3.0 * math.cos(math.radians(-40.0)), 0.0, -3.0 * math.sin(math.radians(-40.0)))   # NED, xuong


def dive_target(t):
    """Vi tri NED muc tieu o ca bo nhao: bay thang deu voi van toc _V suot ca chuyen (qua P_LOSS dung luc mat hinh)."""
    r = t - T_BLACK
    return tuple(P_LOSS[i] + _V[i] * r for i in range(3))


def _quat(yaw, pitch):
    import numpy as np
    from dtrack.geometry import quat_multiply
    qz = np.array([math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)])
    qy = np.array([math.cos(pitch / 2), 0.0, math.sin(pitch / 2), 0.0])
    return tuple(float(c) for c in quat_multiply(qz, qy))


def _setup(seed):
    from dtrack.config import _fill, load_profile, profile_dict
    cfg = load_profile("search_plane_r15")
    _fill(cfg.synthetic, profile_dict("realdet")["synthetic"], "synthetic")
    cfg.synthetic.seed = seed
    cfg.gimbal.delta_init_deg = 110.0     # gimbal da huong xuong luc bat dau de bo bam bat duoc muc tieu o -48 do
    return cfg


def in_frame(cfg, q_body, delta, tgt):
    """Hinh hoc camera that cua ho so: diem tgt co roi vao khung o goc khop delta khong."""
    from dtrack.geometry import project_ned_point
    from dtrack.gimbal import camera_attitude
    return project_ned_point(cfg.camera.to_model(), camera_attitude(q_body, delta), POS, tgt) is not None


def simulate(seed, target_fn, t_resume, t_end, pitch_fn=None, stop_on_track=False):
    """Chay vong kin. Muc tieu bi che trong [T_BLACK, t_resume). Tra dict: ts, ep_s, delta (rad, thuc), pitch,
    ep_t0 (s tuyet doi luc mo dot), first_track, first_visible (tu t_resume, theo hinh hoc that), rtl, lost_frame_t."""
    from dtrack.gimbal import camera_attitude
    from dtrack.gimbal_control import GimbalController
    from dtrack.range_estimator import RangeConfig
    from dtrack.supervisor import Supervisor, SupervisorInput
    from dtrack.synthetic import SyntheticDetector
    from dtrack.tracker import SingleTargetTracker, TrackerConfig
    from dtrack.types import OwnState, TrackStatus
    from simtools.servo_model import ServoModel, SimGimbalPort

    cfg = _setup(seed)
    cam = cfg.camera.to_model()
    tracker = SingleTargetTracker(cam, TrackerConfig(range=RangeConfig(target_size_m=cfg.target_shape.span_m)))
    det = SyntheticDetector(cam, cfg.synthetic, cfg.target_shape)
    sup = Supervisor(cfg.supervisor, cfg.guidance, cfg.search, cfg.gimbal)
    port = SimGimbalPort(ServoModel.from_config(cfg.gimbal))
    gc = GimbalController(cfg.gimbal)
    yaw = 0.0
    rec = {"ts": [], "ep_s": [], "yaw_cmd": [], "delta": [], "pitch": [], "ep_t0": None, "first_track": None,
           "first_visible": None, "rtl": None, "out_of_frame_t": None}
    for k in range(int(t_end / DT) + 1):
        t = k * DT
        pitch = 0.0 if pitch_fn is None else pitch_fn(t)
        tgt = target_fn(t)
        delta_act = port.angle(t)
        q = _quat(yaw, pitch)
        qc = tuple(float(c) for c in camera_attitude(q, delta_act))
        own_c = OwnState(t=t, pos_ned=POS, vel_ned=(0, 0, 0), q_world_body=qc, armed=True, mode="GUIDED")
        dets = [] if T_BLACK <= t < t_resume else det.process(t, tgt, own_c, heading=None, target_vel_ned=None)
        own = OwnState(t=t, pos_ned=POS, vel_ned=(0, 0, 0), q_world_body=q, armed=True, mode="GUIDED")
        tr = tracker.update(dets, own_c, t)
        out = sup.step(SupervisorInput(t=t, track=tr, own=own, engage=True, heartbeat_age_s=0.1, pose_age_s=0.02,
                                       loop_dt_s=DT, gimbal_delta_rad=delta_act))
        sc = None if out.search is None else out.search.scan_delta_rad
        ep_s = None if out.search is None else out.search.ep_s
        if ep_s is not None and rec["ep_t0"] is None:
            rec["ep_t0"] = t - ep_s
        g = gc.step(t, q, tr, scan_delta_rad=sc)
        port.command(t, g.delta_cmd_rad)
        if out.cmd is not None and out.cmd.yaw_rad is not None:
            e = (out.cmd.yaw_rad - yaw + math.pi) % (2 * math.pi) - math.pi
            yaw += max(-math.radians(60) * DT, min(math.radians(60) * DT, e))
        rec["ts"].append(t)
        rec["ep_s"].append(ep_s)
        rec["yaw_cmd"].append(None if out.cmd is None else out.cmd.yaw_rad)
        rec["delta"].append(delta_act)
        rec["pitch"].append(pitch)
        if out.request_rtl and rec["rtl"] is None:
            rec["rtl"] = t
        if T_BLACK <= t and not in_frame(cfg, q, delta_act, tgt) and rec["out_of_frame_t"] is None and t < t_resume:
            rec["out_of_frame_t"] = t - T_BLACK      # muc tieu ra khung luc nay (s sau mat hinh)
        if t >= t_resume:
            if rec["first_visible"] is None and in_frame(cfg, q, delta_act, tgt):
                rec["first_visible"] = t
            if tr.status == TrackStatus.TRACK and rec["first_track"] is None:
                rec["first_track"] = t
                if stop_on_track:
                    break
        if rec["rtl"] is not None:
            break
    return rec


def _boresight_elev_deg(q_body, delta):
    import numpy as np
    from dtrack.geometry import quat_to_matrix
    from dtrack.gimbal import camera_attitude
    x = quat_to_matrix(camera_attitude(q_body, delta)) @ np.array([1.0, 0.0, 0.0])
    return math.degrees(math.asin(max(-1.0, min(1.0, -float(x[2])))))


# ---------------------------------------------------------------- bao ve: gia dinh va hinh hoc
def test_profile_assumptions():
    """CA BAO VE: bo nho 8 s, COAST 4 s, camera fx=fy=933 2304x1296, quet 10-110 o 60 do/s, khong leo (pha 2 tat)."""
    cfg = _setup(0)
    assert cfg.guidance.blind_mem_max_s == MEM_S
    assert cfg.supervisor.coast_follow_s == COAST_S
    assert (cfg.camera.fx, cfg.camera.fy, cfg.camera.width, cfg.camera.height) == (933.0, 933.0, 2304, 1296)
    assert (cfg.search.scan_lo_deg, cfg.search.scan_hi_deg, cfg.search.scan_rate_dps) == (10.0, 110.0, 60.0)
    assert cfg.search.enabled and cfg.search.climb_m == 0.0 and cfg.search.total_s == 20.0


def test_dive_geometry_is_hard_for_sweep_but_frozen_aim_keeps_target_in_frame():
    """CA BAO VE (hinh hoc that): luc 4/8/11,5 s sau mat hinh muc tieu chi lot khung o dai khop hep (>= 95 do, <= 25% dai
    10-110 do) khi than ngang; con huong giu 110 do (ngam cuoi bao hoa khi muc tieu o -45 do) thay muc tieu o MOI thoi diem
    4..11,5 s va voi yaw -45/0/+45 do (bien do quet yaw)."""
    cfg = _setup(0)
    q = _quat(0.0, 0.0)
    deltas = [math.radians(d / 4.0) for d in range(40, 441)]          # 10..110 do, buoc 0,25
    for off in (4.0, 8.0, 11.5):
        p = dive_target(T_BLACK + off)
        vis = [d for d in deltas if in_frame(cfg, q, d, p)]
        assert vis, "muc tieu %.1f s khong lot khung o goc khop nao" % off
        assert math.degrees(min(vis)) >= 95.0, "dai thay duoc %.1f s bat dau o %.1f do" % (off, math.degrees(min(vis)))
        assert len(vis) / len(deltas) <= 0.25
    for yaw_deg in (-45.0, 0.0, 45.0):
        for k in range(0, 76):
            off = 4.0 + 0.1 * k
            assert in_frame(cfg, _quat(math.radians(yaw_deg), 0.0), math.radians(110.0), dive_target(T_BLACK + off)), \
                "huong giu 110 do, yaw %+.0f: muc tieu ra khung luc %.1f s sau mat hinh" % (yaw_deg, off)


# ---------------------------------------------------------------- do: E1
@pytest.mark.parametrize("off", RESUME_OFFSETS)
def test_dive_reacquire_latency_within_1s_for_every_resume_time(off):
    """CA DO (E1): hinh tro lai 'off' s sau mat hinh (4,2..11,5 s, co 8,0 / 9,0 / 11,0): tu luc do toi TRACK <= 1,0 s.
    Hien tai gimbal quet ca dai tu pha 1 nen chi lot khung 0,2-0,3 s moi chu ky 3,33 s."""
    t_resume = T_BLACK + off
    rec = simulate(int(off * 10) % 4, dive_target, t_resume, t_resume + 4.0, stop_on_track=True)
    lat = None if rec["first_track"] is None else rec["first_track"] - t_resume
    vis = None if rec["first_visible"] is None else rec["first_visible"] - t_resume
    assert rec["rtl"] is None
    assert lat is not None and lat <= 1.0, (
        "hinh tro lai %.1f s sau mat hinh: tre toi TRACK = %s (> 1,0 s); muc tieu vao khung (hinh hoc that) sau %s s; "
        "muc tieu ra khung luc %s s sau mat hinh"
        % (off, "khong len TRACK trong 4 s" if lat is None else "%.2f s" % lat,
           "khong bao gio" if vis is None else "%.2f" % vis, rec["out_of_frame_t"]))


# ---------------------------------------------------------------- do: bu tu the
@pytest.mark.parametrize("name,lo,hi", [("memory_alive", 5.7, 7.5), ("memory_expired_last_aim", 8.5, 11.5)])
def test_gimbal_aim_follows_world_when_body_pitches(name, lo, hi):
    """CA DO: muc tieu dung yen o goc ngang -10 do, bi che tu T_BLACK. Than ha mui 15 do (doi dan tu 4,5 s toi 5,5 s). Huong ngam
    THE GIOI cua truc quang van lech <= 5 do khoi -10 do ca khi bo nho du doan con han (5,7-7,5 s) lan sau khi het han
    (8,5-11,5 s; khi do ngam cuoi last_aim). Hien tai: khop quet nen lech lon."""
    elev = -10.0
    p = _pt(elev, 60.0)
    pitch_fn = lambda t: math.radians(-15.0) * min(1.0, max(0.0, (t - (T_BLACK + 4.5)) / 1.0))
    rec = simulate(0, lambda t: p, 1e9, T_BLACK + 11.6, pitch_fn=pitch_fn)
    errs = [abs(_boresight_elev_deg(_quat(0.0, pt), d) - elev)
            for t, d, pt in zip(rec["ts"], rec["delta"], rec["pitch"]) if T_BLACK + lo <= t <= T_BLACK + hi]
    assert errs and max(errs) <= 5.0, (
        "[%s] huong ngam the gioi lech toi da %.1f do (> 5 do) so voi %.0f do" % (name, max(errs), elev))


def test_gimbal_does_not_sweep_before_scan_start():
    """CA DO: truoc scan_start_s (12 s ke tu dau dot), than ngang, khop khong quet: bien do goc khop (thuc) <= 10 do
    trong ep_s 5..11,8 (khong co phat hien). Hien tai quet 10-110 do."""
    rec = simulate(0, dive_target, 1e9, T_BLACK + 14.0)
    ds = [math.degrees(d) for d, e in zip(rec["delta"], rec["ep_s"]) if e is not None and 5.0 <= e <= 11.8]
    assert ds
    assert max(ds) - min(ds) <= 10.0, "goc khop truoc scan_start dao dong %.1f..%.1f do" % (min(ds), max(ds))


def _yaw_dev_deg(rec, lo, hi):
    """Lech (do) cua lenh yaw out.cmd.yaw_rad so voi huong luc vao pha 1 (tick dau co ep_s > coast_follow_s), cho ep_s trong [lo, hi]."""
    ref = next(y for y, e in zip(rec["yaw_cmd"], rec["ep_s"]) if e is not None and e > COAST_S and y is not None)
    wrap = lambda a: (a + math.pi) % (2 * math.pi) - math.pi
    return [math.degrees(wrap(y - ref)) for y, e in zip(rec["yaw_cmd"], rec["ep_s"])
            if e is not None and lo <= e <= hi and y is not None]


def test_yaw_command_holds_heading_before_scan_start():
    """CA DO (S-16, yaw): tu dau pha 1 toi scan_start_s (ep_s 4,1..11,8) lenh yaw out.cmd.yaw_rad khong lech qua 2 do
    khoi huong luc vao pha 1 (khong quet yaw). Hien tai quet +-45 do tu dau pha 1."""
    rec = simulate(0, dive_target, 1e9, T_BLACK + 12.0)
    dev = _yaw_dev_deg(rec, COAST_S + 0.1, SCAN_START - 0.2)
    assert dev
    assert max(abs(d) for d in dev) <= 2.0, "lenh yaw lech toi da %.1f do khoi huong luc vao pha 1 (> 2 do)" % max(abs(d) for d in dev)


def test_yaw_sweep_reaches_amplitude_after_scan_start():
    """CA BAO VE (S-16, yaw): sau scan_start_s (ep_s 12..19,5) lenh yaw quet toi gan bien do yaw_amp_deg (>= 40 do cua 45)
    so voi huong da giu. Xanh tren ma hien tai (quet tu som); y nghia khi di cung ca 'giu huong' o tren."""
    rec = simulate(0, dive_target, 1e9, T_BLACK + 19.5)
    dev = _yaw_dev_deg(rec, SCAN_START, 19.5)
    assert rec["rtl"] is None and dev
    assert max(abs(d) for d in dev) >= 40.0, "yaw quet chi toi %.1f do sau scan_start" % max(abs(d) for d in dev)


# ---------------------------------------------------------------- bao ve: quet tu scan_start
def test_full_sweep_starts_at_scan_start():
    """CA BAO VE doi moc (iii): tu scan_start_s (12 s) trong 4 s tiep theo goc khop phu <= 15 do va >= 105 do, khong RTL.
    (Tren ma hien tai xanh vi no quet tu som; test do truoc moc o ca tren la ca do.)"""
    rec = simulate(0, dive_target, 1e9, T_BLACK + 18.0)
    ds = [math.degrees(d) for d, e in zip(rec["delta"], rec["ep_s"]) if e is not None and SCAN_START + 0.3 <= e <= SCAN_START + 4.0]
    assert rec["rtl"] is None
    assert ds and min(ds) <= 15.0 and max(ds) >= 105.0, "dai goc khop sau scan_start: %.1f..%.1f do" % (min(ds), max(ds))


def test_target_moved_during_blind_found_after_scan_start_and_before_rtl():
    """CA BAO VE: muc tieu doi sang vung chi thay duoc o goc khop <= 45 do (goc ngang +50 do) trong luc bi che; hinh tro lai
    9 s sau mat hinh (con trong giai doan giu). Phai len TRACK trong <= scan_start_s + 4 s ke tu dau dot va truoc RTL (20 s)."""
    p_far = _pt(50.0, 60.0)
    moved = lambda t: P_LOSS if t < T_BLACK else p_far
    t_resume = T_BLACK + 9.0
    rec = simulate(1, moved, t_resume, T_BLACK + 19.0, stop_on_track=True)
    assert rec["rtl"] is None
    assert rec["first_track"] is not None and rec["ep_t0"] is not None
    assert rec["first_track"] - rec["ep_t0"] <= SCAN_START + 4.0, (
        "len TRACK o ep_s=%s (> %.1f)" % (rec["first_track"] - rec["ep_t0"], SCAN_START + 4.0))


# ---------------------------------------------------------------- khoa cau hinh scan_start_s
def _app(search_kw=None, enabled=True):
    from dtrack.config import AppConfig
    cfg = AppConfig()
    cfg.gimbal.enabled = True
    for k, v in (search_kw or {}).items():
        setattr(cfg.search, k, v)
    cfg.search.enabled = enabled
    cfg.guidance.blind_floor_m = 8.0
    return cfg


def test_scan_start_s_default_is_12():
    from dtrack.config import SearchConfig
    assert SearchConfig().scan_start_s == 12.0


def test_scan_start_s_in_search_plane_r15_profile():
    from dtrack.config import load_profile
    assert load_profile("search_plane_r15").search.scan_start_s == 12.0


@pytest.mark.parametrize("val", [4.1, 12.0, 19.9])
def test_scan_start_s_valid_values_accepted_and_stored(val):
    from dtrack.config import validate
    cfg = _app({"scan_start_s": val})
    validate(cfg)
    assert cfg.search.scan_start_s == val        # khoa phai ton tai that (khong chi bi gan them vao doi tuong)
    from dtrack.config import SearchConfig
    assert "scan_start_s" in SearchConfig.__dataclass_fields__


@pytest.mark.parametrize("val", [4.0, 3.0, 20.0, 25.0, 0.0, -1.0, float("nan"), float("inf")])
def test_scan_start_s_invalid_values_rejected_when_enabled(val):
    """coast_follow_s (4,0) < scan_start_s < total_s (20,0), huu han."""
    from dtrack.config import validate
    with pytest.raises(ValueError):
        validate(_app({"scan_start_s": val}))


@pytest.mark.parametrize("name", OLD_PROFILES)
def test_old_profiles_keep_search_disabled(name):
    """CA BAO VE: ho so cu van tat tim lai (hanh vi cu khong doi) va van validate duoc."""
    from dtrack.config import load_profile, validate
    cfg = load_profile(name)
    assert cfg.search.enabled is False
    validate(cfg)


# ---------------------------------------------------------------- leo (pha 2) doc lap voi moc quet; follow qua TRACK ngan
def _run_sup(climb_m, t_end, status_fn, delta_fn=None):
    """Supervisor THAT (ho so search_plane_r15, climb_m cho truoc), drone treo (0,0,-30) co dong hoc vz don gian (z += vz*dt).
    status_fn(t) -> (status, range). delta_fn(t) -> goc khop thuc dau vao hoac None = lay theo scan cuoi (90 do luc dau).
    Tra list (t, out, vz_cmd)."""
    from dtrack.config import load_profile
    from dtrack.supervisor import Supervisor, SupervisorInput
    from dtrack.types import OwnState, TrackState, TrackStatus
    cfg = load_profile("search_plane_r15")
    cfg.search.climb_m = climb_m
    cfg.search.climb_start_s = 10.0
    sup = Supervisor(cfg.supervisor, cfg.guidance, cfg.search, cfg.gimbal)
    z, vzc, delta, rows = -30.0, 0.0, math.radians(90.0), []
    for k in range(int(t_end / DT)):
        t = k * DT
        st, r = status_fn(t)
        if st in (TrackStatus.SEARCH, TrackStatus.LOST):
            trk = TrackState(t=t, status=st)
        else:
            trk = TrackState(t=t, status=st, los_ned=(1.0, 0.0, 0.0), los_rate_ned=(0.0, 0.0, 0.0), range_m=r,
                             range_sigma_m=1.0, range_rate_mps=0.0, range_valid=True)
        own = OwnState(t=t, pos_ned=(0.0, 0.0, z), vel_ned=(0.0, 0.0, vzc), q_world_body=(1.0, 0.0, 0.0, 0.0),
                       armed=True, mode="GUIDED")
        din = delta if delta_fn is None else delta_fn(t, delta)
        out = sup.step(SupervisorInput(t=t, track=trk, own=own, engage=True, heartbeat_age_s=0.1, pose_age_s=0.02,
                                       loop_dt_s=DT, gimbal_delta_rad=din))
        if out.search is not None and out.search.scan_delta_rad is not None:
            delta = out.search.scan_delta_rad
        elif delta_fn is not None:
            delta = din
        vz = out.cmd.vel_ned[2] if out.cmd is not None else 0.0
        rows.append((t, out, vz))
        vzc = vz
        z += vz * DT
    return rows


def _lose_at_1(t):
    from dtrack.types import TrackStatus
    if t < 1.0:
        return TrackStatus.TRACK, 25.0
    return (TrackStatus.COAST, 25.0) if t < 2.5 else (TrackStatus.LOST, 25.0)


def test_climb_starts_at_climb_start_s_independent_of_scan_start_s():
    """CA DO: climb_m=10, climb_start_s=10, scan_start_s=12 (mac dinh): leo (vz < -0,05) bat dau o ep_s 10,0..10,3 (khong cho
    toi moc quet 12 s); trong 10..12 s goc khop khong quet (scan_delta_rad None) va lenh yaw khong doi (<= 1 do)."""
    rows = _run_sup(10.0, 16.0, _lose_at_1)
    ep = lambda o: o.search.ep_s
    first = next((ep(o) for t, o, vz in rows if o.search is not None and ep(o) is not None and ep(o) > 4.0 and vz < -0.05), None)
    assert first is not None and 10.0 <= first <= 10.3, "leo bat dau o ep_s = %s (can 10,0..10,3)" % first
    win = [o for t, o, vz in rows if o.search is not None and ep(o) is not None and 10.0 <= ep(o) <= 11.9]
    assert win and all(o.search.scan_delta_rad is None for o in win), "goc khop quet trong luc leo truoc moc"
    ys = [o.cmd.yaw_rad for o in win]
    assert max(ys) - min(ys) <= math.radians(1.0)


def test_no_climb_when_climb_m_is_zero():
    """CA BAO VE: climb_m = 0 thi khong bao gio leo (vz >= -0,05) ca sau moc quet."""
    rows = _run_sup(0.0, 18.0, _lose_at_1)
    assert min(vz for t, o, vz in rows if o.search is not None and o.search.ep_s is not None and o.search.ep_s > 4.0) >= -0.05


def test_scan_start_after_short_track_straddling_mark_does_not_jump():
    """CA (08 nhan xet nho: nhanh TRACK truoc moc khong goi follow): truoc moc khop dung o 90 do; TRACK ngan (< 1 s, khong dong dot)
    12,6..13,4 s (0,8 s; vat qua moc ep_s 12 s = t 13,0 vi ep0 ~ 1,0 s) trong do gimbal bi dich ve 60 do (>= 15 do so voi luc vao pha 1);
    sau khi TRACK mat, lenh quet dau tien phai gan goc khop thuc (60 do): |nhay| <= scan_rate*0,1 s + 1 do."""
    from dtrack.types import TrackStatus

    def status(t):
        if 12.6 <= t < 13.4:
            return TrackStatus.TRACK, 60.0
        return _lose_at_1(t)

    def delta_fn(t, last_scan):
        if t < 12.6:
            return math.radians(90.0)
        return math.radians(90.0 - 30.0 * min(1.0, (t - 12.6) / 0.3)) if t < 13.4 else last_scan
    rows = _run_sup(0.0, 16.0, status, delta_fn)
    assert not any(o.search is not None and o.search.closed for _, o, _ in rows)
    first = next((o.search.scan_delta_rad for t, o, _ in rows if t >= 13.4 and o.search is not None
                  and o.search.scan_delta_rad is not None), None)
    assert first is not None
    jump = abs(math.degrees(first) - 60.0)
    assert jump <= 60.0 * 0.1 + 1.0, "lenh quet dau tien sau TRACK ngan nhay %.1f do so voi goc khop thuc 60 do" % jump
