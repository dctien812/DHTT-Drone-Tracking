"""Khop gat MOT TRUC (tilt) cho servo MG90S + Raspberry Pi Camera Module 3 Wide.
CadQuery, don vi mm.  Chay:  python tilt_mount.py   (sinh STEP/STL vao out/)

He toa do (lap rap, goc gat = 0):
  X = truc quay (truc ra servo, song song X), Y = huong camera nhin, Z = len.
  Truc quay di qua (y=0, z=0).  Goc gat duong = camera nhin len (quay quanh +X).
  Mat ngoai vach servo la x=0 (tai servo ap vao mat nay, than servo nam o x<0).
"""
import math
import os
import cadquery as cq

# ============================== THAM SO ======================================
# Khe ho lap ghep dung nhat quan cho moi chi tiet in (mm)
CLR = 0.25
# Lo vit (do in FDM 0,4 mm): tu ren vao nhua nho hon danh dinh, lo thong lon hon
M2_PILOT, M2_CLEAR = 1.7, 2.3
M3_PILOT, M3_CLEAR = 2.6, 3.3

# --- Raspberry Pi Camera Module 3 Wide (CHUA DOI CHIEU NGUON: so pho bien; tai lieu
#     chinh thuc: datasheets.raspberrypi.com, "Camera Module 3 mechanical drawing") ---
BOARD_W, BOARD_H, BOARD_T = 25.0, 24.0, 1.0   # rong (X), cao (Z), day bo mach
HOLE_DX, HOLE_DZ, HOLE_D = 21.0, 12.5, 2.2    # luoi lo M2 va duong kinh lo tren bo
LENS_W, LENS_H = 12.0, 11.5                   # khoi lens: rong (X,Z), nho ra khoi mat truoc
CONN_W, CONN_D, CONN_H = 16.5, 3.0, 2.6       # dau noi cap (gia dinh): rong, sau theo Z, cao theo Y
CABLE_W, CABLE_T, CABLE_L = 16.0, 0.4, 10.0   # cap det gan dau noi: rong, day, dai di xuong
FOV_DIAG = 120.0                              # goc nhin cheo (do) cua ban Wide

# --- Servo MG90S (CHUA DOI CHIEU NGUON: so pho bien) ---
SV_L, SV_W = 22.8, 12.2            # than: dai (theo Y), rong (theo Z)
SV_EAR_SPAN = 32.3                 # tong chieu rong tai
SV_EAR_T = 2.5                     # day tai
SV_EAR_HOLE_DIST, SV_EAR_HOLE_D = 27.8, 2.0
SV_BELOW_EAR = 16.5                # tu day than toi mat duoi tai
SV_H = 22.7                        # tu day than toi mat tren cua vo
SV_SHAFT_OFFSET = 5.5              # truc lech khoi tam than (doc theo truc dai)
SV_SPLINE_D, SV_SPLINE_H = 4.8, 5.5  # truc ra nho khoi vo (kem rang)
# Canh tay (horn) mot canh (chua doi chieu nguon)
HORN_HUB_D, HORN_HUB_H = 7.2, 4.5
HORN_ARM_T, HORN_ARM_LEN, HORN_ARM_W = 1.8, 14.5, 4.0
HORN_HOLE_R = (6.0, 8.0)           # ban kinh 2 lo vit tren canh tay
HORN_GAP = 1.0                     # khe giua mat duoi horn va mat tren vo servo

# --- Kich thuoc thiet ke ---
T_WALL = 4.0          # vach de, day (>= SV_H - SV_BELOW_EAR - SV_EAR_T de than ra het qua cua so)
T_FLOOR = 4.0
T_CHEEK = 4.0         # ma (cheek) cua gia kep
POST_D, POST_H = 5.0, 3.2   # tru do bo camera (POST_H > chieu cao linh kien mat sau)
AXIS_AHEAD = 2.0      # truc quay nam truoc mat truoc bo camera bay nhieu (gan tam khoi camera+lens)
AX_H = 20.0           # do cao truc quay so voi mat tren de
FAR_GAP = 5.5         # khoang giua ma 2 va vach xa (de lap horn len truc ra)
PIN_PLAY = 0.5       # do ho doc truc cua ong lot (spacer) o chot
WALL_FRONT = 12.0     # mep truoc cua vach (khong che goc nhin)
WALL_TOP = 10.0       # mep tren vach so voi truc
WALL_BACK_MARGIN = 4.5  # phan vach sau tai servo
TILT_TEST = (-60.0, -50.0, 0.0, 50.0, 60.0)
CONE_LEN = 30.0       # chieu dai hinh non nhin dung de kiem che khuat
PETG_G_CM3 = 1.27

