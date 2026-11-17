"""Khop gat camera mot truc (ban lab) - dung truc tiep trong Fusion.

Chay trong Fusion qua MCP: nap file nay roi goi build(app). Ve bang khoi dac
(direct modeling). Muon doi kich thuoc: sua bang P ben duoi roi chay lai.

He truc (mm): X = truc gat (trai-phai), Y = huong nhin cua camera, Z = len tren.
Goc toa do = tam truc gat. Kich thuoc linh kien la so pho bien, CHUA do vat that.
"""
import adsk.core
import adsk.fusion

P = dict(
    # --- Camera Module 3 (bo mach) ---
    # Nguon: ban ve co khi chinh hang RP-008155-DS (Camera Module 3 Wide), doc 2026-11-17
    cam_w=25.0, cam_h=23.862, cam_t=1.12,
    cam_hole_dx=21.0, cam_hole_dz=12.5, cam_hole_top=2.0,   # hang lo tren cach mep tren
    lens_side=10.8, lens_len=8.3, lens_dz=-2.47,            # khoi lens (chi de xem); tam lens cach mep tren 14.4
    # --- Servo MG90S ---
    sv_len=22.8, sv_wid=12.2, sv_body=15.9, sv_tab_t=2.5, sv_top=4.7,
    sv_tab_len=32.3, sv_hole_pitch=27.8, sv_shaft_off=5.5,  # truc lech tam than
    # --- In 3D ---
    clr=0.25, wall=3.0, d_m2_tap=1.7, d_m3_tap=2.6, d_m3_free=3.3,
    # --- Gia kep camera ---
    plate_t=2.4, standoff=3.0, standoff_d=4.5,
    side_gap=2.0, side_y_front=8.0, side_z=10.0,
    horn_recess=1.6, horn_arm_w=6.2, horn_hub_d=7.6, horn_screw_d=5.0,
    # --- De chu U ---
    # gap_servo: tu mat trong vach servo toi mat ngoai gia kep. TowerPro MG90S: cao tong 32.1,
    # tai o ~18.5-21 tu day -> dau truc cach mat tai 11-13.6 mm, tru vach 3 mm = 8-10.6 mm.
    # Chon 9.0 (thien ve rong: thieu thi chem long den duoi canh tay servo, chat thi khong sua duoc).
    gap_servo=9.0, gap_pivot=1.0, axis_h=24.0, base_t=3.0, up_top=9.0,
    base_y_back=-32.0, base_y_front=21.0, up_y_back=-24.0, up_y_front=13.0,
)

MM = 0.1  # Fusion API dung cm


def _mgr():
    return adsk.fusion.TemporaryBRepManager.get()


def box(x0, x1, y0, y1, z0, z1):
    c = adsk.core.Point3D.create((x0 + x1) / 2 * MM, (y0 + y1) / 2 * MM, (z0 + z1) / 2 * MM)
    obb = adsk.core.OrientedBoundingBox3D.create(
        c, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
        (x1 - x0) * MM, (y1 - y0) * MM, (z1 - z0) * MM)
    return _mgr().createBox(obb)


def cyl(p0, p1, d):
    a = adsk.core.Point3D.create(p0[0] * MM, p0[1] * MM, p0[2] * MM)
    b = adsk.core.Point3D.create(p1[0] * MM, p1[1] * MM, p1[2] * MM)
    return _mgr().createCylinderOrCone(a, d / 2 * MM, b, d / 2 * MM)


def union(target, tools):
    for t in tools:
        _mgr().booleanOperation(target, t, adsk.fusion.BooleanTypes.UnionBooleanType)
    return target


