"""Hinh dang muc tieu that (may bay mo hinh trainer canh tren) trong mo phong - buoc 1b, TEST VIET TRUOC (pha do).

Thiet ke ma cac test nay khoa:
  a) dtrack.config.TargetShapeConfig(span_m, length_m, height_m); mac dinh khoi 0.30^3 (giu hanh vi cu);
     AppConfig.target_shape; validate() tu choi gia tri khong duong.
  b) ham thuan target_bbox_size_px(rel_pos_ned, target_yaw_rad, target_pitch_rad, shape, fx, fy) -> (w_px, h_px)
     trong dtrack.synthetic (hoac dtrack.geometry). Quy uoc test dung:
       - rel_pos_ned = vi tri muc tieu TRU vi tri camera (NED, m); camera nhin thang vao tam muc tieu.
       - yaw = huong mui tu Bac theo chieu kim dong ho (rad); pitch duong = mui ngoc len; bo qua roll.
       - length_m doc mui, span_m ngang vuong goc mui, height_m theo phuong dung cua muc tieu.
       - ba canh bang nhau -> DUNG cong thuc cu 0.5*(fx+fy)*canh/khoang_cach, bbox vuong, khong phu thuoc huong.
  c) SyntheticDetector(camera, config, target_shape=...) ; khong co huong mui/van toc -> dang huong, canh lon nhat.
     SimTruthSource truyen tu the/van toc muc tieu xuong detector.
  d) MOT nguon: App dung RangeConfig.target_size_m = span_m, nguon mo phong dung cung target_shape.
  e) ho so moi accept_plane_r25 = accept_gimbal_r25 + target_shape (2.16, 1.50, 0.65); ho so cu giu nguyen.
  f) analyze_closed_loop dung kich thuoc tu app_cfg.json (khoa target_shape) thay cho literal 0.30.

So do (nguoi dung): sai canh 2.16, than 1.50, ban canh 0.32, than rong 0.18, cao 0.60-0.70 (lay 0.65).
Ban canh va be rong than CHUA dung o buoc nay: hop bao ba canh lam bbox lon hon hinh that o cac goc cheo
(gioi han da biet, xem test goc cheo 45 do).
"""
import dataclasses
import json
import math
import os
import sys
import time
from types import SimpleNamespace

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import dtrack.config as C  # noqa: E402
import dtrack.synthetic as SYN  # noqa: E402
from dtrack.app import App, build_source  # noqa: E402
from dtrack.config import AppConfig, load_config, load_profile, validate  # noqa: E402
from dtrack.range_estimator import RangeConfig, RangeEstimator  # noqa: E402
from dtrack.synthetic import SyntheticConfig, SyntheticDetector  # noqa: E402
from dtrack.types import CameraModel, OwnState  # noqa: E402

FX = 1739.13                    # px, lens 6 mm
SPAN, LENGTH = 2.16, 1.50       # m, do cua nguoi dung: sai canh 2.16, than dai 1.50
HEIGHT_M = 0.65                 # m, nguoi dung cho 0.60-0.70 (tu mat dat toi dinh duoi dung, ca cang); lay giua
PLANE = (SPAN, LENGTH, HEIGHT_M)
R = 25.0


def shape(span=SPAN, length=LENGTH, height=HEIGHT_M):
    return C.TargetShapeConfig(span_m=span, length_m=length, height_m=height)


def bbox_fn():
    for mod in (SYN, __import__("dtrack.geometry", fromlist=["x"])):
        fn = getattr(mod, "target_bbox_size_px", None)
        if fn is not None:
            return fn
    raise AssertionError("target_bbox_size_px chua co trong dtrack.synthetic / dtrack.geometry")


def bbox(rel, yaw=0.0, pitch=0.0, shp=None, fx=FX, fy=FX):
    return bbox_fn()(rel, yaw, pitch, shp or shape(), fx, fy)


