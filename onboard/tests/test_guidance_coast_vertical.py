"""Test hoi quy (pha do TDD): khi KHONG thay muc tieu (COAST that / step_blind) lenh dan duong KHONG lam drone leo cao.

Hinh hoc: drone cao hon muc tieu, LOS cheo xuong 12..40 do, ho so accept_plane_r15 (giu 15 m, lui duoi 10 m).
He NED: vel_ned[2] am = di LEN. "Len" o day = max(0, -vel_ned[2]).
Muc tieu dung yen, drone dung yen (vong ho), nen moi thanh phan dung cua lenh deu do bo dan duong sinh ra.

Hanh vi dich (quyet dinh truong phong, vong sua 2):
  Q1 khong cat cung v_prev z: lenh len dang co giam dan ve 0 qua bo gioi han gia toc (a_max_z), khong nhay.
     Tich phan len <= 1.0 m + v0^2/(2*a_max_z), v0 = lenh len o chu ky cuoi truoc COAST (se trinh nguoi dung;
     phan v0 giam dan khong tranh duoc). Mot so hang jerk nho (v0*a_max_z/jerk) duoc phep: bo gioi han jerk
     lam gia toc z len dan tu 0, nen quang giam toc dai hon v0^2/(2a) mot chut.
  Q2 min_alt/low_alt thang: duoi min_alt khi COAST va step_blind, lenh len van tich luy nhu ban goc.
  Q3 |dvz|/dt <= a_max_z o chu ky vao COAST va COAST -> TRACK.
  Q4 lui luc qua gan khi mat hinh: chi theo phuong ngang, do lon LIEN TUC theo thanh phan ngang cua LOS,
     ve 0 khi LOS thang dung.
  Q5 cac thay doi chi ap khi KHONG thay muc tieu; TRACK co khoang cach khong tin cay (step() chuyen sang
     duong nho) van giu vc va hanh vi dung nhu ban goc.
"""
import copy
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dtrack.config import load_profile
from dtrack.guidance import Guidance
from dtrack.types import OwnState, TrackState, TrackStatus

DT = 1.0 / 30.0
Q0 = (1.0, 0.0, 0.0, 0.0)
ANGLES_DEG = (12.0, 25.0, 40.0)        # muc tieu thap hon drone bay nhieu do
COAST_S = 3.5
R_SET = 15.0
R_NEAR = 9.0                            # < range_back_m = 10 cua ho so
FALSE_RATE_Y = 0.4                      # rad/s quanh truc y: omega x u co thanh phan z am (len) khi u co thanh phan ngang
AZ = load_profile("accept_plane_r15").guidance.a_max_z_mps2
JERK = load_profile("accept_plane_r15").guidance.jerk_max_mps3
STEP_Z = AZ * DT + 1e-9                 # |dvz| toi da moi chu ky (cong sai so so)


def make_cfg(**over):
    cfg = load_profile("accept_plane_r15").guidance
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def los_down(angle_deg):
    a = math.radians(angle_deg)
    return (math.cos(a), 0.0, math.sin(a))      # NED: z duong = xuong


def los_uh(uh):
    """LOS gan thang dung xuong voi thanh phan ngang uh."""
    return (uh, 0.0, math.sqrt(1.0 - uh * uh))


def own(t, alt=30.0):
    return OwnState(t=t, pos_ned=(0.0, 0.0, -alt), vel_ned=(0.0, 0.0, 0.0), q_world_body=Q0,
                    armed=True, mode="GUIDED")


def trk(t, u, r, status=TrackStatus.TRACK, rate=(0.0, 0.0, 0.0), valid=True):
    return TrackState(t=t, status=status, los_ned=u, los_rate_ned=rate, range_m=r, range_sigma_m=1.0,
                      range_rate_mps=0.0, range_valid=valid)


