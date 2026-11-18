"""Test PHA DO cho hinh hoc khop gat chu dong (dtrack/gimbal.py).

Ky vong doc lap: ma tran xoay dung tay bang numpy (Rz*Ry*Rx) va quaternion dung tay tu truc-goc,
KHONG dung quat_from_euler/quat_to_matrix cua du an cho gia tri ky vong.
Quy uoc (theo dtrack/geometry.py:3-6,57-62): quaternion (w,x,y,z), than FRD -> NED;
pitch Euler duong = mui LEN. "Mui chui xuong theta" cua giao viec  <=>  pitch Euler = -theta.
Truc quang trong than = (sin d, 0, -cos d); camera attitude: truc x (tien) cua camera = boresight.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

D = math.radians


# ---------------- ky vong doc lap ----------------
def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _qaxis(axis, a):
    return np.array([math.cos(a / 2), *(math.sin(a / 2) * np.array(axis, float))])


def _qmul(a, b):
    aw, av = a[0], a[1:]
    bw, bv = b[0], b[1:]
    return np.array([aw * bw - av @ bv, *(aw * bv + bw * av + np.cross(av, bv))])


def body_quat(theta_down=0.0, roll=0.0, yaw=0.0):
    """q than->NED: yaw quanh z, roi pitch quanh y (= -theta_down), roi roll quanh x."""
    q = _qmul(_qmul(_qaxis((0, 0, 1), yaw), _qaxis((0, 1, 0), -theta_down)), _qaxis((1, 0, 0), roll))
    return tuple(float(c) for c in q)


def rot_body(theta_down=0.0, roll=0.0, yaw=0.0):
    return _rz(yaw) @ _ry(-theta_down) @ _rx(roll)


def mat_from_q(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def bore_exp(d):
    return np.array([math.sin(d), 0.0, -math.cos(d)])


def elev_of(v):
    return math.asin(max(-1.0, min(1.0, -v[2])))   # NED: z xuong


# ---------------- (0) truc quang ra NED = R_than @ boresight (khong qua Euler) ----------------
@pytest.mark.parametrize("theta,roll,yaw,delta", [(10, 20, 30, 50), (89.9, 20, 77, 12), (90, -35, -150, 40)])
def test_camera_forward_axis_equals_body_rotation_of_boresight(theta, roll, yaw, delta):
    from dtrack.gimbal import boresight_body, camera_attitude
    q = body_quat(D(theta), D(roll), D(yaw))
    fwd = mat_from_q(camera_attitude(q, D(delta)))[:, 0]
    assert fwd == pytest.approx(rot_body(D(theta), D(roll), D(yaw)) @ np.array(boresight_body(D(delta)), float), abs=1e-9)


# ---------------- (1) boresight_body ----------------
@pytest.mark.parametrize("deg,exp", [(90, (1, 0, 0)), (10, (math.sin(D(10)), 0, -math.cos(D(10)))),
                                      (45, (math.sqrt(.5), 0, -math.sqrt(.5)))])
def test_boresight_body_vector_and_unit(deg, exp):
    from dtrack.gimbal import boresight_body
    v = np.array(boresight_body(D(deg)), float)
    assert v.shape == (3,)
    assert v == pytest.approx(exp, abs=1e-12)
    assert np.linalg.norm(v) == pytest.approx(1.0, abs=1e-12)


# Hinh hoc thuan: KHONG ket, KHONG bao loi voi delta huu han ngoai [10, 90] do (chi elev_to_delta ket).
@pytest.mark.parametrize("deg", [0, 5, 120, 180, -30])
def test_boresight_body_not_clamped_outside_limits(deg):
    from dtrack.gimbal import boresight_body
    v = np.array(boresight_body(D(deg)), float)
    assert v == pytest.approx((math.sin(D(deg)), 0.0, -math.cos(D(deg))), abs=1e-12)


@pytest.mark.parametrize("delta", [0, 5, 120, -30])
def test_camera_attitude_not_clamped_outside_limits(delta):
    from dtrack.gimbal import camera_attitude
    theta, roll, yaw = 30, 20, 70
    R_exp = rot_body(D(theta), D(roll), D(yaw)) @ _ry(D(90 - delta))
    q = np.array(camera_attitude(body_quat(D(theta), D(roll), D(yaw)), D(delta)), float)
    assert np.linalg.norm(q) == pytest.approx(1.0, abs=1e-9)
    assert mat_from_q(q) == pytest.approx(R_exp, abs=1e-9)


def test_limits_constants():
    from dtrack.gimbal import DELTA_MAX_RAD, DELTA_MIN_RAD
    assert DELTA_MIN_RAD == pytest.approx(D(10)) and DELTA_MAX_RAD == pytest.approx(D(90))


# ---------------- (2) nam bang, delta=90 -> ngang huong mui ----------------
@pytest.mark.parametrize("yaw_deg", [0, 90, -135])
def test_level_body_delta90_looks_horizontal_along_yaw(yaw_deg):
    from dtrack.gimbal import camera_attitude
    R = mat_from_q(camera_attitude(body_quat(0, 0, D(yaw_deg)), D(90)))
    fwd = R[:, 0]
    assert fwd == pytest.approx((math.cos(D(yaw_deg)), math.sin(D(yaw_deg)), 0.0), abs=1e-9)


# ---------------- camera_attitude: day du 3 truc, khong them roll ----------------
@pytest.mark.parametrize("theta,roll,yaw,delta", [(0, 0, 0, 45), (30, 20, 70, 72), (60, 35, -135, 30), (10, -25, 200, 10)])
def test_camera_attitude_equals_body_times_pitch_joint(theta, roll, yaw, delta):
    from dtrack.gimbal import camera_attitude
    Rb = rot_body(D(theta), D(roll), D(yaw))
    R_exp = Rb @ _ry(D(90 - delta))      # quay quanh y than: x -> (sin d, 0, -cos d)
    R = mat_from_q(camera_attitude(body_quat(D(theta), D(roll), D(yaw)), D(delta)))
    assert R == pytest.approx(R_exp, abs=1e-9)


# Than dung dung (theta = 89.9 / 90, mui chui xuong) kem roll, yaw: ma dung qua Euler se suy bien o day.
# Tinh tay: voi theta=90, truc quang NED = (cos d*cos r, cos d*sin r, sin d) quay yaw -> z_NED = sin d.
@pytest.mark.parametrize("theta", [89.9, 90])
@pytest.mark.parametrize("roll,yaw", [(20, 77), (-35, -150), (0, 200)])
@pytest.mark.parametrize("delta", [12, 40, 90])
def test_camera_attitude_near_vertical_body_with_roll_yaw(theta, roll, yaw, delta):
    from dtrack.gimbal import camera_attitude
    R_exp = rot_body(D(theta), D(roll), D(yaw)) @ _ry(D(90 - delta))
    q = np.array(camera_attitude(body_quat(D(theta), D(roll), D(yaw)), D(delta)), float)
    assert np.linalg.norm(q) == pytest.approx(1.0, abs=1e-9)
    assert mat_from_q(q) == pytest.approx(R_exp, abs=1e-9)
    if theta == 90:
        assert mat_from_q(q)[2, 0] == pytest.approx(math.sin(D(delta)), abs=1e-9)   # z_NED = sin d


def test_camera_attitude_returns_unit_quaternion():
    from dtrack.gimbal import camera_attitude
    q = np.array(camera_attitude(body_quat(D(30), D(20), D(40)), D(60)), float)
    assert q.shape == (4,) and np.linalg.norm(q) == pytest.approx(1.0, abs=1e-9)


# ---------------- (3) vong khep kin ----------------
def test_closed_loop_grid():
    from dtrack.gimbal import camera_attitude, elev_to_delta
    unsat = 0
    for th in (0, 12, 30, 60, 80):
        for ro in (0, 20, 35):
            for yaw in (0.0, D(77), D(-150)):
                for el_deg in (0, -12, -15, -40):
                    q = body_quat(D(th), D(ro), yaw)
                    delta, sat = elev_to_delta(q, D(el_deg))
                    assert sat is True or sat is False
                    assert math.isfinite(delta) and D(10) - 1e-12 <= delta <= D(90) + 1e-12
                    if sat:
                        continue
                    unsat += 1
                    fwd = mat_from_q(camera_attitude(q, delta))[:, 0]
                    assert abs(elev_of(fwd) - D(el_deg)) < D(0.1), (th, ro, yaw, el_deg)
    assert unsat >= 20     # luoi phai co du ca khong bao hoa, tranh test rong


@pytest.mark.parametrize("theta", [89.9, 90])
@pytest.mark.parametrize("roll,yaw", [(20, 77), (-35, -150), (60, 10)])
@pytest.mark.parametrize("el_deg", [-12, -40])
def test_closed_loop_near_vertical_body_with_roll_yaw(theta, roll, yaw, el_deg):
    from dtrack.gimbal import camera_attitude, elev_to_delta
    q = body_quat(D(theta), D(roll), D(yaw))
    delta, sat = elev_to_delta(q, D(el_deg))
    assert sat is False
    fwd = mat_from_q(camera_attitude(q, delta))[:, 0]
    assert abs(elev_of(fwd) - D(el_deg)) < D(0.01)


@pytest.mark.parametrize("roll,yaw", [(20, 77), (-35, -150), (60, 10)])
def test_hand_value_vertical_body_roll_yaw_independent(roll, yaw):
    # theta=90: z_NED = sin d => elev = -d, nen elev -12 do -> d = 12 do, bat ke roll/yaw
    from dtrack.gimbal import elev_to_delta
    delta, sat = elev_to_delta(body_quat(D(90), D(roll), D(yaw)), D(-12))
    assert sat is False
    assert math.degrees(delta) == pytest.approx(12, abs=1e-6)


# ---------------- (4) bang tinh tay, khong roll: d = 90 - theta - elev (do) ----------------
@pytest.mark.parametrize("th,el,exp", [(30, -12, 72), (60, -12, 42), (78, -12, 24), (89.9, -12, 12.1),
                                        (90, -12, 12), (0, 30, 60), (-10, 20, 80)])
def test_hand_table_no_roll(th, el, exp):
    from dtrack.gimbal import elev_to_delta
    delta, sat = elev_to_delta(body_quat(D(th)), D(el))
    assert sat is False
    assert math.degrees(delta) == pytest.approx(exp, abs=1e-6)


# Dung tai gioi han (khong bi ket that su) -> sat False. Dung bang so voi gioi han, nen can dung dung gia tri.
@pytest.mark.parametrize("th,el,exp", [(80, 0, 10), (0, 0, 90), (60, -60, 90)])
def test_exactly_at_limit_is_not_saturated(th, el, exp):
    from dtrack.gimbal import elev_to_delta
    delta, sat = elev_to_delta(body_quat(D(th)), D(el))
    assert sat is False
    assert math.degrees(delta) == pytest.approx(exp, abs=1e-6)


# ---------------- (5) bao hoa ----------------
# theta < 0 = mui ngang LEN (pitch Euler duong): d = 90 - theta - elev = 90 + |theta| - elev > 90 khi elev <= 0
@pytest.mark.parametrize("th,el,exp", [(0, -12, 90), (85, 0, 10), (-20, -12, 90), (-5, -5, 90), (89.9, 0, 10)])
def test_saturation_no_roll(th, el, exp):
    from dtrack.gimbal import elev_to_delta
    delta, sat = elev_to_delta(body_quat(D(th)), D(el))
    assert sat is True
    assert math.degrees(delta) == pytest.approx(exp, abs=1e-6)


def test_custom_limits_respected():
    from dtrack.gimbal import elev_to_delta
    delta, sat = elev_to_delta(body_quat(D(30)), D(-12), delta_min=D(20), delta_max=D(60))
    assert sat is True and math.degrees(delta) == pytest.approx(60, abs=1e-6)


# ---------------- (6) roll lon, ngoai tam ----------------
@pytest.mark.parametrize("el,exp", [(-40, 90), (40, 10)])
def test_unreachable_with_large_roll_returns_nearest_limit(el, exp):
    # theta=0, roll=80: el(delta) = asin(cos80 * cos delta) trong [0, 9.8 do] voi delta in [10,90]
    from dtrack.gimbal import elev_to_delta
    delta, sat = elev_to_delta(body_quat(0.0, D(80), D(20)), D(el))
    assert sat is True
    assert math.isfinite(delta) and math.degrees(delta) == pytest.approx(exp, abs=1e-6)


# ---------------- (7) NaN / inf -> ValueError (tien le: quat_normalize ném ValueError, geometry.py:26) ----------------
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("case", ["boresight_delta", "attitude_delta", "attitude_quat", "elev_target", "elev_quat"])
def test_non_finite_inputs_raise_value_error(case, bad):
    import dtrack.gimbal as g
    q = body_quat(D(20), D(10), D(30))
    calls = {
        "boresight_delta": lambda: g.boresight_body(bad),
        "attitude_delta": lambda: g.camera_attitude(q, bad),
        "attitude_quat": lambda: g.camera_attitude((bad, 0.0, 0.0, 0.0), D(45)),
        "elev_target": lambda: g.elev_to_delta(q, bad),
        "elev_quat": lambda: g.elev_to_delta((1.0, bad, 0.0, 0.0), D(-10)),
    }
    with pytest.raises(ValueError):
        calls[case]()


# ---------------- (8) azimuth ----------------
@pytest.mark.parametrize("yaw_deg", [0, 33, -135, 170])
@pytest.mark.parametrize("theta", [0, 25, 60])
def test_azimuth_in_vertical_plane_of_body_x_when_no_roll(yaw_deg, theta):
    from dtrack.gimbal import camera_attitude
    yaw = D(yaw_deg)
    for deg in range(10, 91, 10):
        fwd = mat_from_q(camera_attitude(body_quat(D(theta), 0.0, yaw), D(deg)))[:, 0]
        in_yaw_frame = _rz(-yaw) @ fwd
        assert abs(in_yaw_frame[1]) < 1e-9      # khong lech ngang khoi mat phang (x_yaw, z)


# ---------------- (9) elev khong voi toi: delta phai la diem toi uu tren ca dai, khong chi o hai dau ----------------
# sin(elev dat duoc) f(d) = A sin d + B cos d = C cos(d - phi); neu phi nam trong dai thi cuc dai o d = phi.
def _sin_elev_achieved(theta, roll, yaw, d):
    return float((rot_body(D(theta), D(roll), D(yaw)) @ bore_exp(d))[2] * -1.0)


def _unreachable_grid():
    sweep = np.linspace(D(10), D(90), 4001)
    out = []
    for th in (-80, -60, -40, -20):
        for ro in (20, 45, 50, 70):
            fs = [_sin_elev_achieved(th, ro, 0.0, d) for d in sweep]
            for el in (30, 60, 90):
                if not (min(fs) - 1e-9 <= math.sin(D(el)) <= max(fs) + 1e-9):
                    out.append((th, ro, el))
    return out


_UNREACH = _unreachable_grid()


def test_unreachable_grid_is_not_empty_and_has_interior_optimum_cases():
    # tranh test rong: luoi co du ca khong voi toi, trong do co ca phi = atan2(-sin th, cos th cos roll) trong dai
    assert len(_UNREACH) >= 8
    interior = [c for c in _UNREACH
                if D(10) < math.atan2(-math.sin(D(c[0])), math.cos(D(c[0])) * math.cos(D(c[1]))) < D(90)]
    assert len(interior) >= 4


def test_unreachable_elev_returns_interior_optimum_hand_value():
    # theta=-80, roll=20: A = sin80 = 0.98481, B = cos80*cos20 = 0.163177, phi = atan2(A, B) = 80.59 do
    # (trong dai) ; C = 0.99830 < sin 90 = 1 nen khong voi toi. Cuc dai f tai d = phi, f(90 do) = 0.98481 chi la 0.0152 sai.
    from dtrack.gimbal import elev_to_delta
    delta, sat = elev_to_delta(body_quat(D(-80), D(20), 0.0), D(90))
    assert sat is True
    assert math.degrees(delta) == pytest.approx(80.59, abs=0.05)


@pytest.mark.parametrize("th,ro,el", _UNREACH)
def test_unreachable_elev_error_is_minimal_over_whole_range(th, ro, el):
    from dtrack.gimbal import elev_to_delta
    yaw = D(37)
    delta, sat = elev_to_delta(body_quat(D(th), D(ro), yaw), D(el))
    assert sat is True
    assert D(10) - 1e-12 <= delta <= D(90) + 1e-12
    s = math.sin(D(el))
    err = abs(_sin_elev_achieved(th, ro, yaw, delta) - s)
    best = min(abs(_sin_elev_achieved(th, ro, yaw, d) - s) for d in np.linspace(D(10), D(90), 4001))
    assert err <= best + 1e-6, (math.degrees(delta), err, best)