def rel_at(dist, azimuth_deg=0.0, depression_deg=0.0):
    """Muc tieu cach dist m, phuong vi azimuth (tu Bac), nam THAP hon camera depression do."""
    a, d = math.radians(azimuth_deg), math.radians(depression_deg)
    return (dist * math.cos(d) * math.cos(a), dist * math.cos(d) * math.sin(a), dist * math.sin(d))


# ---------------------------------------------------------------- cau hinh
def test_target_shape_default_is_old_030_cube():
    s = AppConfig().target_shape
    assert (s.span_m, s.length_m, s.height_m) == (0.30, 0.30, 0.30)


@pytest.mark.parametrize("field", ["span_m", "length_m", "height_m"])
@pytest.mark.parametrize("bad", [0.0, -0.5])
def test_validate_rejects_nonpositive_shape(field, bad):
    cfg = AppConfig()
    setattr(cfg.target_shape, field, bad)
    with pytest.raises(ValueError):
        validate(cfg)


def test_load_config_json_reads_target_shape_and_rejects_unknown_key(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"target_shape": {"span_m": 2.16, "length_m": 1.50, "height_m": 0.65}}))
    s = load_config(str(p)).target_shape
    assert (s.span_m, s.length_m, s.height_m) == PLANE
    p.write_text(json.dumps({"target_shape": {"span_m": 2.16, "wing_m": 1.0}}))
    with pytest.raises(ValueError):
        load_config(str(p))


def test_plane_profile_valid_and_equals_gimbal_profile_except_shape():
    plane, old = load_profile("accept_plane_r25"), load_profile("accept_gimbal_r25")
    s = plane.target_shape
    assert (s.span_m, s.length_m, s.height_m) == PLANE
    assert plane.guidance.range_set_m == 25.0 and plane.guidance.range_back_m == 15.0
    assert plane.camera.gimbal_enabled is True and plane.guidance.elev_accel_comp == 0.0
    a, b = dataclasses.asdict(plane), dataclasses.asdict(old)
    a.pop("target_shape"), b.pop("target_shape")
    assert a == b                                   # chi khac target_shape
    validate(plane)


def test_plane_profile_dict_loads_through_load_config(tmp_path):
    p = tmp_path / "plane.json"
    p.write_text(json.dumps(C.profile_dict("accept_plane_r25")))
    assert dataclasses.asdict(load_config(str(p))) == dataclasses.asdict(load_profile("accept_plane_r25"))


def test_old_gimbal_profile_untouched():
    assert C.PROFILES["accept_gimbal_r25"] == {"guidance": {"range_set_m": 25.0, "range_back_m": 15.0},
                                               "camera": {"gimbal_enabled": True}}
    s = load_profile("accept_gimbal_r25").target_shape
    assert (s.span_m, s.length_m, s.height_m) == (0.30, 0.30, 0.30)


# ------------------------------------------------------ hinh hoc: bbox hop
# Gia tri ky vong = CHIEU DU 8 DINH (phoi canh day du), khong phai xap xi o do sau tam (150.26 x 45.22 sau; 104.35 ngang).
# Chung toi tinh bang script doc lap (ref_box.py, numpy) va khop ham san pham; dung sai 2% de PHAN BIET hai cach tinh
# (xap xi do sau tam lech ~3-4.5%).
def test_rear_view_25m_w_155_h_47():
    # 8 dinh: 154.91 x 46.62 (mat gan 24.25 m to hon tam: +3.1% so voi 150.26 x 45.22)
    w, h = bbox(rel_at(R))
    assert w == pytest.approx(154.91, rel=0.02)
    assert h == pytest.approx(46.62, rel=0.02)


def test_front_view_same_as_rear_view():
    w0, h0 = bbox(rel_at(R), yaw=0.0)
    w1, h1 = bbox(rel_at(R), yaw=math.pi)
    assert w1 == pytest.approx(w0, rel=0.01) and h1 == pytest.approx(h0, rel=0.01)