def warm(g, u, r, n_clean=60, n_false=0, t0=10.0, alt=30.0):
    """TRACK hop le n_clean chu ky (rate 0) roi n_false chu ky voi los_rate gia; tra ve thoi diem ke tiep."""
    t = t0
    for _ in range(n_clean):
        g.step(trk(t, u, r), own(t, alt))
        t += DT
    for _ in range(n_false):
        g.step(trk(t, u, r, rate=(0.0, FALSE_RATE_Y, 0.0)), own(t, alt))
        t += DT
    return t


def coast(g, u, r, t, seconds=COAST_S, alt=30.0):
    """Lap COAST seconds giay (rate 0, tracker bao khoang cach r - bo dan duong tu dong bang bang _last_r)."""
    cmds = []
    for _ in range(int(round(seconds / DT))):
        cmds.append(g.step(trk(t, u, r, status=TrackStatus.COAST), own(t, alt)))
        t += DT
    return cmds


def blind(g, t, seconds=COAST_S, alt=30.0):
    cmds = []
    for _ in range(int(round(seconds / DT))):
        cmds.append(g.step_blind(TrackState(t=t, status=TrackStatus.LOST), own(t, alt)))
        t += DT
    return cmds


def up_speed(c):
    return max(0.0, -c.vel_ned[2])


def up_integral_m(cmds):
    return sum(up_speed(c) for c in cmds) * DT


def hspeed(c):
    return math.hypot(c.vel_ned[0], c.vel_ned[1])


def zs(cmds):
    return [c.vel_ned[2] for c in cmds]


# ---------------- (i) tich phan len <= 1.0 m + v0^2/(2 a_max_z) moi lan COAST (Q1) ----------------
def _integral_bound(v0):
    return 1.0 + v0 * v0 / (2.0 * AZ) + v0 * AZ / JERK


@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_upward_command_integral_bounded_far(angle):
    u = los_down(angle)
    g = Guidance(make_cfg())
    t = warm(g, u, R_SET, n_false=15)
    v0 = up_speed(g.prev)
    cmds = coast(g, u, R_SET, t)
    assert all("coast" in c.reason for c in cmds)
    assert up_integral_m(cmds) <= _integral_bound(v0), \
        "tich phan len %.2f m, v0 %.2f m/s" % (up_integral_m(cmds), v0)


@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_upward_command_integral_bounded_too_close(angle):
    u = los_down(angle)
    g = Guidance(make_cfg())
    t = warm(g, u, R_NEAR, n_false=15)
    v0 = up_speed(g.prev)
    cmds = coast(g, u, R_NEAR, t)
    assert up_integral_m(cmds) <= _integral_bound(v0), \
        "tich phan len %.2f m, v0 %.2f m/s" % (up_integral_m(cmds), v0)


# ---------------- (ii) van toc dung nho (los_rate gia) khong truyen ra lenh ----------------
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_remembered_upward_velocity_not_forwarded(angle):
    u = los_down(angle)
    # tat vc de co lap: chi con van toc nho tac dong theo phuong dung
    g = Guidance(make_cfg(kp_vert_center=0.0))
    t = warm(g, u, R_SET, n_false=15)
    assert g._mem[1][2] < -1.0                  # dieu kien dau: bo nho that su mang van toc len lon
    g.prev, g.prev_accel = None, (0.0, 0.0, 0.0)  # lenh truoc = dung yen: moi thanh phan len sau day la do bo nho
    cmds = coast(g, u, R_SET, t)
    peak = max(up_speed(c) for c in cmds)
    assert peak <= 1e-3, "toc do len lon nhat %.3f m/s" % peak


@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_blind_remembered_upward_velocity_not_forwarded(angle):
    u = los_down(angle)
    g = Guidance(make_cfg(kp_vert_center=0.0))
    t = warm(g, u, R_SET, n_false=15)
    assert g._mem[1][2] < -1.0
    g.prev, g.prev_accel = None, (0.0, 0.0, 0.0)
    cmds = blind(g, t)
    assert all("blind" in c.reason for c in cmds)
    peak = max(up_speed(c) for c in cmds)
    assert peak <= 1e-3, "toc do len lon nhat %.3f m/s" % peak