def cut(target, tools):
    for t in tools:
        _mgr().booleanOperation(target, t, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    return target


def geometry():
    p = P
    g = {}
    half_w = p['cam_w'] / 2
    # mat phang bo camera: mat sau y = -4, mat truoc y = -3
    pcb_back = -4.0
    plate_front = pcb_back - p['standoff']
    plate_back = plate_front - p['plate_t']
    x_in = half_w + p['side_gap']            # mat trong vach ben
    x_out = x_in + p['wall']                 # mat ngoai vach ben
    z_top = p['cam_h'] / 2
    hz1 = z_top - p['cam_hole_top']          # hang lo tren
    hz2 = hz1 - p['cam_hole_dz']             # hang lo duoi
    hx = p['cam_hole_dx'] / 2
    g.update(pcb_back=pcb_back, plate_front=plate_front, plate_back=plate_back,
             x_in=x_in, x_out=x_out, hz1=hz1, hz2=hz2, hx=hx)
    # de
    g['xl_in'] = -x_out - p['gap_servo']     # mat trong vach servo
    g['xl_out'] = g['xl_in'] - p['wall']
    g['xr_in'] = x_out + p['gap_pivot']
    g['xr_out'] = g['xr_in'] + p['wall']
    g['z_floor'] = -p['axis_h']
    g['z_bot'] = g['z_floor'] - p['base_t']
    g['sv_yc'] = -p['sv_shaft_off']          # tam than servo theo Y
    return g


def make_cradle():
    p, g = P, geometry()
    body = box(-g['x_out'], g['x_out'], g['plate_back'], g['plate_front'], g['hz2'] - 3.5, g['hz1'] + 4.0)
    walls = [box(-g['x_out'], -g['x_in'], g['plate_back'], p['side_y_front'], -p['side_z'], p['side_z']),
             box(g['x_in'], g['x_out'], g['plate_back'], p['side_y_front'], -p['side_z'], p['side_z'])]
    posts = [cyl((sx * g['hx'], g['plate_front'], z), (sx * g['hx'], g['pcb_back'], z), p['standoff_d'])
             for sx in (-1, 1) for z in (g['hz1'], g['hz2'])]
    union(body, walls + posts)
    holes = [cyl((sx * g['hx'], g['plate_back'] - 0.1, z), (sx * g['hx'], g['pcb_back'] + 0.1, z), p['d_m2_tap'])
             for sx in (-1, 1) for z in (g['hz1'], g['hz2'])]
    xr = -g['x_out'] + p['horn_recess']
    horn = [box(-g['x_out'] - 0.1, xr, g['plate_back'] - 0.1, 0.0, -p['horn_arm_w'] / 2, p['horn_arm_w'] / 2),
            cyl((-g['x_out'] - 0.1, 0, 0), (xr, 0, 0), p['horn_hub_d']),
            cyl((-g['x_out'] - 0.1, 0, 0), (-g['x_in'] + 0.1, 0, 0), p['horn_screw_d'])]
    pivot = [cyl((g['x_in'] - 0.1, 0, 0), (g['x_out'] + 0.1, 0, 0), p['d_m3_tap'])]
    return cut(body, holes + horn + pivot)


def make_base():
    p, g = P, geometry()
    body = box(g['xl_out'], g['xr_out'], p['base_y_back'], p['base_y_front'], g['z_bot'], g['z_floor'])
    ups = [box(g['xl_out'], g['xl_in'], p['up_y_back'], p['up_y_front'], g['z_floor'], p['up_top']),
           box(g['xr_in'], g['xr_out'], -10.0, 10.0, g['z_floor'], p['up_top'])]
    union(body, ups)
    c = p['clr']
    cuts = [
        # hoc than servo
        box(g['xl_out'] - 0.1, g['xl_in'] + 0.1, g['sv_yc'] - p['sv_len'] / 2 - c, g['sv_yc'] + p['sv_len'] / 2 + c,
            -p['sv_wid'] / 2 - c, p['sv_wid'] / 2 + c),
        # hai lo vit tai servo
        cyl((g['xl_out'] - 0.1, g['sv_yc'] - p['sv_hole_pitch'] / 2, 0), (g['xl_in'] + 0.1, g['sv_yc'] - p['sv_hole_pitch'] / 2, 0), p['d_m2_tap']),
        cyl((g['xl_out'] - 0.1, g['sv_yc'] + p['sv_hole_pitch'] / 2, 0), (g['xl_in'] + 0.1, g['sv_yc'] + p['sv_hole_pitch'] / 2, 0), p['d_m2_tap']),
        # lo truc do ben phai (vit M3)
        cyl((g['xr_in'] - 0.1, 0, 0), (g['xr_out'] + 0.1, 0, 0), p['d_m3_free']),
        # khe cho cap det di xuong
        box(-9.5, 9.5, -22.0, -2.0, g['z_bot'] - 0.1, g['z_floor'] + 0.1),
    ]
    for x in (-16.0, 11.0):
        for y in (p['base_y_back'] + 4.0, p['base_y_front'] - 4.0):
            cuts.append(cyl((x, y, g['z_bot'] - 0.1), (x, y, g['z_floor'] + 0.1), p['d_m3_free']))
    return cut(body, cuts)


def make_mock_servo():
    p, g = P, geometry()
    yc = g['sv_yc']
    x_tab = g['xl_out']
    body = box(x_tab - p['sv_tab_t'] - p['sv_body'], x_tab + p['sv_top'], yc - p['sv_len'] / 2, yc + p['sv_len'] / 2,
               -p['sv_wid'] / 2, p['sv_wid'] / 2)
    tabs = box(x_tab - p['sv_tab_t'], x_tab, yc - p['sv_tab_len'] / 2, yc + p['sv_tab_len'] / 2, -p['sv_wid'] / 2, p['sv_wid'] / 2)
    shaft = cyl((x_tab + p['sv_top'], 0, 0), (-g['x_out'] + P['horn_recess'], 0, 0), 4.8)
    return union(body, [tabs, shaft])


def make_mock_camera():
    p, g = P, geometry()
    pcb = box(-p['cam_w'] / 2, p['cam_w'] / 2, g['pcb_back'], g['pcb_back'] + p['cam_t'], -p['cam_h'] / 2, p['cam_h'] / 2)
    lens = box(-p['lens_side'] / 2, p['lens_side'] / 2, g['pcb_back'] + p['cam_t'], g['pcb_back'] + p['cam_t'] + p['lens_len'],
               p['lens_dz'] - p['lens_side'] / 2, p['lens_dz'] + p['lens_side'] / 2)
    # dau noi cap o mat sau, sat mep duoi (19.61 x 5.71, nho ra 2.75)
    conn = box(-9.8, 9.8, g['pcb_back'] - 2.75, g['pcb_back'], -p['cam_h'] / 2, -p['cam_h'] / 2 + 5.71)
    return union(pcb, [lens, conn])


def build(app):
    design = adsk.fusion.Design.cast(app.activeProduct)
    ours = design is not None and any(o.component.name == 'De_chu_U' for o in design.rootComponent.occurrences)
    if ours:
        # dung lai tai lieu khop gat dang mo: xoa cac khoi cu roi dung lai
        for o in list(design.rootComponent.occurrences):
            o.deleteMe()
    else:
        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root = design.rootComponent
    out = []
    for name, maker in (('De_chu_U', make_base), ('Gia_kep_camera', make_cradle),
                        ('THAM_KHAO_servo_MG90S (khong in)', make_mock_servo),
                        ('THAM_KHAO_camera (khong in)', make_mock_camera)):
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name
        b = occ.component.bRepBodies.add(maker())
        b.name = name
        bb = b.boundingBox
        size = [round((bb.maxPoint.x - bb.minPoint.x) / MM, 1), round((bb.maxPoint.y - bb.minPoint.y) / MM, 1),
                round((bb.maxPoint.z - bb.minPoint.z) / MM, 1)]
        out.append((name, size, round(b.volume * 1000, 0), b.isSolid))
    app.activeViewport.fit()
    return out