def test_side_view_25m_w_is_fuselage_length_109():
    # may bay huong Dong, camera o phia Nam nhin len Bac: thay than dai 1.50 m. 8 dinh: 109.06 x 47.26
    # (xap xi tam 104.35 x 45.22; mat gan +4.5%).
    w, h = bbox(rel_at(R), yaw=math.pi / 2)
    assert w == pytest.approx(109.06, rel=0.02)
    assert h == pytest.approx(47.26, rel=0.02)
    assert w < bbox(rel_at(R), yaw=0.0)[0]


def test_oblique_45deg_width_is_sum_of_projected_half_extents():
    # |2.16*cos45| + |1.50*sin45| = 2.588 m -> 180.03 px (tinh tay); 8 dinh: 180.05 x 47.69.
    # Day la HOP BAO: bbox lon hon hinh that (canh mong 0.32 m, than 0.18 m) o goc cheo - gioi han da biet cua buoc nay.
    w, h = bbox(rel_at(R), yaw=math.radians(45))
    assert w == pytest.approx(180.05, rel=0.02)
    assert h == pytest.approx(47.69, rel=0.02)


def test_view_from_above_20deg_adds_foreshortened_top_face():
    # cao hinh chieu = L*sin20 + H*cos20 = 0.513 + 0.611 = 1.124 m -> 78.18 px (tinh tay); 8 dinh: 155.33 x 78.22
    w, h = bbox(rel_at(R, depression_deg=20.0))
    _, h_level = bbox(rel_at(R))
    assert w == pytest.approx(155.33, rel=0.02)
    assert h == pytest.approx(78.22, rel=0.02)
    assert h > 1.5 * h_level


def test_view_from_above_behind_12deg_is_the_planned_tracking_pose():
    # the bam se dung (sau-tren 12 do): cao = L*sin12 + H*cos12 = 0.312 + 0.636 = 0.948 m -> 65.9 px; 8 dinh: 155.24 x 65.97
    w, h = bbox(rel_at(R, depression_deg=12.0))
    assert w == pytest.approx(155.24, rel=0.02)
    assert h == pytest.approx(65.97, rel=0.02)


def test_nose_down_25deg_seen_from_rear():
    # cao = L*sin25 + H*cos25 = 0.634 + 0.589 = 1.223 m -> 85.1 px; rong = sai canh (truc mui nam trong mat phang dung
    # chua duong ngam, nen khong them be rong): 155.3. 8 dinh (ref_box.py va ham san pham): 155.34 x 85.12.
    # LUU Y: bao cao cua 08 neu 172.64 x 73.47 cho ca nay; KHONG khop tinh tay/ref_box.py -> da bao truong phong, chua giai quyet.
    w, h = bbox(rel_at(R), pitch=math.radians(-25.0))
    assert w == pytest.approx(155.34, rel=0.02)
    assert h == pytest.approx(85.12, rel=0.02)


@pytest.mark.parametrize("pitch_deg", [30.0, -30.0])
def test_nose_pitched_30deg_seen_from_rear_height_grows_both_signs(pitch_deg):
    # cao = L*sin30 + H*cos30 = 0.750 + 0.563 = 1.313 m -> 91.3 px (tinh tay); 8 dinh 155.31 x 91.37; doi xung len/xuong
    w, h = bbox(rel_at(R), pitch=math.radians(pitch_deg))
    assert w == pytest.approx(155.31, rel=0.02)
    assert h == pytest.approx(91.37, rel=0.02)


def test_view_direction_in_azimuth_does_not_matter_when_heading_follows():
    # camera nhin thang vao tam: xoay ca canh (huong ngam va huong mui cung 45 do) khong doi bbox
    w0, h0 = bbox(rel_at(R))
    w1, h1 = bbox(rel_at(R, azimuth_deg=45.0), yaw=math.radians(45))
    assert w1 == pytest.approx(w0, rel=0.01) and h1 == pytest.approx(h0, rel=0.01)