# ============================== DAN XUAT =====================================
SV_YC = -SV_SHAFT_OFFSET                       # tam than servo theo Y
SV_CASE_ABOVE_EAR = SV_H - SV_BELOW_EAR - SV_EAR_T   # 3.7: phan vo nho qua mat tai
X_CASE_TOP = SV_CASE_ABOVE_EAR
X_HORN0 = X_CASE_TOP + HORN_GAP
X_HORN_TOP = X_HORN0 + HORN_HUB_H
X_CH1 = X_HORN0 + HORN_ARM_T                   # mat trong ma 1 = mat tren canh tay horn
X_CH1_OUT = X_CH1 + T_CHEEK
CAM_IN_W = BOARD_W + 2 * CLR
X_CH2 = X_CH1_OUT + CAM_IN_W
X_CH2_OUT = X_CH2 + T_CHEEK
X_W2 = X_CH2_OUT + FAR_GAP                     # mat trong vach xa
X_W2_OUT = X_W2 + T_WALL
X_CAM = (X_CH1_OUT + X_CH2) / 2                # tam camera theo X
SPACER_L = FAR_GAP - PIN_PLAY
Y_BOARD_F = -AXIS_AHEAD                        # mat truoc bo camera
Y_BOARD_B = Y_BOARD_F - BOARD_T
Y_PLATE_F = Y_BOARD_B - POST_H
Y_PLATE_B = -(HORN_HOLE_R[1] + 2.5)            # mat dat ban in cua gia kep
Y_LENS_F = Y_BOARD_F + LENS_H
Z_PLATE = (-9.0, BOARD_H / 2)
CHEEK_R = 9.0
ZF = -AX_H                                     # mat tren de
PILOT_BOARD_DEPTH = (Y_PLATE_F - Y_PLATE_B) - 1.6 + POST_H  # lo ren vao tam, chua 1,6 da
WALL_Y0 = SV_YC - SV_EAR_SPAN / 2 - WALL_BACK_MARGIN

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


# ============================== TIEN ICH =====================================
def box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def cyl_x(y, z, r, x0, x1):
    return cq.Workplane("YZ", origin=(x0, 0, 0)).center(y, z).circle(r).extrude(x1 - x0)


def cyl_y(x, z, r, y0, y1):
    return cq.Workplane("XZ", origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def cyl_z(x, y, r, z0, z1):
    return cq.Workplane("XY", origin=(0, 0, z0)).center(x, y).circle(r).extrude(z1 - z0)


def rot_x(shape, deg):
    """Quay Workplane/Shape quanh truc X qua goc toa do."""
    if isinstance(shape, cq.Workplane):
        return shape.rotate((0, 0, 0), (1, 0, 0), deg)
    return shape.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), deg)


# ============================== CHI TIET IN ==================================
def wall_profile():
    """Duong vien vach (Y,Z): cat cheo goc duoi-truoc de khong che non nhin khi gat xuong."""
    return [(WALL_Y0, ZF), (-3.0, ZF), (WALL_FRONT, -9.0), (WALL_FRONT, WALL_TOP), (WALL_Y0, WALL_TOP)]


def build_wall1():
    w = cq.Workplane("YZ", origin=(0, 0, 0)).polyline(wall_profile()).close().extrude(T_WALL)
    window = (cq.Workplane("YZ", origin=(-1, 0, 0)).center(SV_YC, 0)
              .rect(SV_L + CLR, SV_W + CLR).extrude(T_WALL + 2))
    pil = (cq.Workplane("YZ", origin=(-1, 0, 0))
           .pushPoints([(SV_YC - SV_EAR_HOLE_DIST / 2, 0), (SV_YC + SV_EAR_HOLE_DIST / 2, 0)])
           .circle(M2_PILOT / 2).extrude(T_WALL + 2))
    return w.cut(window).cut(pil)


def build_wall2():
    w = cq.Workplane("YZ", origin=(X_W2, 0, 0)).polyline(wall_profile()).close().extrude(T_WALL)
    return w.cut(cyl_x(0, 0, M3_CLEAR / 2, X_W2 - 1, X_W2_OUT + 1))