# ---------------- (iii) vc khong dong gop khi COAST ----------------
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_vertical_centering_term_does_not_contribute(angle):
    u = los_down(angle)
    g_on = Guidance(make_cfg())
    t = warm(g_on, u, R_SET)                    # cung lich su TRACK (vc bat) cho ca hai nhanh
    g_off = copy.deepcopy(g_on)                 # re nhanh: cung trang thai luc vao COAST
    g_off.cfg.kp_vert_center = 0.0              # chi khac nhau trong pha COAST
    assert g_off.cfg is not g_on.cfg and g_on.cfg.kp_vert_center > 0.0
    out = {"vc_on": np.array([c.vel_ned for c in coast(g_on, u, R_SET, t)]),
           "vc_off": np.array([c.vel_ned for c in coast(g_off, u, R_SET, t)])}
    diff = float(np.max(np.abs(out["vc_on"] - out["vc_off"])))
    assert diff < 1e-6, "vc con anh huong lenh khi COAST: lech toi da %.3f m/s" % diff


# ---------------- (iv) phan lui khi qua gan luc COAST chi theo phuong ngang ----------------
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_back_off_when_too_close_has_no_upward_component(angle):
    u = los_down(angle)
    g = Guidance(make_cfg(kp_vert_center=0.0))   # co lap: chi con phan lui doc duong ngam
    t = warm(g, u, R_NEAR)
    g.prev, g.prev_accel = None, (0.0, 0.0, 0.0)
    cmds = coast(g, u, R_NEAR, t)
    assert all("min_range" in c.reason for c in cmds)       # dieu kien dau: dang o che do lui
    # lui theo phuong NGANG voi toan bo back_speed (chieu xuong mat ngang, khong chi thanh phan ngang cua lui doc LOS:
    # o 40 do thanh phan ngang doc LOS chi con 77% back_speed)
    back = g.cfg.back_speed_mps
    assert min(c.vel_ned[0] for c in cmds) <= -0.9 * back, "lui ngang %.2f < %.2f" % (
        -min(c.vel_ned[0] for c in cmds), 0.9 * back)
    peak = max(up_speed(c) for c in cmds)
    assert peak <= 1e-3, "toc do len lon nhat %.3f m/s" % peak


# ---------------- (iv-b) so hang P theo khoang cach (lui ra tu 12 m ve 15 m) cung khong co thanh phan len ----------------
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_range_recovery_term_has_no_upward_component(angle):
    u = los_down(angle)
    r = 12.0                                    # giua range_back 10 va range_set 15: so hang P keo ra xa doc LOS
    g = Guidance(make_cfg(kp_vert_center=0.0))
    t = warm(g, u, r)
    g.prev, g.prev_accel = None, (0.0, 0.0, 0.0)
    cmds = coast(g, u, r, t)
    assert all("min_range" not in c.reason for c in cmds)
    assert min(c.vel_ned[0] for c in cmds) < -0.3             # dieu kien dau: so hang P co tac dung ngang
    peak = max(up_speed(c) for c in cmds)
    assert peak <= 1e-3, "toc do len lon nhat %.3f m/s" % peak


# ---------------- Q4: lui lien tuc khi LOS gan thang dung ----------------
def _back_hspeed(uh):
    u = los_uh(uh)
    g = Guidance(make_cfg(kp_vert_center=0.0))
    t = warm(g, u, 5.0)
    g.prev, g.prev_accel = None, (0.0, 0.0, 0.0)
    cmds = coast(g, u, 5.0, t, seconds=4.0)
    assert all("min_range" in c.reason for c in cmds)
    return hspeed(cmds[-1]), max(up_speed(c) for c in cmds)