def test_bbox_scales_inversely_with_distance():
    # phoi canh lam w*r lech <= 3% (r=25..100 m, nua do dai may bay 0.9 m); dung sai 5%
    prod = []
    for r in (25.0, 50.0, 100.0):
        w, h = bbox(rel_at(r))
        prod.append((w * r, h * r))
    for k in (0, 1):
        vals = [p[k] for p in prod]
        assert max(vals) / min(vals) < 1.05
    w25, _ = bbox(rel_at(25.0))
    w100, _ = bbox(rel_at(100.0))
    assert w25 / w100 == pytest.approx(4.0, rel=0.05)


def test_fx_fy_scale_axes_independently():
    w, h = bbox(rel_at(R), fx=2000.0, fy=1000.0)
    assert w == pytest.approx(178.14, rel=0.02)      # 8 dinh (xap xi tam 172.8)
    assert h == pytest.approx(26.80, rel=0.02)       # (xap xi tam 26.0)


@pytest.mark.parametrize("yaw,pitch,rel", [(0.0, 0.0, rel_at(20.0)), (1.1, 0.4, rel_at(33.0, 30.0, 10.0)),
                                           (math.pi / 2, -0.7, rel_at(50.0, -80.0, -15.0))])
def test_equal_edges_keep_old_formula_square_and_orientation_free(yaw, pitch, rel):
    # ba canh bang nhau (hop mac dinh 0.30) -> DUNG cong thuc cu 0.5*(fx+fy)*0.30/r, bbox vuong, bat ke huong
    r = math.sqrt(sum(c * c for c in rel))
    w, h = bbox(rel, yaw, pitch, shape(0.30, 0.30, 0.30), fx=1739.0, fy=1739.0)
    assert w == pytest.approx(1739.0 * 0.30 / r, rel=1e-6)
    assert h == pytest.approx(w, rel=1e-9)
    w2, h2 = bbox(rel, yaw, pitch, shape(0.30, 0.30, 0.30), fx=1800.0, fy=1600.0)
    assert w2 == pytest.approx(0.5 * (1800.0 + 1600.0) * 0.30 / r, rel=1e-6)   # fx != fy: trung binh nhu cu
    assert h2 == pytest.approx(w2, rel=1e-9)


# ------------------------------------------- detector tong hop (SyntheticDetector)
NOISELESS = dict(center_sigma_px=0.0, size_sigma_px=0.0, p_miss=0.0, p_false=0.0, latency_s=0.0, frame_rate_hz=30.0)
OWN0 = OwnState(t=0.0, pos_ned=(0.0, 0.0, 0.0), vel_ned=(0.0, 0.0, 0.0), q_world_body=(1.0, 0.0, 0.0, 0.0))


def test_detector_without_heading_or_velocity_is_isotropic_largest_edge():
    det = SyntheticDetector(CameraModel(fx=FX, fy=FX), SyntheticConfig(**NOISELESS), target_shape=shape())
    d = det.process(0.0, rel_at(R), OWN0)[0]
    assert d.w == pytest.approx(FX * SPAN / R, rel=1e-6)       # canh lon nhat = span 2.16 m
    assert d.h == pytest.approx(d.w, rel=1e-9)


def test_detector_default_shape_keeps_old_size():
    det = SyntheticDetector(CameraModel(fx=FX, fy=FX), SyntheticConfig(**NOISELESS))
    d = det.process(0.0, rel_at(R), OWN0)[0]
    assert d.w == pytest.approx(FX * 0.30 / R, rel=1e-6) and d.h == pytest.approx(d.w, rel=1e-9)


