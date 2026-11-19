"""Test (pha do, viet truoc ma) cho BUOC 4b: ElevRefRamp + noi vao guidance.

Dac ta: .office/design-gimbal-steps-3-6.md, muc "Buoc 4b" va config buoc 3
(GuidanceConfig.elev_ramp_enabled=False, elev_ramp_dps=2.0; diem cuoi = target_elev_ref_deg).

Quy uoc dau / don vi dung trong file nay (theo design "Quyet dinh chung" va guidance.py:172-182):
  - u = LOS NED don vi tu drone toi muc tieu; z NED huong XUONG.
  - elev_los (rad) = asin(-u_z/|u|): DUONG = muc tieu CAO hon mat phang ngang cua drone.
  - ElevRefRamp.update(t, elev_los_rad) nhan RADIAN, tra / luu value bang DO.
  - e_ref (do) cung quy uoc: e_ref < elev_los nghia la muon muc tieu THAP hon -> drone phai LEO.
  - Vong dung voi cam_tilt_up_deg=0, than ngang: err_tong = e_ref - elev_los (rad),
    vc = clip(kp_vert_center * r * tan(err_tong)), vel_ned[2] > 0 = XUONG, < 0 = LEN.
  - Ramp di tu elev luc khoa toi final; khi da khoi dong thi KHONG theo do dac nua.

Quyet dinh cua truong phong (cho cho dac ta chua ro):
  - Ramp CHI khoi dong o lan TRACK dau tien co los_ned hop le. COAST, SEARCH, LOST hay TRACK co los_ned
    hong thi chua khoi dong: last_elev_ref_deg van None, di duong cu.
  - Da khoi dong thi ramp tien theo thoi gian o MOI trang thai di qua step() hoac step_blind()
    (SEARCH/LOST/COAST deu tien tiep; last_elev_ref_deg = gia tri ramp hien tai); khong khoi dong lai.
  - Guidance.reset() dua last_elev_ref_deg ve None.
  - Ramp trong Guidance dung cfg.elev_ramp_dps, cfg.target_elev_ref_deg, cfg.dt_max_s.

Moi import moi (dtrack.elev_ramp, truong elev_ramp_*, tham so elev_ref_deg) dat TRONG ham test de
moi ca do rieng, khong loi thu thap.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.config import GuidanceConfig
from dtrack.guidance import Guidance, compute_guidance_ex
from dtrack.types import GuidanceCommand, OwnState, TrackState, TrackStatus

Q0 = (1.0, 0.0, 0.0, 0.0)
DT = 1.0 / 30
R = math.radians


def own(v=(0.0, 0.0, 0.0), alt=30.0, t=10.0):
    return OwnState(t=t, pos_ned=(0.0, 0.0, -alt), vel_ned=v, q_world_body=Q0, armed=True, mode="GUIDED")


def track(r=15.0, u=(1.0, 0.0, 0.0), status=TrackStatus.TRACK, rate=(0.0, 0.0, 0.0), rdot=0.0, t=10.0,
          valid=True):
    if status in (TrackStatus.SEARCH, TrackStatus.LOST):
        return TrackState(t=t, status=status)
    return TrackState(t=t, status=status, los_ned=u, los_rate_ned=rate, range_m=r, range_sigma_m=1.0,
                      range_rate_mps=rdot, range_valid=valid)


def prev_cmd(v=(0.0, 0.0, 0.0), dt=0.1, t=10.0, reason="track"):
    return GuidanceCommand(t=t - dt, vel_ned=v, yaw_rad=0.0, valid=True, reason=reason)


def u_el(deg):
    """LOS don vi o goc nang `deg` (duong = muc tieu cao hon), huong Bac."""
    e = R(deg)
    return (math.cos(e), 0.0, -math.sin(e))


def make_ramp(final=-12.0, rate=2.0, dt_max=0.2):
    from dtrack.elev_ramp import ElevRefRamp
    return ElevRefRamp(final, rate, dt_max)


def gcfg(**kw):
    base = dict(cam_tilt_up_deg=0.0, elev_ramp_enabled=True, elev_ramp_dps=2.0, target_elev_ref_deg=-12.0)
    base.update(kw)
    return GuidanceConfig(**base)


# =============== (1) khoi dong tu elev do, khong nhay ===============
def test_ramp_starts_at_measured_elevation():
    r = make_ramp()
    assert r.update(10.0, R(3.0)) == pytest.approx(3.0, abs=1e-9)   # tra DO, nhan RAD
    assert r.value == pytest.approx(3.0, abs=1e-9)


def test_guidance_first_lock_step_has_no_vertical_jump():
    # Tinh tay: u o +3 do, tilt 0, than ngang -> err anh = -3 do; e_ref = 3 (gia tri khoi dong) -> err_tong = 0
    # -> vc = 0. r = range_set 15 -> u_p = 0; v_own = 0 -> v_t = 0. Lenh = 0.
    # Duong cu (khong ramp): e_ref = clip(-12, +-8) = -8 -> err_tong = -11 do -> vz != 0 (da chay: -0.00858).
    g = Guidance(gcfg())
    c = g.step(track(u=u_el(3.0), t=10.0), own())
    assert g.last_elev_ref_deg == pytest.approx(3.0, abs=1e-9)
    assert abs(c.vel_ned[2]) < 1e-9


# =============== (2) buoc <= rate*dt, don dieu, dung dung final, hai chieu ===============
@pytest.mark.parametrize("start,final", [(3.0, -12.0), (-20.0, -12.0)])
def test_ramp_rate_limited_monotone_and_stops_at_final(start, final):
    # Tinh tay: rate 2 do/s, dt = 1/30 s -> buoc 1/15 do. |final-start| = 15 do (7.5 s = 225 buoc)
    # hoac 8 do (4 s = 120 buoc). Tai k = 15 (t = 10.5 s): start -/+ 1.0 do.
    r = make_ramp(final=final, rate=2.0, dt_max=0.2)
    sgn = 1.0 if final > start else -1.0
    vals = [r.update(10.0, R(start))]
    for k in range(1, 301):
        meas = R(start + 5.0 * math.sin(0.3 * k))     # do dac doi lien tuc: sau khoi dong ramp KHONG theo
        vals.append(r.update(10.0 + k * DT, meas))
    assert vals[15] == pytest.approx(start + sgn * 1.0, abs=1e-9)
    for a, b in zip(vals, vals[1:]):
        assert abs(b - a) <= 2.0 * DT + 1e-9
        assert sgn * (b - a) >= -1e-12                 # don dieu ve phia final
        assert sgn * (final - b) >= -1e-12             # khong vuot qua final
    n_end = int(round(abs(final - start) / (2.0 * DT)))
    for v in vals[n_end + 1:]:
        assert v == pytest.approx(final, abs=1e-9)
    assert r.value == pytest.approx(final, abs=1e-9)


# =============== (3) khong khoi dong khi chua co TRACK ===============
def test_ramp_does_not_start_without_measurement():
    r = make_ramp()
    assert r.value is None
    for k in range(10):
        assert r.update(10.0 + 0.1 * k, None) is None
    assert r.value is None
    # thoi gian truoc khi khoi dong khong duoc tinh vao doc: khoi dong o dung 3.0
    assert r.update(15.0, R(3.0)) == pytest.approx(3.0, abs=1e-9)


def test_ramp_continues_and_does_not_restart_after_target_lost():
    r = make_ramp()
    r.update(10.0, R(3.0))
    assert r.update(10.1, None) == pytest.approx(2.8, abs=1e-9)      # mat muc tieu: van tien ve final
    assert r.update(10.2, R(10.0)) == pytest.approx(2.6, abs=1e-9)   # bat lai: KHONG khoi dong lai tu 10


def test_guidance_ramp_not_started_uses_old_path():
    # Ramp bat nhung chi co SEARCH: last_elev_ref_deg None, lenh y het ramp tat; TRACK dau moi khoi dong.
    g_on, g_off = Guidance(gcfg()), Guidance(gcfg(elev_ramp_enabled=False))
    for k in range(5):
        tr = track(status=TrackStatus.SEARCH, t=10.0 + k * DT)
        assert g_on.step(tr, own()) == g_off.step(tr, own())
        assert g_on.last_elev_ref_deg is None
    g_on.step(track(u=u_el(3.0), t=11.0), own())
    assert g_on.last_elev_ref_deg == pytest.approx(3.0, abs=1e-9)


# =============== (4) t lap / lui khong doi trang thai ===============
def test_ramp_repeated_or_backward_time_keeps_state():
    r = make_ramp()
    r.update(10.0, R(3.0))
    assert r.update(10.1, None) == pytest.approx(2.8, abs=1e-9)
    assert r.update(10.1, None) == pytest.approx(2.8, abs=1e-9)      # t lap
    assert r.update(10.0, None) == pytest.approx(2.8, abs=1e-9)      # t lui
    assert r.update(9.0, R(3.0)) == pytest.approx(2.8, abs=1e-9)
    # t_prev van la 10.1 (khong bi lui ve 9.0): 10.2 -> 2.8 - 2*0.1 = 2.6
    assert r.update(10.2, None) == pytest.approx(2.6, abs=1e-9)


# =============== (5) dt lon bi chan bang dt_max ===============
@pytest.mark.parametrize("dt_max,expect", [(0.2, 3.0 - 2.0 * 0.2), (0.5, 3.0 - 2.0 * 0.5)])
def test_ramp_large_dt_clamped_by_dt_max(dt_max, expect):
    r = make_ramp(dt_max=dt_max)
    r.update(10.0, R(3.0))
    assert r.update(20.0, None) == pytest.approx(expect, abs=1e-9)   # 10 s nhung chi tien rate*dt_max


# =============== (6) reset ===============
def test_ramp_reset_clears_and_restarts_from_measurement():
    r = make_ramp()
    r.update(10.0, R(3.0))
    r.update(10.1, None)
    r.reset()
    assert r.value is None
    assert r.update(10.2, None) is None
    # t_prev cung bi xoa: khoi dong lai o thoi diem som hon van dung
    assert r.update(5.0, R(-5.0)) == pytest.approx(-5.0, abs=1e-9)
    assert r.update(5.1, None) == pytest.approx(-5.2, abs=1e-9)


def test_guidance_reset_resets_ramp():
    g = Guidance(gcfg())
    for k in range(30):
        g.step(track(u=u_el(3.0), t=10.0 + k * DT), own())
    assert g.last_elev_ref_deg < 2.0
    g.reset()
    g.step(track(u=u_el(-5.0), t=20.0), own())
    assert g.last_elev_ref_deg == pytest.approx(-5.0, abs=1e-9)


# =============== (7) NaN khong lam hong ===============
def test_ramp_nan_measurement_before_start_does_not_start():
    r = make_ramp()
    assert r.update(10.0, float("nan")) is None
    assert r.update(10.05, float("inf")) is None
    assert r.update(10.1, R(3.0)) == pytest.approx(3.0, abs=1e-9)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])   # inf/-inf: lay tu ban 29 ca
def test_ramp_nan_measurement_after_start_continues_ramp(bad):
    r = make_ramp()
    r.update(10.0, R(3.0))
    assert r.update(10.1, bad) == pytest.approx(2.8, abs=1e-9)


def test_ramp_nan_time_keeps_state():
    r = make_ramp()
    r.update(10.0, R(3.0))
    assert r.update(float("nan"), R(3.0)) == pytest.approx(3.0, abs=1e-9)
    assert r.update(10.1, None) == pytest.approx(2.8, abs=1e-9)


@pytest.mark.parametrize("bad_t", [float("inf"), float("-inf")])
def test_ramp_infinite_time_keeps_state_and_next_update_advances(bad_t):
    # Tinh tay: khoi dong 3.0 o t=10; update(+-inf) khong doi gia tri (khong tien rate*dt_max = 0.4)
    # va khong doi moc t; t=10.1 -> 3 - 2*0.1 = 2.8; t=10.2 -> 2.6 (ramp khong dung im).
    r = make_ramp()
    r.update(10.0, R(3.0))
    assert r.update(bad_t, R(3.0)) == pytest.approx(3.0, abs=1e-9)
    assert r.value == pytest.approx(3.0, abs=1e-9)
    assert r.update(10.1, None) == pytest.approx(2.8, abs=1e-9)
    assert r.update(10.2, None) == pytest.approx(2.6, abs=1e-9)


def test_ramp_nan_time_before_start_never_yields_nan():
    r = make_ramp()
    out = [r.update(float("nan"), R(5.0)), r.update(10.0, R(3.0)), r.update(10.1, None)]
    for v in out:
        assert v is None or math.isfinite(v)
    assert out[1] is not None and out[2] is not None
    assert abs(out[2] - out[1]) <= 2.0 * 0.1 + 1e-9


# =============== compute_guidance_ex(elev_ref_deg=...) ===============
def test_compute_guidance_elev_ref_used_directly_without_clip():
    # Tinh tay: u=(1,0,0), tilt 0 -> err anh = 0; e_ref = -12 (KHONG cat ve -8) -> err_tong = -12 do
    # vc = 0.5*15*tan(-12 do) = -1.594174; w vuong goc u nen giu nguyen; v_t = 0, u_p = 0 (r = 15).
    # prev = (0,0,vc), prev_accel = 0 -> a_des = 0 -> v_cmd = (0,0,vc).
    # Neu bi cat -8: vc_cu = 7.5*tan(-8) = -1.054 -> a_des z = +5.4 -> sau gioi han vz = vc + 0.1*1.0 != vc.
    vc = 0.5 * 15.0 * math.tan(R(-12.0))
    cfg = GuidanceConfig(cam_tilt_up_deg=0.0)
    cmd, _ = compute_guidance_ex(track(), own(), cfg, prev_cmd(v=(0.0, 0.0, vc), dt=0.1), (0.0, 0.0, 0.0),
                                 elev_ref_deg=-12.0)
    assert cmd.vel_ned[2] == pytest.approx(-1.594174, abs=1e-6)
    assert cmd.vel_ned[0] == pytest.approx(0.0, abs=1e-9)


def test_compute_guidance_elev_ref_ignores_accel_compensation():
    # Khac None: bo cat +-elev_ref_max va bo bu gia toc -> bit-bang cau hinh target=-12, max=90, comp=0.
    kw = dict(prev=prev_cmd(v=(5.0, 0.0, -0.5), dt=0.1), prev_accel=(4.0, 0.0, 0.0))
    tr, o = track(u=u_el(1.0)), own(v=(5.0, 0.0, 0.0))
    got = compute_guidance_ex(tr, o, GuidanceConfig(cam_tilt_up_deg=0.0), elev_ref_deg=-12.0, **kw)
    ref = compute_guidance_ex(tr, o, GuidanceConfig(cam_tilt_up_deg=0.0, target_elev_ref_deg=-12.0,
                                                    elev_ref_max_deg=90.0, elev_accel_comp=0.0), **kw)
    assert got == ref


def test_compute_guidance_elev_ref_none_is_old_result():
    kw = dict(prev=prev_cmd(v=(5.0, 0.0, -0.5), dt=0.1), prev_accel=(4.0, 0.0, 0.0))
    tr, o, cfg = track(u=u_el(1.0)), own(v=(5.0, 0.0, 0.0)), GuidanceConfig(cam_tilt_up_deg=0.0)
    assert compute_guidance_ex(tr, o, cfg, elev_ref_deg=None, **kw) == compute_guidance_ex(tr, o, cfg, **kw)


# =============== (8) ramp tat -> lenh bit-bang ban cu ===============
def _scenario(g):
    """Chuoi SEARCH -> TRACK (bay, goc nang doi, co gia toc) -> LOST bay mu (step_blind) -> TRACK."""
    out = []
    t = 10.0
    for _ in range(3):
        out.append(g.step(track(status=TrackStatus.SEARCH, t=t), own(t=t)))
        t += DT
    for k in range(30):
        el = 3.0 - 5.0 * k / 29.0
        o = own(v=(4.0 + 0.05 * k, 0.3, -0.2), alt=30.0 - 0.1 * k, t=t)
        out.append(g.step(track(r=22.0 - 0.15 * k, u=u_el(el), rate=(0.0, 0.01, 0.02), rdot=-0.5, t=t), o))
        t += DT
    for k in range(10):
        out.append(g.step_blind(track(status=TrackStatus.LOST, t=t), own(v=(5.0, 0.3, -0.1), t=t)))
        t += DT
    for k in range(5):
        out.append(g.step(track(r=17.0, u=u_el(-2.0), t=t), own(v=(5.0, 0.0, 0.0), t=t)))
        t += DT
    return [(c.t, c.vel_ned, c.yaw_rad, c.valid, c.reason) for c in out]


# Ghi tu ma HIEN TAI (truoc buoc 4b), cung cau hinh GuidanceConfig(cam_tilt_up_deg=0.0) va
# GuidanceConfig() mac dinh; repr float -> so sanh bang ==.
# GHI CHU 2026-11-19 (sinh lai lan cuoi, ma Q1-Q5 da chot): buoc 0-32 (truoc COAST dau) = golden GOC (HEAD, giu nguyen);
# buoc 33-47 (10 buoc COAST+blind roi 5 buoc TRACK ke thua v_prev) duoc SINH LAI sau thay doi khong-leo-khi-COAST:
# lenh len dang co giam dan qua gioi han gia toc/jerk (khong cat cung v_prev z), kep v_t z va v_des z >= 0, vc = 0,
# lui chi theo phuong ngang, cat radial_cap chi theo phuong ngang khi khong thay muc tieu.
GOLDEN_TILT0 = [
    (10.0, (0.0, 0.0, 0.0), None, True, 'brake:no_track:search'),
    (10.033333333333333, (0.0, 0.0, 0.0), None, True, 'brake:no_track:search'),
    (10.066666666666666, (0.0, 0.0, 0.0), None, True, 'brake:no_track:search'),
    (10.1, (0.01012473531990107, 0.0013376982854133065, -0.004376881095324053), 0.009999999999999787, True, 'track'),
    (10.133333333333333, (0.030375196639637506, 0.0040055754153709355, -0.013130643196711657), 0.009999999999999787, True, 'track'),
    (10.166666666666666, (0.06075246884532685, 0.007995348032755544, -0.026261285890932573), 0.009999999999999787, True, 'track'),
    (10.2, (0.10125775702124795, 0.013297754881047459, -0.043768808067848414), 0.009999999999999787, True, 'track'),
    (10.233333333333333, (0.15189242232018968, 0.019902258672616486, -0.06565320730191239), 0.009999999999999787, True, 'track'),
    (10.266666666666666, (0.21265803370056297, 0.027796611681865008, -0.09191447877699893), 0.009999999999999787, True, 'track'),
    (10.299999999999999, (0.28266600203264175, 0.03685412236307148, -0.11211912641277688), 0.009999999999999787, True, 'track'),
    (10.333333333333332, (0.3587241159791571, 0.04666226796607096, -0.12303458272843693), 0.009999999999999787, True, 'track'),
    (10.366666666666665, (0.44083393557211514, 0.05720864269760778, -0.12466086972461268), 0.009999999999999787, True, 'track'),
    (10.399999999999999, (0.5289973117923626, 0.06847838622473548, -0.11699802436791394), 0.009999999999999787, True, 'track'),
    (10.433333333333332, (0.6232165116597216, 0.08045309863206512, -0.10004610968450181), 0.009999999999999787, True, 'track'),
    (10.466666666666665, (0.7234944443619549, 0.09310886002459985, -0.0738052381792059), 0.009999999999999787, True, 'track'),
    (10.499999999999998, (0.8298351413262022, 0.10641197519803035, -0.03827563087677044), 0.009999999999999787, True, 'track'),
    (10.533333333333331, (0.9422451195243227, 0.12030667630484491, 0.006542175471283725), 0.009999999999999787, True, 'track'),
    (10.566666666666665, (1.0580519485489006, 0.1344449032935165, 0.05654217547128355), 0.009999999999999787, True, 'track'),
    (10.599999999999998, (1.174183597647301, 0.1460280720726087, 0.09573370843896292), 0.009999999999999787, True, 'track'),
    (10.633333333333331, (1.2904764270953555, 0.1563084948160172, 0.12389194345068866), 0.009999999999999787, True, 'track'),
    (10.666666666666664, (1.4066913977657616, 0.1672098353847288, 0.1409567033897233), 0.009999999999999787, True, 'track'),
    (10.699999999999998, (1.5226690481334497, 0.18007643073209223, 0.14708810872679065), 0.009999999999999787, True, 'track'),
    (10.73333333333333, (1.6384269447463933, 0.19476883985606191, 0.142261644632993), 0.009999999999999787, True, 'track'),
    (10.766666666666664, (1.7541773892198775, 0.20949009034387917, 0.1263241093592954), 0.009999999999999787, True, 'track'),
    (10.799999999999997, (1.870189011626433, 0.22199000372818362, 0.09950290569285036), 0.009999999999999787, True, 'track'),
    (10.83333333333333, (1.9864589366143681, 0.2322755385455389, 0.06179654711422591), 0.009999999999999787, True, 'track'),
    (10.866666666666664, (2.102378027503444, 0.24547882915525102, 0.013374760093644474), 0.009999999999999787, True, 'track'),
    (10.899999999999997, (2.218595571690807, 0.2561133776470081, -0.03662523990635535), 0.009999999999999787, True, 'track'),
    (10.93333333333333, (2.3344103240739797, 0.2702048093811062, -0.08662523990635518), 0.009999999999999787, True, 'track'),
    (10.966666666666663, (2.4508722463364703, 0.27870321894091094, -0.136625239906355), 0.009999999999999787, True, 'track'),
    (10.999999999999996, (2.5664728237789567, 0.2946903619092107, -0.18662523990635482), 0.009999999999999787, True, 'track'),
    (11.03333333333333, (2.683218884926754, 0.30067499267568465, -0.23662523990635465), 0.009999999999999787, True, 'track'),
    (11.066666666666663, (2.798709090041947, 0.3176995335753447, -0.28662523990635447), 0.009999999999999787, True, 'track'),
    (11.099999999999996, (2.9130989193958303, 0.3444144077012676, -0.331301387422357), 0.0, True, 'coast+blind'),
    (11.13333333333333, (3.0263551015049988, 0.38068350708415644, -0.3704198003470751), 0.0, True, 'coast+blind'),
    (11.166666666666663, (3.1384730753014733, 0.42586562763127406, -0.4030022110008038), 0.0, True, 'coast+blind'),
    (11.199999999999996, (3.249558119551386, 0.47827666944450126, -0.4272101041159705), 0.0, True, 'coast+blind'),
    (11.233333333333329, (3.360163688179147, 0.5330764741322855, -0.4405773005201155), 0.0, True, 'coast+blind'),
    (11.266666666666662, (3.4714066638307424, 0.5827123372213759, -0.4441269509185267), 0.0, True, 'coast+blind'),
    (11.299999999999995, (3.583922129730417, 0.6237798135014649, -0.4407181312132924), 0.0, True, 'coast+blind'),
    (11.333333333333329, (3.697961915155201, 0.6552607990369155, -0.43190260869471725), 0.0, True, 'coast+blind'),
    (11.366666666666662, (3.813626643325597, 0.6768323787317393, -0.41833103454872167), 0.0, True, 'coast+blind'),
    (11.399999999999995, (3.9296987261844425, 0.6883267717230588, -0.40009671867451835), 0.0, True, 'coast+blind'),
    (11.433333333333328, (4.047597258814003, 0.6895044939941111, -0.38556202124119415), 0.0, True, 'track'),
    (11.466666666666661, (4.167263295834742, 0.6803922474722224, -0.3748285421113773), 0.0, True, 'track'),
    (11.499999999999995, (4.288606742559869, 0.6610193233872785, -0.36801444848876663), 0.0, True, 'track'),
    (11.533333333333328, (4.411503860204916, 0.6314212226442922, -0.36526097786119915), 0.0, True, 'track'),
    (11.566666666666661, (4.535793097696129, 0.5916453846019114, -0.36674218029325234), 0.0, True, 'track'),
]
GOLDEN_DEFAULT = [
    (10.0, (0.0, 0.0, 0.0), None, True, 'brake:no_track:search'),
    (10.033333333333333, (0.0, 0.0, 0.0), None, True, 'brake:no_track:search'),
    (10.066666666666666, (0.0, 0.0, 0.0), None, True, 'brake:no_track:search'),
    (10.1, (0.01012473531990107, 0.0013376982854133065, -0.004376881095324053), 0.009999999999999787, True, 'track'),
    (10.133333333333333, (0.030375196639637506, 0.0040055754153709355, -0.013130643196711657), 0.009999999999999787, True, 'track'),
    (10.166666666666666, (0.06075246884532685, 0.007995348032755544, -0.026261285890932573), 0.009999999999999787, True, 'track'),
    (10.2, (0.10125775702124795, 0.013297754881047459, -0.043768808067848414), 0.009999999999999787, True, 'track'),
    (10.233333333333333, (0.15189242232018968, 0.019902258672616486, -0.06565320730191239), 0.009999999999999787, True, 'track'),
    (10.266666666666666, (0.21265803370056297, 0.027796611681865008, -0.09191447877699893), 0.009999999999999787, True, 'track'),
    (10.299999999999999, (0.28266600203264175, 0.03685412236307148, -0.1121191264127769), 0.009999999999999787, True, 'track'),
    (10.333333333333332, (0.3587241159791571, 0.04666226796607096, -0.12303458272843694), 0.009999999999999787, True, 'track'),
    (10.366666666666665, (0.44083393557211514, 0.05720864269760778, -0.12466086972461271), 0.009999999999999787, True, 'track'),
    (10.399999999999999, (0.5289973117923626, 0.06847838622473548, -0.11699802436791398), 0.009999999999999787, True, 'track'),
    (10.433333333333332, (0.6232165116597216, 0.08045309863206512, -0.10004610968450187), 0.009999999999999787, True, 'track'),
    (10.466666666666665, (0.7234944443619549, 0.09310886002459984, -0.07380523817920595), 0.009999999999999787, True, 'track'),
    (10.499999999999998, (0.8298351413262022, 0.10641197519803033, -0.0382756308767705), 0.009999999999999787, True, 'track'),
    (10.533333333333331, (0.9422451195243227, 0.1203066763048449, 0.006542175471283655), 0.009999999999999787, True, 'track'),
    (10.566666666666665, (1.0580519485489006, 0.13444490329351647, 0.05654217547128348), 0.009999999999999787, True, 'track'),
    (10.599999999999998, (1.174183597647301, 0.1460280720726087, 0.09573370843896284), 0.009999999999999787, True, 'track'),
    (10.633333333333331, (1.2904764270953555, 0.1563084948160172, 0.12389194345068856), 0.009999999999999787, True, 'track'),
    (10.666666666666664, (1.4066913977657616, 0.16720983538472883, 0.1409567033897232), 0.009999999999999787, True, 'track'),
    (10.699999999999998, (1.5226690481334497, 0.18007643073209223, 0.1470881087267905), 0.009999999999999787, True, 'track'),
    (10.73333333333333, (1.6384269447463933, 0.19476883985606191, 0.14226164463299285), 0.009999999999999787, True, 'track'),
    (10.766666666666664, (1.7541773892198775, 0.20949009034387917, 0.1263241093592952), 0.009999999999999787, True, 'track'),
    (10.799999999999997, (1.870189011626433, 0.2219900037281836, 0.09950290569285014), 0.009999999999999787, True, 'track'),
    (10.83333333333333, (1.9864589366143681, 0.23227553854553892, 0.06179654711422566), 0.009999999999999787, True, 'track'),
    (10.866666666666664, (2.102378027503444, 0.24547882915525096, 0.013374760093644161), 0.009999999999999787, True, 'track'),
    (10.899999999999997, (2.218595571690807, 0.25611337764700814, -0.03662523990635566), 0.009999999999999787, True, 'track'),
    (10.93333333333333, (2.3344103240739797, 0.2702048093811061, -0.08662523990635548), 0.009999999999999787, True, 'track'),
    (10.966666666666663, (2.4508722463364703, 0.27870321894091105, -0.1366252399063553), 0.009999999999999787, True, 'track'),
    (10.999999999999996, (2.5664728237789567, 0.29469036190921055, -0.18662523990635513), 0.009999999999999787, True, 'track'),
    (11.03333333333333, (2.683218884926754, 0.3006749926756848, -0.23662523990635495), 0.009999999999999787, True, 'track'),
    (11.066666666666663, (2.798709090041947, 0.3176995335753452, -0.2866252399063548), 0.009999999999999787, True, 'track'),
    (11.099999999999996, (2.9130989193958303, 0.3444144077012684, -0.3313013874223573), 0.0, True, 'coast+blind'),
    (11.13333333333333, (3.0263551015049988, 0.38068350708415755, -0.3704198003470754), 0.0, True, 'coast+blind'),
    (11.166666666666663, (3.1384730753014733, 0.42586562763127545, -0.40300221100080397), 0.0, True, 'coast+blind'),
    (11.199999999999996, (3.2495581195513856, 0.4782766694445028, -0.42721010411597043), 0.0, True, 'coast+blind'),
    (11.233333333333329, (3.3601636881791466, 0.5330764741322869, -0.4405773005201152), 0.0, True, 'coast+blind'),
    (11.266666666666662, (3.471406663830742, 0.5827123372213769, -0.4441269509185262), 0.0, True, 'coast+blind'),
    (11.299999999999995, (3.5839221297304165, 0.6237798135014655, -0.4407181312132918), 0.0, True, 'coast+blind'),
    (11.333333333333329, (3.6979619151552003, 0.6552607990369156, -0.4319026086947166), 0.0, True, 'coast+blind'),
    (11.366666666666662, (3.8136266433255965, 0.676832378731739, -0.41833103454872095), 0.0, True, 'coast+blind'),
    (11.399999999999995, (3.929698726184442, 0.688326771723058, -0.40009671867451757), 0.0, True, 'coast+blind'),
    (11.433333333333328, (4.047597258814003, 0.6895044939941098, -0.3855620212411933), 0.0, True, 'track'),
    (11.466666666666661, (4.167263295834742, 0.6803922474722207, -0.37482854211137634), 0.0, True, 'track'),
    (11.499999999999995, (4.288606742559869, 0.6610193233872765, -0.36801444848876563), 0.0, True, 'track'),
    (11.533333333333328, (4.411503860204917, 0.6314212226442899, -0.3652609778611981), 0.0, True, 'track'),
    (11.566666666666661, (4.53579309769613, 0.5916453846019086, -0.36674218029325123), 0.0, True, 'track'),
]


@pytest.mark.parametrize("cfg_kw,golden_name", [({"cam_tilt_up_deg": 0.0}, "GOLDEN_TILT0"),
                                                 ({}, "GOLDEN_DEFAULT")])
def test_ramp_disabled_commands_bit_equal_old(cfg_kw, golden_name):
    golden = globals()[golden_name]
    got = _scenario(Guidance(GuidanceConfig(**cfg_kw)))
    assert len(got) == len(golden)
    # So abs=1e-12 cho so (golden nhay voi sai so libm tan/atan2), == cho valid/reason/yaw None.
    for i, (a, b) in enumerate(zip(got, golden)):
        assert a[0] == pytest.approx(b[0], abs=1e-12), f"buoc {i} t"
        assert a[1] == pytest.approx(b[1], abs=1e-12), f"buoc {i} vel: {a[1]} != {b[1]}"
        if b[2] is None:
            assert a[2] is None, f"buoc {i} yaw"
        else:
            assert a[2] == pytest.approx(b[2], abs=1e-12), f"buoc {i} yaw"
        assert (a[3], a[4]) == (b[3], b[4]), f"buoc {i}: {a[3:]} != {b[3:]}"


def test_ramp_disabled_last_elev_ref_is_none():
    g = Guidance(GuidanceConfig(cam_tilt_up_deg=0.0))
    g.step(track(u=u_el(3.0)), own())
    assert g.last_elev_ref_deg is None


# =============== (9) ramp bat: dau van toc dung, gioi han leo ===============
def _run_fixed(cfg, el_deg, n=300):
    g = Guidance(cfg)
    vz, refs = [], []
    for k in range(n):
        t = 10.0 + k * DT
        vz.append(g.step(track(u=u_el(el_deg), t=t), own(t=t)).vel_ned[2])
        refs.append(g.last_elev_ref_deg)
    return vz, refs


def test_guidance_ramp_climbs_when_target_above_ref():
    # elev_los = 0 > e_ref (doc 0 -> -12 trong 6 s): drone phai LEN (vel_ned[2] < 0, NED).
    # Tinh tay on dinh: vc = 0.5*15*tan(-12 do) = -1.594174 (< climb_max 4, < vert_center_max 2.5).
    # Ghi chu: design ghi "(9) elev_los > e_ref thi van toc dung duong (xuong)" -- trai voi
    # test_guidance.py:235-241 va guidance.py:179-182; test nay theo dau cua ma (LEN).
    vz, refs = _run_fixed(gcfg(), 0.0)
    assert refs[-1] == pytest.approx(-12.0, abs=1e-9)
    assert all(v <= 1e-9 for v in vz)
    assert vz[-1] == pytest.approx(-1.594174, abs=1e-4)


def test_guidance_ramp_descends_when_target_below_ref():
    # elev_los = -20 < e_ref (doc -20 -> -12 trong 4 s): drone XUONG.
    # Tinh tay on dinh: err anh = +20, err_tong = 20 + (-12) = 8 do; vc = 7.5*tan(8) = 1.054063;
    # bo thanh phan doc u (u_z = sin20): vz = vc*cos^2(20) = 0.930755.
    vz, refs = _run_fixed(gcfg(), -20.0)
    assert refs[-1] == pytest.approx(-12.0, abs=1e-9)
    assert all(v >= -1e-9 for v in vz)
    assert vz[-1] == pytest.approx(0.930755, abs=1e-4)


def test_guidance_ramp_climb_command_within_climb_max():
    # climb_max 1.0 < 1.594: lenh leo bi cat dung -1.0 (guidance.py:272), khong buoc nao vuot.
    vz, refs = _run_fixed(gcfg(climb_max_mps=1.0), 0.0)
    assert min(vz) >= -1.0 - 1e-9
    assert vz[-1] == pytest.approx(-1.0, abs=1e-6)


def test_guidance_step_passes_ramp_value_to_compute():
    cfg = gcfg()
    g = Guidance(cfg)
    g.step(track(u=u_el(3.0), t=10.0), own())
    prev, pa = g.prev, g.prev_accel
    tr2 = track(u=u_el(3.0), t=10.1)
    c2 = g.step(tr2, own(t=10.1))
    assert g.last_elev_ref_deg == pytest.approx(2.8, abs=1e-9)        # 3 - 2*0.1
    exp, _ = compute_guidance_ex(tr2, own(t=10.1), cfg, prev, pa, None, {}, elev_ref_deg=2.8)
    assert c2.vel_ned == pytest.approx(exp.vel_ned, abs=1e-9)


# =============== (10) step_blind van dung ramp ===============
def test_step_blind_advances_and_uses_ramp():
    cfg = gcfg()
    g = Guidance(cfg)
    g.step(track(u=u_el(3.0), t=10.0), own())
    g.step(track(u=u_el(3.0), t=10.1), own(t=10.1))
    assert g.last_elev_ref_deg == pytest.approx(2.8, abs=1e-9)
    for t, exp_ref in ((10.2, 2.6), (10.3, 2.4)):
        prev, pa = g.prev, g.prev_accel
        c = g.step_blind(track(status=TrackStatus.LOST, t=t), own(t=t))
        assert c.reason.endswith("+blind")
        assert g.last_elev_ref_deg == pytest.approx(exp_ref, abs=1e-9)
        # Tinh lai lenh mu: v_own = 0 -> v_t nho duoc = 0 -> v_t_hold = (0,0,0); u nho = u_el(3), r = 15.
        synth = TrackState(t=t, status=TrackStatus.COAST, los_ned=u_el(3.0), los_rate_ned=(0.0, 0.0, 0.0),
                           range_m=15.0, range_rate_mps=0.0, range_valid=True)
        exp, _ = compute_guidance_ex(synth, own(t=t), cfg, prev, pa, v_t_hold=(0.0, 0.0, 0.0),
                                     elev_ref_deg=exp_ref)
        assert c.vel_ned == pytest.approx(exp.vel_ned, abs=1e-9)


# =============== Guidance dung dung tham so cfg (rate, final, dt_max) ===============
def test_guidance_ramp_uses_cfg_rate_and_final():
    # Tinh tay: rate 4 do/s, final -10. Khoi dong 3 (t=10); t=10.1 -> 3 - 0.4 = 2.6;
    # 13 do / 4 do/s = 3.25 s -> sau t = 13.25 dung o -10 (khong phai -12).
    g = Guidance(gcfg(elev_ramp_dps=4.0, target_elev_ref_deg=-10.0))
    g.step(track(u=u_el(3.0), t=10.0), own())
    g.step(track(u=u_el(3.0), t=10.1), own(t=10.1))
    assert g.last_elev_ref_deg == pytest.approx(2.6, abs=1e-9)
    for k in range(1, 41):
        t = 10.1 + 0.1 * k
        g.step(track(u=u_el(3.0), t=t), own(t=t))
    assert g.last_elev_ref_deg == pytest.approx(-10.0, abs=1e-9)


@pytest.mark.parametrize("dt_max,expect", [(0.2, 3.0 - 2.0 * 0.2), (0.5, 3.0 - 2.0 * 0.5)])
def test_guidance_ramp_time_jump_clamped_by_cfg_dt_max(dt_max, expect):
    # t nhay 1 s giua hai lan step: buoc = rate * min(1, cfg.dt_max_s).
    g = Guidance(gcfg(dt_max_s=dt_max))
    g.step(track(u=u_el(3.0), t=10.0), own())
    g.step(track(u=u_el(3.0), t=11.0), own(t=11.0))
    assert g.last_elev_ref_deg == pytest.approx(expect, abs=1e-9)


# =============== Guidance: trang thai khac TRACK sau khi da khoi dong ===============
def test_guidance_ramp_advances_through_search_lost_coast_without_restart():
    g = Guidance(gcfg())
    g.step(track(u=u_el(3.0), t=10.0), own())
    steps = [(track(status=TrackStatus.SEARCH, t=10.1), 2.8),
             (track(status=TrackStatus.LOST, t=10.2), 2.6),
             (track(status=TrackStatus.COAST, u=u_el(3.0), t=10.3), 2.4),
             (track(u=u_el(10.0), t=10.4), 2.2)]            # TRACK lai o +10 do: KHONG khoi dong lai
    for tr, exp in steps:
        g.step(tr, own(t=tr.t))
        assert g.last_elev_ref_deg == pytest.approx(exp, abs=1e-9), tr.status


# =============== Guidance: chua khoi dong ===============
def test_guidance_coast_before_lock_does_not_start_ramp():
    g_on, g_off = Guidance(gcfg()), Guidance(gcfg(elev_ramp_enabled=False))
    for k in range(3):
        tr = track(status=TrackStatus.COAST, u=u_el(3.0), t=10.0 + k * DT)
        assert g_on.step(tr, own(t=tr.t)) == g_off.step(tr, own(t=tr.t))
        assert g_on.last_elev_ref_deg is None


@pytest.mark.parametrize("bad", [None, (0.0, 0.0, 0.0), (float("nan"), 0.0, 0.0)])
def test_guidance_track_with_bad_los_does_not_start_ramp(bad):
    g_on, g_off = Guidance(gcfg()), Guidance(gcfg(elev_ramp_enabled=False))
    tr = track(u=bad, t=10.0)
    assert g_on.step(tr, own()) == g_off.step(tr, own())
    assert g_on.last_elev_ref_deg is None
    g_on.step(track(u=u_el(3.0), t=10.1), own(t=10.1))
    assert g_on.last_elev_ref_deg == pytest.approx(3.0, abs=1e-9)


def test_guidance_reset_sets_last_elev_ref_none():
    g = Guidance(gcfg())
    g.step(track(u=u_el(3.0), t=10.0), own())
    assert g.last_elev_ref_deg is not None
    g.reset()
    assert g.last_elev_ref_deg is None


# =============== Ca lay them tu ban 29 ca (hanh vi ban 36 ca chua khoa) ===============
def test_ramp_start_equal_to_final_stays_put():
    r = make_ramp(final=-12.0)
    r.update(10.0, R(-12.0))
    assert r.update(11.0, R(-12.0)) == pytest.approx(-12.0, abs=1e-9)


@pytest.mark.parametrize("e_ref", [5.0, -3.0])
def test_compute_guidance_elev_ref_positive_and_small_used_directly(e_ref):
    # Nhu test_compute_guidance_elev_ref_used_directly_without_clip, them e_ref duong va trong +-8:
    # vz = 0.5*15*tan(e_ref): 5 -> +0.656168 (XUONG), -3 -> -0.393062 (LEN).
    vc = 0.5 * 15.0 * math.tan(R(e_ref))
    cmd, _ = compute_guidance_ex(track(), own(), GuidanceConfig(cam_tilt_up_deg=0.0),
                                 prev_cmd(v=(0.0, 0.0, vc), dt=0.1), (0.0, 0.0, 0.0), elev_ref_deg=e_ref)
    assert cmd.vel_ned[2] == pytest.approx(vc, abs=1e-6)


def _sequence_coast(cfg):
    """150 buoc: 100 TRACK, 20 COAST qua step(), 30 step_blind; doi theo sin (khong rng). Tu ban 29 ca."""
    g = Guidance(cfg)
    out = []
    for i in range(150):
        t = 10.0 + i / 30.0
        el = math.radians(6.0 * math.sin(0.04 * i))
        az = 0.1 * math.sin(0.03 * i)
        u = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), -math.sin(el))
        o = OwnState(t=t, pos_ned=(0.1 * i, 0.0, -30.0),
                     vel_ned=(6.0 + math.sin(0.1 * i), 0.5, 0.2 * math.cos(0.07 * i)),
                     q_world_body=Q0, armed=True, mode="GUIDED")
        r = 22.0 + 3.0 * math.sin(0.05 * i)
        if i < 100:
            c = g.step(track(r=r, u=u, t=t, rdot=0.5 * math.cos(0.05 * i)), o)
        elif i < 120:
            c = g.step(track(r=r, u=u, t=t, status=TrackStatus.COAST), o)
        else:
            c = g.step_blind(TrackState(t=t, status=TrackStatus.LOST), o)
        out.append((c.vel_ned[0], c.vel_ned[1], c.vel_ned[2], c.yaw_rad, c.reason))
    return out


# Ghi tu chuoi tren voi GuidanceConfig() mac dinh. Lich su: ban 29 ca da khoa CA chuoi 150 buoc bang sha256 ghi tu ma
# TRUOC 4b (8b1faa0b...). Sha do chi con dung cho buoc 0-99 (TRACK, giu nguyen ban cu); no KHONG con ung voi ca chuoi
# vi buoc 100-149 (COAST + blind) da duoc SINH LAI ngay 2026-11-19 (lan cuoi, ma Q1-Q5 da chot) sau thay doi
# khong-leo-khi-COAST. Khong dung sha do de kiem chuoi nay nua.
GOLDEN_COAST_SEQ = [
    (6.005953179771873, 0.49088427641005894, 0.2022181127471378, 0.0, 'track'),
    (6.018019397422675, 0.4727792040735945, 0.20673386931514995, 0.002999550020249764, 'track'),
    (6.036686997760675, 0.446103574096027, 0.21378420246735624, 0.005996400647944267, 'track'),
    (6.063250455580825, 0.4116630187204235, 0.22173905665745625, 0.00898785491980103, 'track'),
    (6.098617509894068, 0.37302781886672, 0.22436864685291985, 0.011971220728892007, 'track'),
    (6.143159698192017, 0.3366565274526653, 0.22115457166926916, 0.014943813247359827, 'track'),
    (6.194440286808924, 0.3078844951304944, 0.21343472102302227, 0.017902957342582404, 'track'),
    (6.250455109293936, 0.28861176027507585, 0.20242744472077995, 0.020845989984609847, 'track'),
    (6.31016610234035, 0.27948106333335176, 0.18878688524696374, 0.023770262642713647, 'track'),
    (6.373080285955667, 0.2807343086535285, 0.1728289774168913, 0.02667314366888318, 'track'),
    (6.439041588984751, 0.2924397310541045, 0.1546520951206134, 0.029552020666133938, 'track'),
    (6.50819439905207, 0.3145325688058742, 0.1341573096188198, 0.03240430283948692, 'track'),
    (6.581126319598901, 0.3467185127026754, 0.11095987311250805, 0.035227423327508944, 'track'),
    (6.659477093517972, 0.3878541584526075, 0.08402135989037045, 0.03801884151231594, 'track'),
    (6.74701024828153, 0.4309644555028089, 0.0511463978650689, 0.04077604530595691, 'track'),
    (6.8405567317874025, 0.46541707664855136, 0.014758414989607636, 0.04349655341112291, 'track'),
    (6.938018295158603, 0.48968213883386147, -0.023713454206955482, 0.04617791755414835, 'track'),
    (7.038775436505851, 0.5034662340659862, -0.06384221436356317, 0.04881772468829082, 'track'),
    (7.142822185869212, 0.5067659262585061, -0.10561796029027024, 0.0514135991653113, 'track'),
    (7.251008113010633, 0.49999640782880145, -0.1496151910560754, 0.0539632048733969, 'track'),
    (7.368278087108961, 0.49526480095086123, -0.19961519105607523, 0.056464247339503615, 'track'),
    (7.484793943490899, 0.5016186844361518, -0.24961519105607505, 0.05891447579422682, 'track'),
    (7.600561688974206, 0.5190584652783009, -0.29961519105607487, 0.0613116851973432, 'track'),
    (7.715558797151706, 0.5475826003310656, -0.34961519105607736, 0.06365371822219679, 'track'),
    (7.83108733914213, 0.5677538139237078, -0.3996151910560772, 0.06593846719714724, 'track'),
    (7.946766801235948, 0.5855940528575213, -0.449615191056077, 0.06816387600233353, 'track'),
    (8.062340807683812, 0.6047146689952383, -0.4996151910560768, 0.07032794192004088, 'track'),
    (8.177862797819266, 0.624345182361355, -0.5496151910560767, 0.07242871743701418, 'track'),
    (8.293322568689687, 0.6446005022391428, -0.5996151910560765, 0.07446431199708581, 'track'),
    (8.408722126352524, 0.6654300607531919, -0.6496151910560763, 0.07643289370255069, 'track'),
    (8.513131946575498, 0.6859328593642589, -0.6996151910560762, 0.07833269096274842, 'track'),
    (8.606453390789822, 0.7057252302068334, -0.749615191056076, 0.08016199408837776, 'track'),
    (8.68868843908959, 0.724776915050372, -0.7996151910560758, 0.08191915683009965, 'track'),
    (8.759841887492067, 0.7430193200660444, -0.8496151910560756, 0.08360259786005209, 'track'),
    (8.819912715255539, 0.7604665459224226, -0.8996151910560755, 0.08521080219493626, 'track'),
    (8.868899702437826, 0.7771357820010221, -0.9496151910560753, 0.08674232255940151, 'track'),
    (8.906802269134255, 0.7930353346277083, -0.9996151910560751, 0.08819578068849498, 'track'),
    (8.933621991875599, 0.8081428266565485, -1.0496151910560776, 0.08956986856800464, 'track'),
    (8.94936414669621, 0.8223876025762069, -1.0996151910560747, 0.09086334961158826, 'track'),
    (8.954040102072694, 0.8356343704867444, -1.1496151910560772, 0.09207505977361352, 'track'),
    (8.949718210072364, 0.8478927808020157, -1.193171691853711, 0.09320390859672267, 'track'),
    (8.937476062455893, 0.8590600533069177, -1.229012250753091, 0.09424888019316979, 'track'),
    (8.91734947247935, 0.8688503858410956, -1.2571459039756667, 0.09520903415905169, 'track'),
    (8.889390496387987, 0.8769121563276668, -1.2775904355891479, 0.09608350642060737, 'track'),
    (8.853670079287147, 0.8828398333538854, -1.2903758243862096, 0.0968715100118267, 'track'),
    (8.810277951428926, 0.8861960301834021, -1.2955461535133461, 0.09757233578266611, 'track'),
    (8.75931815001874, 0.8865419893471592, -1.293158336285061, 0.09818535303723586, 'track'),
    (8.700896340538694, 0.8834837753127509, -1.2832747315380608, 0.09871001010138514, 'track'),
    (8.635096531398478, 0.8767358045293242, -1.2659474982222079, 0.0991458348191685, 'track'),
    (8.561945386896992, 0.8662112920613474, -1.2411937992978397, 0.09949243497775795, 'track'),
    (8.481364882254567, 0.8521675066337463, -1.208965067540411, 0.0997494986604055, 'track'),
    (8.39312771803226, 0.8354796611213278, -1.1691309889487405, 0.09991679452714752, 'track'),
    (8.296911080886659, 0.8182164235234337, -1.1215862861321446, 0.09999417202299643, 'track'),
    (8.197982695369658, 0.8024310761586696, -1.0715862861321475, 0.09998156151342918, 'track'),
    (8.099120645936697, 0.7859228713712518, -1.021586286132145, 0.09987897434705229, 'track'),
    (8.00033340489616, 0.7685845700145358, -0.9715862861321451, 0.09968650284539171, 'track'),
    (7.901606438927066, 0.7505409113654506, -0.9215862861321453, 0.09940432021980783, 'track'),
    (7.802922470456463, 0.73194725738065, -0.8715862861321455, 0.09903268041561564, 'track'),
    (7.709889302884736, 0.7134899293825728, -0.8215862861321457, 0.09857191788355557, 'track'),
    (7.627933342282812, 0.6958999397680679, -0.7715862861321459, 0.09802244727880449, 'track'),
    (7.55705307512237, 0.6791964065336331, -0.721586286132146, 0.09738476308781951, 'track'),
    (7.497244541851221, 0.6634274848806332, -0.6715862861321462, 0.09665943918332998, 'track'),
    (7.448506116446788, 0.6486122413403668, -0.6215862861321464, 0.09584712830789144, 'track'),
    (7.4108372357862535, 0.6347571901174532, -0.5715862861321466, 0.09494856148646313, 'track'),
    (7.384235810270511, 0.6218861240272924, -0.5215862861321467, 0.09396454736853244, 'track'),
    (7.368697764668704, 0.6100438509208473, -0.4715862861321469, 0.09289597150038675, 'track'),
    (7.364217351629021, 0.5992904084920277, -0.4215862861321471, 0.0917437955281808, 'track'),
    (7.370786270126529, 0.5897070355930694, -0.3715862861321446, 0.09050905633251993, 'track'),
    (7.3883924469613325, 0.5814026148117513, -0.32158628613214746, 0.08919286509533819, 'track'),
    (7.417019579599539, 0.5745107531629884, -0.27158628613214497, 0.08779640629990793, 'track'),
    (7.452570095030725, 0.5686037578170505, -0.23022072874246247, 0.0863209366648876, 'track'),
    (7.495038257875542, 0.5638026228934885, -0.197479556380732, 0.08476778401335716, 'track'),
    (7.544347506290241, 0.5602370321834139, -0.17340612702658575, 0.08313834607786852, 'track'),
    (7.600325094413099, 0.558034718835177, -0.15811515236886337, 0.08143408924257978, 'track'),
    (7.662654523591007, 0.5573044720382208, -0.15182106191643416, 0.0796565472236086, 'track'),
    (7.730778338294663, 0.5581078012579047, -0.1548827200232402, 0.07780731968879229, 'track'),
    (7.803676075716356, 0.5604053665910734, -0.16786575456896985, 0.07588807081809223, 'track'),
    (7.879319471734646, 0.5639373629107151, -0.1915443175791571, 0.07390052780594702, 'track'),
    (7.953281243739226, 0.5679436710772299, -0.22619575437299305, 0.07184647930691268, 'track'),
    (8.019164702914303, 0.5712489981274477, -0.2684436559647949, 0.06972777382599382, 'track'),
    (8.074400157059547, 0.5736249402664265, -0.31372685370275416, 0.06754631805511524, 'track'),
    (8.118574460044881, 0.5752528846373857, -0.35975047326651544, 0.06530407515722647, 'track'),
    (8.155133262640788, 0.5764512960399728, -0.3976947088580229, 0.06300306299958924, 'track'),
    (8.183366307390227, 0.5772949946068738, -0.42828960943133265, 0.060645352337831415, 'track'),
    (8.202799227025912, 0.5778985070881245, -0.45210535823248527, 0.05823306495240832, 'track'),
    (8.213082069674728, 0.5783955517475222, -0.4696186038911715, 0.05576837173914173, 'track'),
    (8.213944128855374, 0.5789225873230337, -0.4812407775324537, 0.05325349075556218, 'track'),
    (8.205315074028, 0.5796508579440596, -0.48708929986224553, 0.05069068522480524, 'track'),
    (8.187195374176177, 0.5807522077146114, -0.4871719519982569, 0.04808226149886474, 'track'),
    (8.159586798282556, 0.5823556878558724, -0.48149562100547855, 0.04543056698303083, 'track'),
    (8.122489832514168, 0.5844941735088848, -0.4700624665126892, 0.04273798802338291, 'track'),
    (8.075902109781586, 0.5870471029908606, -0.452866451733318, 0.04000694775924174, 'track'),
    (8.019822948876739, 0.5897193544569276, -0.4298950448625264, 0.03723990394250576, 'track'),
    (7.954267178141054, 0.5920035908105601, -0.4011357108575992, 0.03443934672583904, 'track'),
    (7.879291959505265, 0.5931644589252221, -0.3665911512580783, 0.03160779642170519, 'track'),
    (7.795027857489949, 0.5922880027780227, -0.32630004960815473, 0.028747801234254577, 'track'),
    (7.701664084877247, 0.5884976076094881, -0.28033781539740776, 0.02586193496611111, 'track'),
    (7.601815413411683, 0.5827021454312064, -0.23033781539740528, 0.02295279470212641, 'track'),
    (7.501893473280334, 0.5778567541730755, -0.18033781539740812, 0.020022998472176923, 'track'),
    (7.402007356440643, 0.5725325820347535, -0.13033781539740563, 0.017075182895114782, 'track'),
    (5.477342301257212, 0.5525454890334629, -0.08033781539740581, 0.014112000805986735, 'coast'),
    (5.38288506628386, 0.5491375511968869, -0.030337815397405987, 0.011136118868665168, 'coast'),
    (5.295022615505105, 0.5367872640297299, 0.019662184602593835, 0.008150215176026876, 'coast'),
    (5.214375268999761, 0.5159871803888543, 0.06966218460259366, 0.005156976839853389, 'coast'),
    (5.142482459015721, 0.48834495670113676, 0.11966218460259348, 0.0021590975726097916, 'coast'),
    (5.080093623907935, 0.45787135548677566, 0.16465074239733812, -0.0008407247367148152, 'coast'),
    (5.025415237117381, 0.4270364683873887, 0.20164710090903, -0.003839790450523406, 'coast'),
    (4.978302562716821, 0.39693685490251907, 0.2305393765690265, -0.006835400612104969, 'coast'),
    (4.93877091868562, 0.3700534067112325, 0.25197235940284507, -0.00982485937451072, 'coast'),
    (4.906601854811682, 0.3482626167930484, 0.26682400230738434, -0.012805476426637874, 'coast'),
    (4.881531009392575, 0.33275371287621797, 0.27587823258585, -0.01577456941432498, 'coast'),
    (4.863458631620003, 0.32408967102665187, 0.2796764088307301, -0.01872946635429029, 'coast'),
    (4.852473797513491, 0.3224296874898288, 0.2785586231090304, -0.02166750803873807, 'coast'),
    (4.848697648889175, 0.3278367800729591, 0.27279884655827874, -0.024586050428463846, 'coast'),
    (4.852668383203598, 0.33973941841455374, 0.26242924569887316, -0.027482467032312385, 'coast'),
    (4.865209564589387, 0.3569305739856341, 0.247365412992424, -0.030354151270842955, 'coast'),
    (4.887270677852454, 0.3772897047838247, 0.2275275232968052, -0.033198518822073364, 'coast'),
    (4.91943727743502, 0.3978128481736808, 0.20307346243455318, -0.03601300994719692, 'coast'),
    (4.961525154879148, 0.41549684734115094, 0.17450062799250488, -0.038795091794173064, 'coast'),
    (5.0134262213115734, 0.4280411472481047, 0.1450666295040359, -0.04154226067712452, 'coast'),
    (5.073909698546766, 0.4349713029841394, 0.11990818947782138, 0.010817616882705217, 'coast+blind'),
    (5.141457493815449, 0.4372593186295264, 0.10196104172303419, 0.017075182895114782, 'coast+blind'),
    (5.2151430029186265, 0.4362536953349526, 0.09267052157618334, 0.017075182895114782, 'coast+blind'),
    (5.294615834406766, 0.43348869364166404, 0.09270031673441216, 0.017075182895114782, 'coast+blind'),
    (5.3800903875756685, 0.43087866650067913, 0.1020795562546476, 0.017075182895114782, 'coast+blind'),
    (5.47256446331631, 0.43126087693357523, 0.11955261985208683, 0.017075182895114782, 'coast+blind'),
    (5.573470157455163, 0.43865760027431944, 0.13880366263270966, 0.017075182895114782, 'coast+blind'),
    (5.67785772065447, 0.4509139470956096, 0.1486889466295122, 0.017075182895114782, 'coast+blind'),
    (5.777588610529218, 0.46252573270442315, 0.14850662294051004, 0.017075182895114782, 'coast+blind'),
    (5.8677352068213215, 0.4708643810328167, 0.14375432343226485, 0.017075182895114782, 'coast+blind'),
    (5.947004479989534, 0.4771169946738514, 0.13989033190283892, 0.017075182895114782, 'coast+blind'),
    (6.015340135219016, 0.48208340859139437, 0.13752916410374524, 0.017075182895114782, 'coast+blind'),
    (6.072629881820499, 0.486110593545226, 0.13591802407693346, 0.017075182895114782, 'coast+blind'),
    (6.1188639701717715, 0.48927270372972625, 0.13500032216664404, 0.017075182895114782, 'coast+blind'),
    (6.154038250752086, 0.49161962238973966, 0.13477030112079985, 0.017075182895114782, 'coast+blind'),
    (6.178147315304075, 0.49318933762659745, 0.13518350570332088, 0.017075182895114782, 'coast+blind'),
    (6.19118444774105, 0.4940083947536235, 0.13614954097068765, 0.017075182895114782, 'coast+blind'),
    (6.193142724728174, 0.4940909481243729, 0.1375318865331014, 0.017075182895114782, 'coast+blind'),
    (6.184016840553347, 0.4934374266269734, 0.13915162469820447, 0.017075182895114782, 'coast+blind'),
    (6.163805267306793, 0.4920330934968355, 0.14079523377864891, 0.017075182895114782, 'coast+blind'),
    (6.132512160973335, 0.4898466132379437, 0.1422275126994673, 0.017075182895114782, 'coast+blind'),
    (6.090148166386907, 0.4868286661796951, 0.14321158812281218, 0.017075182895114782, 'coast+blind'),
    (6.036729007650427, 0.48291056300388946, 0.14354003049100275, 0.017075182895114782, 'coast+blind'),
    (5.972270461023715, 0.4780026043717754, 0.1430881579817729, 0.017075182895114782, 'coast+blind'),
    (5.896778020422898, 0.4719911932480395, 0.14193459715813578, 0.017075182895114782, 'coast+blind'),
    (5.811256147812311, 0.4648428952279493, 0.14095914154416778, 0.017075182895114782, 'coast+blind'),
    (5.7327764282602764, 0.45855260922702096, 0.14095914154416778, 0.017075182895114782, 'coast+blind'),
    (5.660965639284766, 0.4528081777708319, 0.14095914154416778, 0.017075182895114782, 'coast+blind'),
    (5.595375163897719, 0.44756172764645463, 0.14095914154416778, 0.017075182895114782, 'coast+blind'),
    (5.535498485997731, 0.44277232386065446, 0.14095914154416778, 0.017075182895114782, 'coast+blind'),
]


def test_ramp_disabled_sequence_with_coast_equals_old():
    got = _sequence_coast(GuidanceConfig())
    assert len(got) == len(GOLDEN_COAST_SEQ)
    for i, (a, b) in enumerate(zip(got, GOLDEN_COAST_SEQ)):
        assert a[:4] == pytest.approx(b[:4], abs=1e-12), f"buoc {i}: {a} != {b}"
        assert a[4] == b[4], f"buoc {i}"


def test_ramp_explicit_flag_false_equals_default():
    assert _sequence_coast(GuidanceConfig(elev_ramp_enabled=False)) == _sequence_coast(GuidanceConfig())