def test_coast_back_off_continuous_in_horizontal_los_component():
    h0, h1, h2 = _back_hspeed(0.0)[0], _back_hspeed(5e-4)[0], _back_hspeed(2e-3)[0]
    assert h0 <= 0.1, "LOS thang dung: lui ngang %.3f m/s phai ~0" % h0
    assert abs(h2 - h1) <= 0.5, "buoc nhay lui ngang %.3f -> %.3f m/s khi uh 5e-4 -> 2e-3" % (h1, h2)


@pytest.mark.parametrize("uh", (0.0, 5e-4, 2e-3))
def test_coast_back_off_near_vertical_los_has_no_upward_component(uh):
    peak = _back_hspeed(uh)[1]
    assert peak <= 1e-3, "toc do len lon nhat %.3f m/s" % peak


# ---------------- Q3: khong nhay lenh dung luc vao COAST va luc quay lai TRACK ----------------
# Ca thu hai tat vc o TRACK de lenh truoc la lenh LEN (neu bat, vc keo xuong; luc do viec cat thanh phan tien lai gan
# cua COAST - da co o ban goc - moi la thu cat nhanh lenh xuong, khong thuoc Q3).
ENTRY_CASES = [(R_NEAR, 0, {}), (R_SET, 25, {"kp_vert_center": 0.0})]


@pytest.mark.parametrize("r,n_false,kp", ENTRY_CASES)
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_entry_vertical_command_respects_accel_limit_and_decays(angle, r, n_false, kp):
    u = los_down(angle)
    g = Guidance(make_cfg(**kp))
    t = warm(g, u, r, n_false=n_false)
    z_prev = g.prev.vel_ned[2]
    v0 = up_speed(g.prev)
    cmds = coast(g, u, r, t)
    for c in cmds:
        assert abs(c.vel_ned[2] - z_prev) <= STEP_Z, \
            "nhay vz %.3f -> %.3f (gioi han %.3f)" % (z_prev, c.vel_ned[2], STEP_Z)
        z_prev = c.vel_ned[2]
    ups = [up_speed(c) for c in cmds]
    # gia toc len dang co chi duoc doi dan (jerk, ke ca ghep 3 chieu): lenh len co the tang them chut roi giam ve 0
    assert max(ups) <= v0 + 0.3, "lenh len tang len %.3f (v0 %.3f)" % (max(ups), v0)
    assert ups[-1] <= 0.01


@pytest.mark.parametrize("r,n_false,kp", ENTRY_CASES)
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_coast_to_track_vertical_command_respects_accel_limit(angle, r, n_false, kp):
    u = los_down(angle)
    g = Guidance(make_cfg(**kp))
    t = warm(g, u, r, n_false=n_false)
    cmds = coast(g, u, r, t, seconds=1.5)
    t += 1.5
    z_prev = cmds[-1].vel_ned[2]
    for _ in range(30):
        c = g.step(trk(t, u, r), own(t))
        assert abs(c.vel_ned[2] - z_prev) <= STEP_Z, "nhay vz %.3f -> %.3f" % (z_prev, c.vel_ned[2])
        z_prev = c.vel_ned[2]
        t += DT


# ---------------- Q2: min_alt thang, COAST va step_blind ----------------
LOW_ALT = 7.0       # < min_alt 10 cua ho so


@pytest.mark.parametrize("angle", (12.0, 40.0))
def test_coast_below_min_alt_climb_command_still_accumulates(angle):
    u = los_down(angle)
    g = Guidance(make_cfg())
    t = warm(g, u, R_SET, alt=LOW_ALT)
    v_before = up_speed(g.prev)
    assert v_before > 1.5                                   # dieu kien dau: dang leo tranh dat
    cmds = coast(g, u, R_SET, t, seconds=0.5, alt=LOW_ALT)
    assert all("low_alt" in c.reason for c in cmds)
    assert min(up_speed(c) for c in cmds) >= v_before - 0.1, \
        "lenh leo tranh dat bi cat: %.2f -> %.2f m/s" % (v_before, min(up_speed(c) for c in cmds))