# ------------------------------------- MOT nguon: App + SimTruthSource tu AppConfig
class FakeReader:
    """Thay SimStateReader (ranh gioi mang/MAVLink): tra tuple SIM_STATE tu bang lop, khong mo ket noi."""
    states = {}

    def __init__(self, url, rate_hz=50.0, clock=time.monotonic, connect_timeout=60.0):
        self.url = url

    @property
    def last(self):
        return (time.monotonic(),) + tuple(FakeReader.states[self.url])

    def poll(self):
        pass

    def close(self):
        pass


def _plane_cfg():
    cfg = AppConfig()
    cfg.target_shape = shape()
    return cfg


def _sim_widths(monkeypatch, cfg, body_yaw, tgt_v_ned, n=25, body_pitch=0.0):
    """Dung nguon qua build_source(args, cfg) nhu app that; muc tieu o 25 m phia Bac chaser cung do cao.
    body_yaw/body_pitch = tu the THAN copter muc tieu (SIM_STATE) - co y cho khac huong van toc."""
    import simtools.sim_truth_source as sts
    from dtrack.mavlink_io import latlon_to_ned
    monkeypatch.setattr(sts, "SimStateReader", FakeReader)
    lat0, lon0 = -35.0, 149.0
    n0, e0 = latlon_to_ned(lat0, lon0, lat0 + 1e-4, lon0 + 1e-4)
    lat, lon = lat0 + 1e-4 * R / n0, lon0
    # (lat, lon, alt_msl, vn, ve, vd, roll, pitch, yaw)
    FakeReader.states = {"T": (lat, lon, 100.0) + tuple(tgt_v_ned) + (0.0, body_pitch, body_yaw),
                         "C": (lat0, lon0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)}
    args = SimpleNamespace(source="sim", sim_target="T", sim_chaser="C", sim_seed=7, sim_blackout_file=None)
    src = build_source(args, cfg)
    ws, hs, t_end = [], [], time.monotonic() + 5.0
    while len(ws) < n and time.monotonic() < t_end:
        for d in src.poll():
            if d.w > 50.0:             # bo phat hien gia (p_false; bbox gia <= 40 px) lam lech trung vi
                ws.append(d.w), hs.append(d.h)
        time.sleep(0.004)
    assert len(ws) >= n, "nguon mo phong khong tra du phat hien"
    ws.sort(), hs.sort()
    return ws[len(ws) // 2], hs[len(hs) // 2]

def test_app_range_size_comes_from_target_shape_span():
    cfg = _plane_cfg()
    app = App(cfg, source=None, link=None)
    assert app.tracker.range.cfg.target_size_m == SPAN
    assert App(AppConfig(), source=None, link=None).tracker.range.cfg.target_size_m == 0.30


def test_plane_profile_estimator_and_source_cannot_disagree_on_size(monkeypatch):
    # tu hai phia cung mot cfg: kich thuoc ngam trong bbox nguon (w*r/f, nhin tu sau) == kich thuoc cua bo uoc luong
    cfg = load_profile("accept_plane_r25")
    cfg.camera.gimbal_enabled = False      # tranh mo hinh khop gat; hinh hoc nguon khong doi
    app = App(cfg, source=None, link=None)
    w, _ = _sim_widths(monkeypatch, cfg, 0.0, (10.0, 0.0, 0.0))
    implied = w * R / app.tracker.range.f
    assert implied == pytest.approx(app.tracker.range.cfg.target_size_m, rel=0.06)


def test_sim_source_rear_vs_side_view_from_target_velocity(monkeypatch):
    cfg = _plane_cfg()
    w_rear, h_rear = _sim_widths(monkeypatch, cfg, 0.0, (10.0, 0.0, 0.0))     # bay ra xa theo Bac
    w_side, h_side = _sim_widths(monkeypatch, cfg, 0.0, (0.0, 10.0, 0.0))     # bay ngang theo Dong (than yaw 0!)
    assert (w_rear, h_rear) == pytest.approx((154.91, 46.62), rel=0.02)
    assert (w_side, h_side) == pytest.approx((109.05, 47.26), rel=0.02)


def test_sim_source_uses_velocity_not_copter_body_pose(monkeypatch):
    # muc tieu that la may bay canh co dinh: mui theo huong bay. Than copter mo phong chui mui -10 do, yaw 0 (de bay),
    # nhung van toc huong Dong va cam 25 do -> bbox phai theo van toc: yaw 90, pitch -25: 118.80 x 88.91 (fx 1739; 8 dinh)
    cfg = _plane_cfg()
    v = (0.0, 10.0 * math.cos(math.radians(25)), 10.0 * math.sin(math.radians(25)))
    w, h = _sim_widths(monkeypatch, cfg, 0.0, v, body_pitch=math.radians(-10.0))
    assert (w, h) == pytest.approx((118.80, 88.91), rel=0.02)


def test_sim_source_dive_25deg_from_directly_behind_matches_nose_down_case(monkeypatch):
    # van toc 10 m/s cam 25 do, may bam o chinh sau cung do cao (than copter nam ngang) -> nhu ca mui chui 25 do tu sau
    cfg = _plane_cfg()
    v = (10.0 * math.cos(math.radians(25)), 0.0, 10.0 * math.sin(math.radians(25)))
    w, h = _sim_widths(monkeypatch, cfg, 0.0, v)
    assert (w, h) == pytest.approx((155.34, 85.12), rel=0.02)      # xem luu y ve 172.64 x 73.47 cua 08 o tren


def test_sim_source_slow_target_is_isotropic_largest_edge(monkeypatch):
    # toc do 0.5 m/s <= 1 m/s: khong suy huong -> dang huong, canh lon nhat (2.16 m): 1739*2.16/25 = 150.3 px, bbox vuong,
    # du than copter yaw 90 / pitch 30 do (khong duoc dung)
    cfg = _plane_cfg()
    w, h = _sim_widths(monkeypatch, cfg, math.pi / 2, (0.5, 0.0, 0.0), body_pitch=math.radians(30.0))
    assert w == pytest.approx(1739.0 * SPAN / R, rel=0.02)
    assert h == pytest.approx(w, rel=0.01)


# --------------------------- duong mac dinh co nhieu + RNG: dung hanh vi cu
def _det_stream(det, n=250, **kw):
    out = []
    for i in range(n):
        rel = (15.0 + 0.1 * i, 0.3 * math.sin(i / 7.0), 0.4 * math.cos(i / 5.0))     # truoc mui, trong khung
        out.append(det.process(i / 30.0, rel, OWN0, **kw))
    return out


def test_default_path_with_noise_identical_to_cube_shape_detector_and_old_formula():
    cfg = dict(seed=3, latency_s=0.0)
    cam = CameraModel()
    a = _det_stream(SyntheticDetector(cam, SyntheticConfig(**cfg)))
    # detector co target_shape = khoi 0.30^3: PHAI ra chuoi y het (ke ca khi duoc cap huong mui/van toc)
    b = _det_stream(SyntheticDetector(cam, SyntheticConfig(**cfg), target_shape=C.TargetShapeConfig()),
                    heading=(0.7, 0.3), target_vel_ned=(5.0, 3.0, 1.0))
    assert a == b                                       # Detection la dataclass dong bang: so tung so (cx, cy, w, h, conf)
    assert sum(len(x) for x in a) > 150
    # cong thuc cu + dung nhieu da rut: tai lap RNG theo thu tu rut cua _make_frame
    rng = SyntheticConfig(**cfg)
    import numpy as np
    g = np.random.default_rng(rng.seed)
    n_checked = 0
    for i, dets in enumerate(a):
        r_miss = g.random(); noise = g.normal(size=4); conf = g.normal(rng.true_conf_mean, rng.true_conf_sigma)
        g.random(); g.random(4); g.normal(rng.false_conf_mean, rng.false_conf_sigma)
        if r_miss < rng.p_miss:
            continue
        r = math.sqrt(sum(c * c for c in (15.0 + 0.1 * i, 0.3 * math.sin(i / 7.0), 0.4 * math.cos(i / 5.0))))
        size = 0.5 * (cam.fx + cam.fy) * 0.30 / r
        d = dets[0]
        assert d.w == pytest.approx(max(1.0, size + rng.size_sigma_px * noise[2]), rel=1e-9)
        assert d.h == pytest.approx(max(1.0, size + rng.size_sigma_px * noise[3]), rel=1e-9)
        assert d.conf == pytest.approx(min(1.0, max(0.0, conf)), rel=1e-9)
        n_checked += 1
    assert n_checked > 150

# ------------------------------------------- uoc luong khoang cach bang bbox that
def _estimate_r(est, rel, yaw):
    w, h = bbox(rel, yaw)
    s, _ = est.measure_size_px(w, h)                  # measure_size_px THAT: hai canh khac xa -> lay canh lon
    return est.f * est.cfg.target_size_m / s


def _plane_estimator():
    app = App(load_profile("accept_plane_r25"), source=None, link=None)
    est = RangeEstimator(FX, RangeConfig(target_size_m=app.cfg.target_shape.span_m))
    return est


def test_range_estimate_from_behind_25m_within_5_percent():
    r = _estimate_r(_plane_estimator(), rel_at(R), 0.0)
    assert r == pytest.approx(R, rel=0.05)


def test_range_estimate_broadside_is_known_far_bias_35_to_50_percent():
    # HANH VI DA BIET (khong phai loi): nhin ngang canh lon la than 1.50 m nhung bo uoc luong gia dinh 2.16 m
    # -> r that bi bao XA hon ~2.16/1.50 = +44% (tru phoi canh gan ~4.5% -> ~+38%). Ghi nhan trong dai 35-50%.
    r = _estimate_r(_plane_estimator(), rel_at(R), math.pi / 2)
    assert 1.35 * R <= r <= 1.50 * R, "r_est/r = %.3f" % (r / R)


def test_range_estimate_oblique_45deg_underestimates_due_to_bounding_box():
    # GHI NHAN GIOI HAN (khong phai loi): w hop bao 45 do = 180.0 px > than thuc cua may bay -> r = f*2.16/180.0 = 20.9 m,
    # tuc bao GAN hon ~16.5% (r_est/r = 0.835; dai 0.78-0.88). Luong hoa van de cho buoc sau (dung ban canh/be rong than).
    r = _estimate_r(_plane_estimator(), rel_at(R), math.radians(45))
    assert 0.78 * R <= r <= 0.88 * R, "r_est/r = %.3f" % (r / R)


# --------------------------- analyze_closed_loop: kich thuoc tu cau hinh cua lan chay
def _b4_size_px(tmp_path, capsys, app_cfg):
    import test_analyze_closed_loop as tacl
    out = tacl.make_run(tmp_path)                      # d3 = 25 m khong doi trong cua so
    (tmp_path / "app_cfg.json").write_text(json.dumps(app_cfg))
    _, text = tacl.run(out, capsys)
    line = next(ln for ln in text.splitlines() if ln.startswith("B4JSON "))
    return json.loads(line[len("B4JSON "):])["size_px_med"]


def test_analyze_uses_target_span_from_app_cfg(tmp_path, capsys):
    cfg = {"camera": {"fx": FX}, "target_shape": {"span_m": 2.16, "length_m": 1.50, "height_m": 0.65}}
    assert _b4_size_px(tmp_path, capsys, cfg) == pytest.approx(FX * 2.16 / 25.0, rel=1e-3)   # 150.26 px


def test_analyze_without_target_shape_keeps_old_030(tmp_path, capsys):
    assert _b4_size_px(tmp_path, capsys, {"camera": {"fx": FX}}) == pytest.approx(FX * 0.30 / 25.0, rel=1e-3)