def build_floor():
    x0, x1, y0, y1 = -4.0, X_W2_OUT + 4.0, -35.0, 21.0
    f = box(x0, x1, y0, y1, ZF - T_FLOOR, ZF)
    # cua so cho cap det di xuong (rong hon cap), chi cat phan duoi camera
    f = f.cut(box(X_CAM - 12.5, X_CAM + 12.5, -22.0, 4.0, ZF - T_FLOOR - 1, ZF + 1))
    pts = [(2.0, 17.0), (2.0, -31.0), (X_W2 + T_WALL / 2, 17.0), (X_W2 + T_WALL / 2, -31.0)]
    for (x, y) in pts:
        f = f.cut(cyl_z(x, y, M3_CLEAR / 2, ZF - T_FLOOR - 1, ZF + 1))
    return f


def build_base():
    return build_floor().union(build_wall1()).union(build_wall2())


def post_points():
    return [(X_CAM + sx * HOLE_DX / 2, sz * HOLE_DZ / 2) for sx in (-1, 1) for sz in (-1, 1)]


def build_bracket():
    plate = box(X_CH1_OUT, X_CH2, Y_PLATE_B, Y_PLATE_F, Z_PLATE[0], Z_PLATE[1])

    def cheek(x0):
        c = (cq.Workplane("YZ", origin=(x0, 0, 0)).center(Y_PLATE_B / 2, 0)
             .rect(-Y_PLATE_B, 2 * CHEEK_R).extrude(T_CHEEK))
        return c.union(cq.Workplane("YZ", origin=(x0, 0, 0)).circle(CHEEK_R).extrude(T_CHEEK))

    c1 = cheek(X_CH1).cut(cyl_x(0, 0, (HORN_HUB_D + CLR) / 2, X_CH1 - 1, X_CH1_OUT + 1))
    for r in HORN_HOLE_R:
        c1 = c1.cut(cyl_x(-r, 0, M2_CLEAR / 2, X_CH1 - 1, X_CH1_OUT + 1))
    c2 = cheek(X_CH2).cut(cyl_x(0, 0, M3_PILOT / 2, X_CH2 - 1, X_CH2_OUT + 1))
    b = plate.union(c1).union(c2)
    for (x, z) in post_points():
        b = b.union(cyl_y(x, z, POST_D / 2, Y_PLATE_F - 0.01, Y_BOARD_B))
    for (x, z) in post_points():
        b = b.cut(cyl_y(x, z, M2_PILOT / 2, Y_BOARD_B - PILOT_BOARD_DEPTH, Y_BOARD_B + 0.5))
    return b


def build_spacer():
    """Ong lot o chot (truc X) giua ma 2 va vach xa, lo M3 thong."""
    return (cq.Workplane("YZ", origin=(X_CH2_OUT + PIN_PLAY / 2, 0, 0)).circle(4.0)
            .circle(M3_CLEAR / 2).extrude(SPACER_L))


# ----- khoi thay the (khong in) -----
def build_servo():
    body = box(-(SV_EAR_T + SV_BELOW_EAR), X_CASE_TOP, SV_YC - SV_L / 2, SV_YC + SV_L / 2,
               -SV_W / 2, SV_W / 2)
    ears = box(-SV_EAR_T, 0, SV_YC - SV_EAR_SPAN / 2, SV_YC + SV_EAR_SPAN / 2, -SV_W / 2, SV_W / 2)
    ears = ears.cut(cq.Workplane("YZ", origin=(-SV_EAR_T - 1, 0, 0))
                    .pushPoints([(SV_YC - SV_EAR_HOLE_DIST / 2, 0), (SV_YC + SV_EAR_HOLE_DIST / 2, 0)])
                    .circle(SV_EAR_HOLE_D / 2).extrude(SV_EAR_T + 2))
    spline = cyl_x(0, 0, SV_SPLINE_D / 2, X_CASE_TOP - 0.5, X_CASE_TOP + SV_SPLINE_H)
    return body.union(ears).union(spline)


def build_horn():
    hub = cyl_x(0, 0, HORN_HUB_D / 2, X_HORN0, X_HORN_TOP)
    arm = box(X_HORN0, X_CH1, -HORN_ARM_LEN, 0, -HORN_ARM_W / 2, HORN_ARM_W / 2)
    arm = arm.union(cyl_x(-HORN_ARM_LEN, 0, HORN_ARM_W / 2, X_HORN0, X_CH1))
    h = hub.union(arm).cut(cyl_x(0, 0, SV_SPLINE_D / 2 + 0.05, X_HORN0 - 1, X_HORN_TOP + 1))
    return h