@pytest.mark.parametrize("angle", (12.0, 40.0))
def test_blind_below_min_alt_climb_command_still_accumulates(angle):
    u = los_down(angle)
    g = Guidance(make_cfg())
    t = warm(g, u, R_SET, alt=LOW_ALT)
    v_before = up_speed(g.prev)
    assert v_before > 1.5
    cmds = blind(g, t, seconds=0.5, alt=LOW_ALT)
    assert all("low_alt" in c.reason and "blind" in c.reason for c in cmds)
    assert min(up_speed(c) for c in cmds) >= v_before - 0.1


# ---------------- (v) bao ve: TRACK binh thuong GIU NGUYEN hanh vi dung hien co ----------------
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_track_vertical_centering_still_acts(angle):
    u = los_down(angle)
    res = {}
    for name, kp in (("on", make_cfg().kp_vert_center), ("off", 0.0)):
        g = Guidance(make_cfg(kp_vert_center=kp))
        t = warm(g, u, R_SET)
        res[name] = g.step(trk(t, u, R_SET), own(t))
    assert res["on"].vel_ned[2] > res["off"].vel_ned[2] + 0.01     # muc tieu thap hon mong muon -> vc keo xuong


@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_track_too_close_back_off_keeps_upward_component(angle):
    u = los_down(angle)
    g = Guidance(make_cfg(kp_vert_center=0.0))
    t = warm(g, u, R_NEAR)
    cmds = [g.step(trk(t + k * DT, u, R_NEAR), own(t + k * DT)) for k in range(60)]
    assert "min_range" in cmds[-1].reason
    assert up_speed(cmds[-1]) > 0.5


@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_track_remembered_vertical_velocity_is_followed(angle):
    # muc tieu that dang di len (los_rate that, TRACK hop le): lenh phai theo
    u = los_down(angle)
    g = Guidance(make_cfg(kp_vert_center=0.0))
    t = warm(g, u, R_SET)
    last = None
    for k in range(45):
        last = g.step(trk(t + k * DT, u, R_SET, rate=(0.0, FALSE_RATE_Y, 0.0)), own(t + k * DT))
    assert up_speed(last) > 1.0


# ---------------- Q5: TRACK co khoang cach khong tin cay (con THAY muc tieu) giu hanh vi ban goc ----------------
@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_track_with_invalid_range_keeps_vertical_centering(angle):
    u = los_down(angle)
    g_on = Guidance(make_cfg())
    t = warm(g_on, u, R_SET)
    g_off = copy.deepcopy(g_on)
    g_off.cfg.kp_vert_center = 0.0
    z = {}
    for name, g in (("on", g_on), ("off", g_off)):
        tt = t
        for _ in range(20):
            c = g.step(trk(tt, u, R_SET, valid=False), own(tt))
            tt += DT
        z[name] = c.vel_ned[2]
    assert z["on"] - z["off"] > 0.3, "vc mat tac dung khi TRACK khoang cach khong tin cay: %.3f vs %.3f" % (
        z["on"], z["off"])


@pytest.mark.parametrize("angle", ANGLES_DEG)
def test_track_with_invalid_range_still_follows_remembered_vertical_velocity(angle):
    u = los_down(angle)
    g = Guidance(make_cfg(kp_vert_center=0.0))
    t = warm(g, u, R_SET, n_false=15)
    assert g._mem[1][2] < -1.0
    last = None
    for k in range(30):
        last = g.step(trk(t + k * DT, u, R_SET, valid=False), own(t + k * DT))
    assert up_speed(last) > 1.0, "van toc dung nho bi kep khi TRACK khoang cach khong tin cay: %.3f" % up_speed(last)
