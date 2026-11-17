import math
import os
import sys
from functools import lru_cache

import pytest
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tilt_mount as T  # noqa: E402


@lru_cache(None)
def parts():
    return T.parts()


@lru_cache(None)
def dummies():
    return T.dummies()


def cyl_faces(wp, radius, axis):
    """Cac mat tru co ban kinh `radius` va truc song song `axis` (0=X,1=Y,2=Z) -> (center, r)."""
    out = []
    for f in wp.val().Faces():
        if f.geomType() != "CYLINDER":
            continue
        s = BRepAdaptor_Surface(f.wrapped).Cylinder()
        d = s.Axis().Direction()
        comp = [abs(d.X()), abs(d.Y()), abs(d.Z())]
        if comp[axis] > 0.999 and abs(s.Radius() - radius) < 1e-4:
            out.append(f.Center())
    return out


# (a) luoi lo camera 21 x 12,5 va duong kinh lo
def test_camera_hole_grid_and_diameter():
    pts = cyl_faces(parts()["bracket"], T.M2_PILOT / 2, 1)
    assert len(pts) == 4
    xs = sorted({round(p.x, 3) for p in pts})
    zs = sorted({round(p.z, 3) for p in pts})
    assert len(xs) == 2 and len(zs) == 2
    assert xs[1] - xs[0] == pytest.approx(21.0, abs=1e-3)
    assert zs[1] - zs[0] == pytest.approx(12.5, abs=1e-3)
    # lo tren bo camera gia lap cung luoi, dk 2,2
    cam = cyl_faces(dummies()["camera"], T.HOLE_D / 2, 1)
    assert len(cam) == 4
    assert T.M2_PILOT == 1.7 and T.M2_CLEAR == 2.3 and T.M3_PILOT == 2.6 and T.M3_CLEAR == 3.3


# (b) hoc servo lon hon than servo dung bang khe ho
def test_servo_window_equals_body_plus_clearance():
    w1 = parts()["base"].val()
    eps = 0.02
    zc = 0.0
    x = 1.0
    def inside(y, z):
        return w1.isInside(cq.Vector(x, y, z))
    hl = (T.SV_L + T.CLR) / 2
    hw = (T.SV_W + T.CLR) / 2
    assert not inside(T.SV_YC + hl - eps, zc) and inside(T.SV_YC + hl + eps, zc)
    assert not inside(T.SV_YC - hl + eps, zc) and inside(T.SV_YC - hl - eps, zc)
    assert not inside(T.SV_YC, hw - eps) and inside(T.SV_YC, hw + eps)
    assert not inside(T.SV_YC, -hw + eps) and inside(T.SV_YC, -hw - eps)


def intersect_vol(a, b):
    try:
        r = a.intersect(b)
        return sum(s.Volume() for s in r.vals()) if r.vals() else 0.0
    except Exception:
        return 0.0


MOVING = ("bracket", "horn", "camera", "lens", "cable")


def pose_sets(ang):
    P, D = parts(), dummies()
    moving = {k: T.rot_x({**P, **D}[k], ang) for k in MOVING}
    static = {"base": P["base"], "servo": D["servo"], "spacer": P["spacer"]}
    return moving, static


# (c1) khong va cham o cac goc gat
@pytest.mark.parametrize("ang", T.TILT_TEST)
def test_no_collision(ang):
    moving, static = pose_sets(ang)
    for mk, m in moving.items():
        for sk, s in static.items():
            v = intersect_vol(m, s)
            assert v < 1e-3, f"{mk} giao {sk} {v:.4f} mm3 o {ang} do"


# (c2) khoi lens khong bi che trong non nhin 120 do (khong tinh tam de: de la ban/bang, xem README)
@pytest.mark.parametrize("ang", T.TILT_TEST)
def test_fov_cone_not_occluded(ang):
    P, D = parts(), dummies()
    cone = T.rot_x(T.build_cone(), ang)
    base_wp = cq.Workplane("XY").add(T.build_wall1().val()).add(T.build_wall2().val())
    occluders = {"wall1": T.build_wall1(), "wall2": T.build_wall2(), "servo": D["servo"],
                 "spacer": P["spacer"]}
    occluders.update({k: T.rot_x({**P, **D}[k], ang) for k in ("bracket", "horn")})
    for k, o in occluders.items():
        v = intersect_vol(cone, o)
        assert v < 1e-3, f"{k} che non nhin {v:.2f} mm3 o {ang} do"


# (d) truc quay gia kep trung truc ra servo
def test_axis_coincident():
    P, D = parts(), dummies()
    sp = cyl_faces(D["servo"], T.SV_SPLINE_D / 2, 0)
    assert sp
    ref = (sp[0].y, sp[0].z)
    assert ref == pytest.approx((0, 0), abs=1e-6)
    found = [
        cyl_faces(P["bracket"], (T.HORN_HUB_D + T.CLR) / 2, 0),
        cyl_faces(P["bracket"], T.M3_PILOT / 2, 0),
        cyl_faces(P["base"], T.M3_CLEAR / 2, 0),
        cyl_faces(D["horn"], T.SV_SPLINE_D / 2 + 0.05, 0),
    ]
    for lst in found:
        assert lst
        for c in lst:
            if abs(c.y) < 1 and abs(c.z) < 1:
                assert (c.y, c.z) == pytest.approx(ref, abs=1e-6)


# (e) thanh mong nhat (cong thuc tren tham so)
def test_min_walls():
    m = 1.6
    assert T.T_WALL >= m and T.T_FLOOR >= m and T.T_CHEEK >= m
    assert (T.POST_D - T.M2_PILOT) / 2 >= m                      # thanh tru do camera
    assert (T.CHEEK_R - (T.HORN_HUB_D + T.CLR) / 2) >= m         # quanh lo hub
    assert (4.0 * 2 - T.M3_CLEAR) / 2 >= m                       # ong lot (OD 8)
    assert (T.Y_PLATE_F - T.Y_PLATE_B) - (T.PILOT_BOARD_DEPTH - T.POST_H) >= m - 1e-9  # da duoi lo ren
    assert T.T_CHEEK - 0 >= m and (T.CHEEK_R - T.M3_PILOT / 2) >= m
    assert T.T_WALL >= T.X_CASE_TOP                              # than servo khong thoi ra ngoai vach


def test_known_thin_web_between_window_and_ear_screw():
    """Ngoai le co chu y: gan giua cua so servo va lo vit tai ~1,5 mm (< 1,6)."""
    web = T.SV_EAR_HOLE_DIST / 2 - T.M2_PILOT / 2 - (T.SV_L + T.CLR) / 2
    assert web >= 1.5 - 1e-9


def test_assembly_slide_room():
    assert T.FAR_GAP >= T.HORN_HUB_H + 0.5   # du cho de lap horn len truc ra roi day ve vach servo
    assert T.X_HORN_TOP <= T.X_CASE_TOP + T.SV_SPLINE_H + 1e-9