def build_camera():
    board = box(X_CAM - BOARD_W / 2, X_CAM + BOARD_W / 2, Y_BOARD_B, Y_BOARD_F,
                -BOARD_H / 2, BOARD_H / 2)
    for (x, z) in post_points():
        board = board.cut(cyl_y(x, z, HOLE_D / 2, Y_BOARD_B - 1, Y_BOARD_F + 1))
    return board


def build_lens():
    return box(X_CAM - LENS_W / 2, X_CAM + LENS_W / 2, Y_BOARD_F, Y_LENS_F, -LENS_W / 2, LENS_W / 2)


def build_cable():
    """Dau noi + cap det: cap roi bo o canh duoi mat sau, di thang xuong."""
    zb = -BOARD_H / 2
    conn = box(X_CAM - CONN_W / 2, X_CAM + CONN_W / 2, Y_BOARD_B - CONN_H, Y_BOARD_B, zb, zb + CONN_D)
    cab = box(X_CAM - CABLE_W / 2, X_CAM + CABLE_W / 2, Y_BOARD_B - CONN_H + 0.2,
              Y_BOARD_B - CONN_H + 0.2 + CABLE_T, zb - CABLE_L, zb + CONN_D)
    return conn.union(cab)


def build_cone():
    """Non nhin (nua goc = FOV/2) dinh o tam mat truoc lens, huong +Y, dai CONE_LEN."""
    r = CONE_LEN * math.tan(math.radians(FOV_DIAG / 2))
    c = cq.Solid.makeCone(0.0, r, CONE_LEN, cq.Vector(X_CAM, Y_LENS_F, 0), cq.Vector(0, 1, 0))
    return cq.Workplane("XY").add(c)


# ============================== XUAT FILE ====================================
def print_pose(name, wp):
    """Xoay chi tiet ve huong in (mat dat ban o z=0, nam trong x,y >= 0)."""
    if name == "bracket":      # +Y -> +Z : mat sau tam (y = Y_PLATE_B) nam tren ban in
        wp = wp.rotate((0, 0, 0), (1, 0, 0), 90)
    elif name == "spacer":     # truc X -> Z
        wp = wp.rotate((0, 0, 0), (0, 1, 0), -90)
    bb = wp.val().BoundingBox()
    return wp.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def parts():
    return {"base": build_base(), "bracket": build_bracket(), "spacer": build_spacer()}


def dummies():
    return {"servo": build_servo(), "horn": build_horn(), "camera": build_camera(),
            "lens": build_lens(), "cable": build_cable()}


def export_all():
    os.makedirs(OUT, exist_ok=True)
    P, D = parts(), dummies()
    for k, wp in {**P, **D}.items():
        cq.exporters.export(wp, os.path.join(OUT, f"{k}.step"))
    for k, wp in P.items():
        cq.exporters.export(print_pose(k, wp), os.path.join(OUT, f"{k}_print.stl"),
                            tolerance=0.01, angularTolerance=0.1)
    colors = {"base": (0.6, 0.6, 0.65), "bracket": (1.0, 0.55, 0.1), "spacer": (0.9, 0.9, 0.2),
              "servo": (0.2, 0.3, 0.8), "horn": (0.95, 0.95, 0.95), "camera": (0.1, 0.6, 0.2),
              "lens": (0.05, 0.05, 0.05), "cable": (0.8, 0.2, 0.2)}
    for ang in (0.0, 50.0):
        a = cq.Assembly(name=f"tilt_mount_{int(ang)}deg")
        for k, wp in {**P, **D}.items():
            moving = k in ("bracket", "horn", "camera", "lens", "cable")
            shp = rot_x(wp, ang) if moving else wp
            a.add(shp, name=k, color=cq.Color(*colors[k]))
        a.save(os.path.join(OUT, f"assembly_{int(ang)}deg.step"))
    return P, D


if __name__ == "__main__":
    import trimesh
    P, D = export_all()
    for k in P:
        m = trimesh.load(os.path.join(OUT, f"{k}_print.stl"))
        e = m.bounding_box.extents
        print(f"{k:8s} bao {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm  watertight={m.is_watertight}  "
              f"V={m.volume:.0f} mm3  m(100%)={m.volume * PETG_G_CM3 / 1000:.1f} g PETG")
    print("OK ->", OUT)
