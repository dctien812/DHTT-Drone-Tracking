"""Cong cu dung bao cao hinh anh tu log mot lan mo phong: simtools/report_run.py.
TEST VIET TRUOC (pha do): module chua ton tai, moi ca phai loi ModuleNotFoundError khi nap fixture `rr`.

GIAO DIEN CAC TEST NAY KHOA (lop (a), ham thuan, khong ve). run_dir la str hoac pathlib.Path.
  load_run(run_dir) -> RunData
      RunData co cac thuoc tinh:
        .run_dir  : str duong dan; .name : ten thu muc (basename), vd "20261118_170437_10ms_s1_none"
        .truth    : dict ten_cot -> np.ndarray float (moi cot cua truth.csv). BO MOI dong hong (nhu drop_bad_rows cua
                    bo cham): dong thieu cot, hoac o cac cot so (t, tgt_*, ch_n/e/alt, ch_roll/pitch/yaw, d3) co
                    gia tri rong / khong doc duoc / NaN, o BAT KY vi tri nao (ke ca giua file).
        .events   : dict (events.json; thieu file -> {})
        .cfg      : dict (app_cfg.json; thieu file -> {})
        .gimbal   : None neu khong co gimbal.csv; nguoc lai doi tuong co .t (s), .delta_rad (rad, tu cot
                    delta_act_deg KHONG phai delta_cmd_deg), .sat (bool, sat>0); bo dong cuoi bi cat cut.
      Thieu truth.csv -> FileNotFoundError.
  target_pixels(run) -> (t, u, v, in_frame)   bon np.ndarray cung do dai voi truth["t"]
      Hinh hoc y het bo cham (analyze_closed_loop.b4_metrics): fx/width/height lay tu cfg["camera"]
      (mac dinh 1739, 1456, 1088); tam anh (W/2, H/2); u = fx*x/z + W/2, v = fx*y/z + H/2 trong he camera
      (x phai, y xuong, z truc quang). Camera:
        - cfg["gimbal"]["enabled"] truthy VA co gimbal.csv: camera_attitude(q_than, delta) voi delta = np.interp
          THEO THOI GIAN delta_act, bo qua camera.tilt_up_deg (dung make_camera(0)). KHONG kep hai dau: mau truth
          nam ngoai [t_gimbal[0], t_gimbal[-1]] (dung sai 1e-6 s) hoac trong khoang trong giua hai dong gimbal
          lien tiep > 0.5 s (+1e-9; mau trung dung thoi diem mot dong thi tinh la co) -> u = v = NaN,
          in_frame=False (cung nguong va cach xac dinh voi analyze_closed_loop.gimbal_series, nhung ap cho MOI
          mau truth va KHONG nem loi).
        - nguoc lai (khong co gimbal.csv, hoac cfg khong bat gimbal): camera co dinh make_camera(tilt_up_deg),
          tilt_up_deg = cfg["camera"]["tilt_up_deg"], mac dinh 15.
      Diem sau camera (z <= 1e-6): in_frame=False, u = v = NaN. Con lai in_frame = 0<=u<=W va 0<=v<=H
      (bao gom bien); u, v van la so huu han ke ca khi ra khung.
      Goc than (roll, pitch, yaw) lay tu cot ch_roll/ch_pitch/ch_yaw (RAD); vector tu chaser den muc tieu NED =
      (tgt_n-ch_n, tgt_e-ch_e, -(tgt_alt-ch_alt)).
  phases(run, dive_after=5.0) -> dict ten_pha -> (t0, t1)   (cung moc voi bo cham; float giay)
      t_go, t_stop = events["t_go"], events["t_stop_target"]; t_end = events["t_both_stopped"] hoac truth t cuoi;
      t90 = mau dau tien T >= t_go co toc do ngang muc tieu >= 0.9*events["speed"] (khong co, hoac events thieu
      "speed" -> t_stop; quyet dinh cua test vi bo cham nhan speed tu dong lenh).
      Co events["t_dive_cmd"]: tang_toc (t_go,t90), bam_on_dinh (t90,t_dive), cam_xuong (t_dive,t_cut),
         bay_bang (t_cut,t_stop), giam_toc_cuoi (t_stop,t_end); t_cut = min(t_dive_end+dive_after, t_stop);
         t_dive_end = mau dau tien sau dinh tgt_vd (trong [t_dive,t_stop]) co tgt_vd < 0.5 (nghiem ngat).
      Khong dive: tang_toc (t_go,t90), bam_on_dinh (t90,t_stop), phanh_cuoi (t_stop,t_end).
      Thieu t_go hoac t_stop_target -> {}.
  gimbal_gaps(run) -> list[(t0, t1)]   cac doan khong do duoc (de to xam), theo thu tu thoi gian:
      (truth t dau, t_gimbal[0]) neu truth bat dau truoc gimbal.csv; (t_i, t_i+1) cho moi cap dong gimbal lien
      tiep cach > 0.5 s; (t_gimbal[-1], truth t cuoi) neu truth keo dai sau gimbal.csv. Camera co dinh
      (khong co gimbal.csv hoac cfg khong bat gimbal) -> [].
  VONG 2 (08 ra loi tren ma da co):
  run.unsupported : str ly do (khac rong) hoac None. Gan khi cau hinh bat khop ma khong dung duoc: (i) kieu cu
      cfg["camera"]["gimbal_enabled"] truthy KHONG kem cfg["gimbal"]["enabled"]; (ii) cfg["gimbal"]["enabled"] truthy
      nhung gimbal.csv thieu/hong. Khi unsupported: target_pixels tra u, v = NaN, in_frame = False cho moi mau;
      load_run khong nem loi; hinh/HTML ghi ro ly do va khong in so ra khung. Camera co dinh that su (cfg khong bat
      khop) hoac gimbal.enabled + csv tot -> unsupported = None.
  out_of_frame_stats(run, t0, t1) -> (so_lan, so_giay) | None   thong ke ra khung trong [t0, t1] (cong thuc cua bo
      cham: so canh len + mau dau, giay = tong khoang giua mau ra khung va mau ke sau). KHONG tinh mau khong do duoc
      (ngoai dai/khoang trong gimbal.csv); mau SAU camera van tinh la ra khung (bo cham tinh vay). Khong co mau
      nao trong cua so -> None.
  effective_gimbal_limits(run) -> (delta_min_deg, delta_max_deg) tung can, uu tien: cfg["gimbal"]["delta_min_deg"|
      "delta_max_deg"] ghi ro -> suy tu cac mau gimbal.csv co sat>0 (can tren = max delta_act cua mau sat nam tren
      trung vi delta_act toan file; can duoi = min delta_act cua mau sat nam duoi trung vi) -> mac dinh (10.0, 110.0).
  render_batch: moi lan chay duoc boc rieng; lan loi (thieu cot truth, cfg gia tri null...) van co mot hang trong
      bang voi chu "loi dung hinh" va ly do; cac lan tot van co hinh; HTML luon duoc ghi. <img src> la URL da ma hoa
      (urllib.parse.quote) cua ten file PNG nam canh file HTML, roi html.escape.
  saturation_spans(run) -> list[(t0, t1)]   moi doan lien tiep cac dong gimbal.csv co sat>0:
      t0 = t dong sat dau doan; t1 = t dong KE SAU doan (dong sat=0 dau tien); doan chay toi het file thi t1 = t dong cuoi.
      Khong co gimbal.csv -> [].
  parse_result(run_dir) -> (verdict, [(ten_tieu_chi, "PASS"|"FAIL", chi_tiet), ...])
      Dong "[PASS] ten: chi tiet" / "[FAIL] ten: chi tiet" (tach o ": " dau tien), theo thu tu file; dong khac
      ("[tham khao]", so lieu...) bo qua. verdict = tu dau tien sau "KET QUA: " ("PASS"/"FAIL"); thieu
      result.txt hoac thieu dong KET QUA -> verdict None (khong nem loi).
  render_run(run_dir, out_png) -> None; ghi PNG (backend Agg), ke ca khi khong co gimbal.csv.
  render_batch(run_dirs, out_html) -> None; ghi HTML co ten moi lan chay va chu PASS/FAIL cua ket qua.
  (Lenh `python -m simtools.report_run <run_dir>...` va noi ghi dau ra mac dinh KHONG duoc test khoi o day.)

Du lieu mau dung trong tmp_path. Gia tri ky vong tinh doc lap bang luong giac (tan, sin, cos) va truc quang
hinh hoc cua dtrack/gimbal.py: truc quang trong than (sin d, 0, -cos d); goc nang truc quang = 90 - d + pitch (do).
Chaser o do cao 100 m, huong bac (yaw 0), nen "phia truoc" = +N, "phai" = +E, "len" = -alt.
"""
import csv
import json
import math
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, ".."), os.getcwd(), os.path.join(os.getcwd(), "tests"), HERE):
    sys.path.insert(0, p)

FX, W, H = 1739.0, 1456, 1088
CX, CY = W / 2.0, H / 2.0
TRUTH_COLS = ["t", "tgt_n", "tgt_e", "tgt_alt", "tgt_vn", "tgt_ve", "tgt_vd", "ch_n", "ch_e", "ch_alt",
              "ch_vn", "ch_ve", "ch_vd", "ch_roll", "ch_pitch", "ch_yaw", "d3", "dh", "ch_armed", "ch_mode"]
GCOLS = ["t", "mode", "delta_cmd_deg", "delta_act_deg", "delta_rate_dps", "elev_los_deg", "elev_aim_deg",
         "elev_ref_deg", "sat", "theta_deg"]
GIMBAL_ON = {"gimbal": {"enabled": True}}
CH_ALT = 100.0


@pytest.fixture
def rr():
    from simtools import report_run
    return report_run


# ---------------------------------------------------------------- du lieu mau
def truth_row(t, n=15.0, e=0.0, up=0.0, roll=0.0, pitch=0.0, yaw=0.0, vn=0.0, vd=0.0):
    """Chaser o (0, 0, CH_ALT); muc tieu o n (bac), e (dong), up (m phia tren chaser) so voi chaser."""
    d3 = math.sqrt(n * n + e * e + up * up)
    r = {"t": t, "tgt_n": n, "tgt_e": e, "tgt_alt": CH_ALT + up, "tgt_vn": vn, "tgt_ve": 0.0, "tgt_vd": vd,
         "ch_n": 0.0, "ch_e": 0.0, "ch_alt": CH_ALT, "ch_vn": 0.0, "ch_ve": 0.0, "ch_vd": 0.0,
         "ch_roll": roll, "ch_pitch": pitch, "ch_yaw": yaw, "d3": d3, "dh": math.hypot(n, e),
         "ch_armed": 1, "ch_mode": 4}
    return r


def write_run(root, name, truth_rows, gimbal=None, events=None, cfg=None, result=None):
    """gimbal: list (t, delta_act_deg, sat). delta_cmd_deg = delta_act + 7 de bat loi doc nham cot."""
    d = os.path.join(str(root), name)
    os.makedirs(d)
    with open(os.path.join(d, "truth.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(TRUTH_COLS)
        for r in truth_rows:
            w.writerow([repr(float(r[c])) if c != "ch_armed" and c != "ch_mode" else r[c] for c in TRUTH_COLS])
    if gimbal is not None:
        with open(os.path.join(d, "gimbal.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(GCOLS)
            for t, da, sat in gimbal:
                w.writerow([repr(float(t)), "track", repr(da + 7.0), repr(float(da)), "0.0", "", "", "", sat, "0.0"])
    if events is not None:
        with open(os.path.join(d, "events.json"), "w") as f:
            json.dump(events, f)
    if cfg is not None:
        with open(os.path.join(d, "app_cfg.json"), "w") as f:
            json.dump(cfg, f)
    if result is not None:
        with open(os.path.join(d, "result.txt"), "w") as f:
            f.write(result)
    return d


def append_raw(d, fname, text):
    with open(os.path.join(d, fname), "a", newline="") as f:
        f.write(text)


def pixels(rr, tmp_path, rows, gimbal=None, cfg=None, name="r"):
    d = write_run(tmp_path, name, rows, gimbal=gimbal, cfg=cfg, events={})
    return rr.target_pixels(rr.load_run(d))


def level_gimbal(delta_deg=90.0, t_end=10.0):
    """delta khong doi, dong moi 0.5 s tu 0 toi t_end (khong co khoang trong > 0.5 s)."""
    return [(0.5 * i, delta_deg, 0) for i in range(int(round(t_end / 0.5)) + 1)]


def ahead_at_elev(elev_deg, rng=15.0):
    """(n, up) cua muc tieu o khoang cach rng, goc nang elev_deg tren duong chan troi, huong bac."""
    return rng * math.cos(math.radians(elev_deg)), rng * math.sin(math.radians(elev_deg))


# ---------------------------------------------------------------- load_run
def test_load_run_name_is_directory_basename(rr, tmp_path):
    d = write_run(tmp_path, "20261118_170437_10ms_s1_none", [truth_row(0.0)], events={})
    assert rr.load_run(d).name == "20261118_170437_10ms_s1_none"


def test_load_run_accepts_pathlib_path(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)], events={})
    from pathlib import Path
    assert rr.load_run(Path(d)).name == "r"


def test_load_run_truth_columns_are_float_arrays(rr, tmp_path):
    rows = [truth_row(0.5 * i, n=15.0 + i) for i in range(4)]
    run = rr.load_run(write_run(tmp_path, "r", rows, events={}))
    assert isinstance(run.truth["t"], np.ndarray)
    assert run.truth["t"].dtype.kind == "f"
    assert list(run.truth["t"]) == [0.0, 0.5, 1.0, 1.5]
    assert list(run.truth["tgt_n"]) == [15.0, 16.0, 17.0, 18.0]


def test_load_run_gimbal_uses_delta_act_in_radians_not_cmd(rr, tmp_path):
    g = [(0.0, 90.0, 0), (1.0, 60.0, 1), (2.0, 110.0, 0)]
    run = rr.load_run(write_run(tmp_path, "r", [truth_row(0.0)], gimbal=g, events={}))
    assert list(run.gimbal.t) == [0.0, 1.0, 2.0]
    assert np.allclose(run.gimbal.delta_rad, np.radians([90.0, 60.0, 110.0]), atol=1e-12)
    assert list(run.gimbal.sat) == [False, True, False]
    assert run.gimbal.sat.dtype == bool


def test_load_run_without_gimbal_csv_is_fixed_camera_not_error(rr, tmp_path):
    run = rr.load_run(write_run(tmp_path, "r", [truth_row(0.0)], events={}))
    assert run.gimbal is None


def test_load_run_reads_events_and_cfg(rr, tmp_path):
    ev = {"t_go": 12.5, "t_stop_target": 70.0, "speed": 10.0}
    cfg = {"camera": {"fx": 1000.0}, "gimbal": {"enabled": True}}
    run = rr.load_run(write_run(tmp_path, "r", [truth_row(0.0)], events=ev, cfg=cfg))
    assert run.events["t_go"] == 12.5
    assert run.cfg["camera"]["fx"] == 1000.0


def test_load_run_missing_events_and_cfg_give_empty_dicts(rr, tmp_path):
    run = rr.load_run(write_run(tmp_path, "r", [truth_row(0.0)]))
    assert run.events == {}
    assert run.cfg == {}


def test_load_run_drops_truncated_last_truth_row(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0), truth_row(0.5)], events={})
    append_raw(d, "truth.csv", "1.0,15.000,0.0")      # app/mo phong bi giet giua dong: thieu cot
    run = rr.load_run(d)
    assert list(run.truth["t"]) == [0.0, 0.5]
    assert all(len(v) == 2 for v in run.truth.values())


def test_load_run_drops_every_bad_truth_row_even_in_the_middle(rr, tmp_path):
    rows = [truth_row(0.5 * i, n=10.0 + i) for i in range(6)]
    d = write_run(tmp_path, "r", rows, events={})
    p = os.path.join(d, "truth.csv")
    lines = open(p).read().splitlines()
    cols = lines[0].split(",")
    k = cols.index("tgt_n")
    for idx, bad in ((2, ""), (4, "nan")):       # lines[0] la header: lines[2] = mau t=0.5 (rong), lines[4] = mau t=1.5 (NaN)
        f = lines[idx].split(",")
        f[k] = bad
        lines[idx] = ",".join(f)
    open(p, "w", newline="").write("\n".join(lines) + "\n")
    run = rr.load_run(d)
    assert list(run.truth["t"]) == [0.0, 1.0, 2.0, 2.5]
    assert list(run.truth["tgt_n"]) == [10.0, 12.0, 14.0, 15.0]
    assert all(len(v) == 4 for v in run.truth.values())


def test_load_run_drops_truncated_last_gimbal_row(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)], gimbal=[(0.0, 90.0, 0), (0.5, 80.0, 0)], events={})
    append_raw(d, "gimbal.csv", "1.0,track,87.0")
    run = rr.load_run(d)
    assert list(run.gimbal.t) == [0.0, 0.5]
    assert len(run.gimbal.delta_rad) == len(run.gimbal.sat) == 2


def test_load_run_missing_truth_csv_raises(rr, tmp_path):
    d = os.path.join(str(tmp_path), "r")
    os.makedirs(d)
    with pytest.raises(FileNotFoundError):
        rr.load_run(d)


# ---------------------------------------------------------------- target_pixels: hinh hoc
def test_target_on_boresight_maps_to_image_center(rr, tmp_path):
    # delta 90: truc quang nam ngang ve phia truoc; muc tieu thang truoc cung do cao
    rows = [truth_row(float(i), n=n) for i, n in enumerate([10.0, 15.0, 40.0])]
    t, u, v, ok = pixels(rr, tmp_path, rows, level_gimbal(90.0), GIMBAL_ON)
    assert list(t) == [0.0, 1.0, 2.0]
    assert np.allclose(u, CX, atol=1e-6) and np.allclose(v, CY, atol=1e-6)
    assert ok.all()


def test_target_on_tilted_boresight_maps_to_center(rr, tmp_path):
    # delta 70 -> truc quang len 20 do; muc tieu o goc nang 20 do
    n, up = ahead_at_elev(20.0)
    _, u, v, ok = pixels(rr, tmp_path, [truth_row(0.0, n=n, up=up)], level_gimbal(70.0), GIMBAL_ON)
    assert u[0] == pytest.approx(CX, abs=1e-6) and v[0] == pytest.approx(CY, abs=1e-6)
    assert ok[0]


def test_azimuth_offset_maps_to_pixel_through_fx(rr, tmp_path):
    az = math.radians(10.0)
    rows = [truth_row(0.0, n=15.0, e=15.0 * math.tan(az)), truth_row(1.0, n=15.0, e=-15.0 * math.tan(az))]
    _, u, v, ok = pixels(rr, tmp_path, rows, level_gimbal(90.0), GIMBAL_ON)
    assert u[0] == pytest.approx(CX + FX * math.tan(az), abs=1e-6)      # ben phai -> u lon hon
    assert u[1] == pytest.approx(CX - FX * math.tan(az), abs=1e-6)
    assert np.allclose(v, CY, atol=1e-6)
    assert ok.all()


def test_elevation_offset_maps_to_pixel_up_is_smaller_v(rr, tmp_path):
    el = math.radians(5.0)
    rows = [truth_row(0.0, n=15.0, up=15.0 * math.tan(el)), truth_row(1.0, n=15.0, up=-15.0 * math.tan(el))]
    _, u, v, _ = pixels(rr, tmp_path, rows, level_gimbal(90.0), GIMBAL_ON)
    assert v[0] == pytest.approx(CY - FX * math.tan(el), abs=1e-6)      # muc tieu cao hon truc -> v nho hon
    assert v[1] == pytest.approx(CY + FX * math.tan(el), abs=1e-6)
    assert np.allclose(u, CX, atol=1e-6)


def test_body_pitch_up_raises_boresight_elevation(rr, tmp_path):
    # delta 90, pitch +0.2 rad (mui len): goc nang truc quang = 0.2 rad
    p = 0.2
    n, up = 15.0 * math.cos(p), 15.0 * math.sin(p)
    _, u, v, _ = pixels(rr, tmp_path, [truth_row(0.0, n=n, up=up, pitch=p)], level_gimbal(90.0), GIMBAL_ON)
    assert u[0] == pytest.approx(CX, abs=1e-6) and v[0] == pytest.approx(CY, abs=1e-6)


def test_body_yaw_rotates_boresight(rr, tmp_path):
    # yaw 90 do: mui huong dong; muc tieu o phia dong -> tam anh
    _, u, v, _ = pixels(rr, tmp_path, [truth_row(0.0, n=0.0, e=15.0, yaw=math.pi / 2)], level_gimbal(90.0), GIMBAL_ON)
    assert u[0] == pytest.approx(CX, abs=1e-6) and v[0] == pytest.approx(CY, abs=1e-6)


def test_fx_taken_from_cfg_camera(rr, tmp_path):
    cfg = {"gimbal": {"enabled": True}, "camera": {"fx": 1000.0}}
    row = truth_row(0.0, n=15.0, e=15.0 * math.tan(math.radians(10.0)))
    _, u, _, _ = pixels(rr, tmp_path, [row], level_gimbal(90.0), cfg)
    assert u[0] == pytest.approx(CX + 1000.0 * math.tan(math.radians(10.0)), abs=1e-6)


# ---------------------------------------------------------------- target_pixels: noi suy theo thoi gian
def test_delta_interpolated_linearly_by_time_between_gimbal_rows(rr, tmp_path):
    # gimbal 3 dong cach 0.5 s: delta 90, 80, 70 (t=0, 0.5, 1.0). Goc nang truc quang = 90 - delta.
    g = [(0.0, 90.0, 0), (0.5, 80.0, 0), (1.0, 70.0, 0)]
    rows = []
    for t, el in [(0.0, 0.0), (0.25, 5.0), (0.5, 10.0), (0.75, 15.0), (1.0, 20.0)]:
        n, up = ahead_at_elev(el)
        rows.append(truth_row(t, n=n, up=up))
    _, u, v, ok = pixels(rr, tmp_path, rows, g, GIMBAL_ON)
    assert np.allclose(u, CX, atol=1e-6)
    assert np.allclose(v, CY, atol=1e-6)
    assert ok.all()


def test_delta_interpolation_is_by_time_not_by_row_index(rr, tmp_path):
    # gimbal 0.5 s/dong: delta 90 toi t=10 roi giam 4 do/s (t=15 -> 70); truth chi 2 mau (t=0, 15), khong tuong ung chi so dong
    g = [(0.5 * i, 90.0 if 0.5 * i <= 10.0 else 90.0 - 4.0 * (0.5 * i - 10.0), 0) for i in range(41)]
    n, up = ahead_at_elev(20.0)
    rows = [truth_row(0.0, n=15.0), truth_row(15.0, n=n, up=up)]
    _, u, v, ok = pixels(rr, tmp_path, rows, g, GIMBAL_ON)
    assert np.allclose(u, CX, atol=1e-6) and np.allclose(v, CY, atol=1e-6)
    assert ok.all()


# ---------------------------------------------------------------- khoang trong / ngoai dai thoi gian cua gimbal.csv
def test_samples_outside_gimbal_time_range_are_unmeasurable_not_clamped(rr, tmp_path):
    g = [(0.0, 90.0, 0), (0.5, 90.0, 0), (1.0, 90.0, 0)]
    rows = [truth_row(t) for t in (-1.0, 0.5, 2.0)]       # truoc dong dau, trong dai, sau dong cuoi
    _, u, v, ok = pixels(rr, tmp_path, rows, g, GIMBAL_ON)
    assert list(ok) == [False, True, False]
    assert math.isnan(u[0]) and math.isnan(v[0]) and math.isnan(u[2]) and math.isnan(v[2])
    assert u[1] == pytest.approx(CX, abs=1e-6)


def test_sample_in_gimbal_gap_over_half_second_is_unmeasurable(rr, tmp_path):
    g = [(0.0, 90.0, 0), (0.5, 90.0, 0), (1.0, 90.0, 0), (2.0, 90.0, 0), (2.5, 90.0, 0)]     # khoang trong 1.0 -> 2.0
    rows = [truth_row(t) for t in (0.25, 1.0, 1.5, 2.0, 2.25)]
    _, u, v, ok = pixels(rr, tmp_path, rows, g, GIMBAL_ON)
    # t=1.0 va t=2.0 trung dung thoi diem mot dong -> do duoc (nhu bo cham); t=1.5 roi vao khoang trong
    assert list(ok) == [True, True, False, True, True]
    assert math.isnan(u[2]) and math.isnan(v[2])


@pytest.mark.parametrize("gap,covered", [(0.5, True), (0.75, False)])
def test_gap_threshold_is_half_second(rr, tmp_path, gap, covered):
    g = [(0.0, 90.0, 0), (gap, 90.0, 0)]
    _, u, _, ok = pixels(rr, tmp_path, [truth_row(gap / 2.0)], g, GIMBAL_ON)
    assert bool(ok[0]) is covered


def test_gimbal_gaps_lists_unmeasurable_intervals(rr, tmp_path):
    g = [(0.0, 90.0, 0), (0.5, 90.0, 0), (1.0, 90.0, 0), (2.0, 90.0, 0), (2.5, 90.0, 0)]
    d = write_run(tmp_path, "r", [truth_row(t) for t in (0.0, 1.0, 2.5)], gimbal=g, events={}, cfg=GIMBAL_ON)
    assert rr.gimbal_gaps(rr.load_run(d)) == [(1.0, 2.0)]


def test_gimbal_gaps_include_truth_outside_gimbal_range(rr, tmp_path):
    g = [(0.0, 90.0, 0), (0.5, 90.0, 0), (1.0, 90.0, 0)]
    d = write_run(tmp_path, "r", [truth_row(t) for t in (-1.0, 0.5, 2.0)], gimbal=g, events={}, cfg=GIMBAL_ON)
    assert rr.gimbal_gaps(rr.load_run(d)) == [(-1.0, 0.0), (1.0, 2.0)]


def test_gimbal_gaps_empty_when_fully_covered(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(t) for t in (0.0, 1.0)], gimbal=level_gimbal(90.0, 2.0),
                  events={}, cfg=GIMBAL_ON)
    assert rr.gimbal_gaps(rr.load_run(d)) == []


def test_gimbal_gaps_empty_for_fixed_camera(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0), truth_row(100.0)], events={})
    assert rr.gimbal_gaps(rr.load_run(d)) == []
    d2 = write_run(tmp_path, "r2", [truth_row(0.0), truth_row(100.0)], gimbal=level_gimbal(90.0, 1.0), events={}, cfg={})
    assert rr.gimbal_gaps(rr.load_run(d2)) == []      # cfg khong bat gimbal -> camera co dinh


# ---------------------------------------------------------------- roll khac 0
def test_roll_90_degrees_turns_image_right_into_down(rr, tmp_path):
    # roll +90 do (canh phai xuong): trong anh "phai" = xuong (NED), "xuong anh" = tay (-E)
    a = 15.0 * math.tan(math.radians(10.0))
    b = 15.0 * math.tan(math.radians(5.0))
    rows = [truth_row(0.0, n=15.0, up=-a, roll=math.pi / 2),      # duoi may bay a met -> ben phai anh
            truth_row(0.5, n=15.0, e=b, roll=math.pi / 2),        # phia dong -> len tren anh (v nho)
            truth_row(1.0, n=15.0, up=a, roll=math.pi / 2)]       # tren may bay -> ben trai anh
    _, u, v, ok = pixels(rr, tmp_path, rows, level_gimbal(90.0), GIMBAL_ON)
    assert u[0] == pytest.approx(CX + FX * math.tan(math.radians(10.0)), abs=1e-6) and v[0] == pytest.approx(CY, abs=1e-6)
    assert u[1] == pytest.approx(CX, abs=1e-6) and v[1] == pytest.approx(CY - FX * math.tan(math.radians(5.0)), abs=1e-6)
    assert u[2] == pytest.approx(CX - FX * math.tan(math.radians(10.0)), abs=1e-6)
    assert ok.all()


def test_roll_does_not_change_boresight_target_stays_centered(rr, tmp_path):
    # muc tieu ngay tren truc quang (truc mui, delta 90) van o tam anh du roll bao nhieu
    rows = [truth_row(0.0, n=15.0, roll=0.7), truth_row(1.0, n=15.0, roll=-1.2)]
    _, u, v, _ = pixels(rr, tmp_path, rows, level_gimbal(90.0), GIMBAL_ON)
    assert np.allclose(u, CX, atol=1e-6) and np.allclose(v, CY, atol=1e-6)


# ---------------------------------------------------------------- target_pixels: sau camera
def test_target_behind_camera_not_in_frame_pixels_nan(rr, tmp_path):
    rows = [truth_row(0.0, n=-15.0), truth_row(1.0, n=15.0)]      # hang 0 o sau luong chaser, hang 1 o truoc
    _, u, v, ok = pixels(rr, tmp_path, rows, level_gimbal(90.0), GIMBAL_ON)
    assert list(ok) == [False, True]
    assert math.isnan(u[0]) and math.isnan(v[0])
    assert math.isfinite(u[1]) and math.isfinite(v[1])


def test_target_exactly_abeam_is_not_in_frame(rr, tmp_path):
    # vuong goc voi truc quang (z = 0): khong chieu duoc
    _, u, v, ok = pixels(rr, tmp_path, [truth_row(0.0, n=0.0, e=15.0)], level_gimbal(90.0), GIMBAL_ON)
    assert not ok[0]
    assert math.isnan(u[0]) and math.isnan(v[0])


def test_boresight_pointing_up_makes_level_target_behind(rr, tmp_path):
    # delta 0: truc quang thang len (-z than); muc tieu ngang o truoc la vuong goc -> khong thay; muc tieu duoi chan cung khong
    rows = [truth_row(0.0, n=15.0, up=0.0), truth_row(1.0, n=1.0, up=-15.0), truth_row(2.0, n=1.0, up=15.0)]
    _, u, v, ok = pixels(rr, tmp_path, rows, level_gimbal(0.0), GIMBAL_ON)
    assert list(ok) == [False, False, True]


# ---------------------------------------------------------------- target_pixels: ra khung theo tung mep
# tai 100 m phia truoc, fx 1739: mep phai/trai u = 728 +- 1739*e/100 -> e = +-41.86 m; mep tren/duoi v: up = +-31.28 m
@pytest.mark.parametrize("e,up,expect_in,edge", [
    (41.0, 0.0, True, "phai trong"), (42.7, 0.0, False, "phai ngoai"),
    (-41.0, 0.0, True, "trai trong"), (-42.7, 0.0, False, "trai ngoai"),
    (0.0, -30.5, True, "duoi trong"), (0.0, -32.1, False, "duoi ngoai"),
    (0.0, 30.5, True, "tren trong"), (0.0, 32.1, False, "tren ngoai"),
])
def test_in_frame_per_edge(rr, tmp_path, e, up, expect_in, edge):
    _, u, v, ok = pixels(rr, tmp_path, [truth_row(0.0, n=100.0, e=e, up=up)], level_gimbal(90.0), GIMBAL_ON)
    assert bool(ok[0]) is expect_in, edge
    assert u[0] == pytest.approx(CX + FX * e / 100.0, abs=1e-6)          # ra khung van tra pixel huu han
    assert v[0] == pytest.approx(CY - FX * up / 100.0, abs=1e-6)


# Mep chinh xac (khong dung sai). Than ngang, yaw 0, delta 90 -> ma tran don vi, nen tia camera = (e, -up, n) chinh xac
# va u = fx*e/n + W/2 tinh duoc chinh xac trong so thuc dau phay dong: chon fx de u (hoac v) = 0, W (hoac H) dung.
@pytest.mark.parametrize("fx,e,up,axis,expect", [
    (728.0, 15.0, 0.0, "u", float(W)),         # 728*15/15 + 728 = 1456
    (728.0, -15.0, 0.0, "u", 0.0),             # -728 + 728 = 0
    (544.0, 0.0, -15.0, "v", float(H)),        # muc tieu o duoi: v = 544 + 544 = 1088
    (544.0, 0.0, 15.0, "v", 0.0),              # muc tieu o tren: v = 544 - 544 = 0
])
def test_pixel_exactly_on_frame_edge_is_in_frame(rr, tmp_path, fx, e, up, axis, expect):
    cfg = {"gimbal": {"enabled": True}, "camera": {"fx": fx}}
    _, u, v, ok = pixels(rr, tmp_path, [truth_row(0.0, n=15.0, e=e, up=up)], level_gimbal(90.0), cfg)
    assert (u if axis == "u" else v)[0] == pytest.approx(expect, abs=1e-9)
    assert ok[0]


# ---------------------------------------------------------------- target_pixels: camera co dinh (khong co gimbal.csv)
def test_no_gimbal_csv_uses_fixed_camera_tilt_from_cfg(rr, tmp_path):
    cfg = {"camera": {"tilt_up_deg": 0.0}}
    _, u, v, ok = pixels(rr, tmp_path, [truth_row(0.0, n=15.0)], None, cfg)
    assert u[0] == pytest.approx(CX, abs=1e-6) and v[0] == pytest.approx(CY, abs=1e-6) and ok[0]


def test_no_gimbal_csv_default_tilt_is_15_degrees(rr, tmp_path):
    n, up = ahead_at_elev(15.0)
    _, u, v, ok = pixels(rr, tmp_path, [truth_row(0.0, n=n, up=up)], None, {})
    assert u[0] == pytest.approx(CX, abs=1e-6) and v[0] == pytest.approx(CY, abs=1e-6) and ok[0]


def test_fixed_camera_level_target_is_below_center_by_tilt(rr, tmp_path):
    cfg = {"camera": {"tilt_up_deg": 10.0}}
    _, u, v, _ = pixels(rr, tmp_path, [truth_row(0.0, n=15.0)], None, cfg)
    assert v[0] == pytest.approx(CY + FX * math.tan(math.radians(10.0)), abs=1e-6)
    assert u[0] == pytest.approx(CX, abs=1e-6)


def test_gimbal_enabled_ignores_camera_tilt_up_deg(rr, tmp_path):
    cfg = {"gimbal": {"enabled": True}, "camera": {"tilt_up_deg": 15.0}}
    _, u, v, _ = pixels(rr, tmp_path, [truth_row(0.0, n=15.0)], level_gimbal(90.0), cfg)
    assert v[0] == pytest.approx(CY, abs=1e-6)


def test_gimbal_csv_present_but_cfg_gimbal_disabled_uses_fixed_camera_like_scorer(rr, tmp_path):
    # bo cham chi doc gimbal.csv khi app_cfg.json gimbal.enabled; neu khong thi camera co dinh tilt 15 mac dinh
    n, up = ahead_at_elev(15.0)
    _, u, v, _ = pixels(rr, tmp_path, [truth_row(0.0, n=n, up=up)], level_gimbal(60.0), {})
    assert v[0] == pytest.approx(CY, abs=1e-6)      # delta 60 trong csv bi bo qua


# ---------------------------------------------------------------- phases
EV_DIVE = {"t_go": 10.0, "t_stop_target": 70.0, "t_both_stopped": 80.0, "t_dive_cmd": 50.0, "speed": 10.0}


def scenario_rows(dive_floor=None):
    """dive_floor: neu cho (vd 1.0) thi tgt_vd giam tu 4 (t=52) xuong dive_floor tai t=56 roi giu nguyen -> khong bao
    gio < 0.5 (khong co mau t_dive_end)."""
    """t = 0..90 buoc 0.5 s. Toc do muc tieu tang 1 m/s moi s tu t=10 toi 10 m/s (0.9*10 = 9 dat o t=19.0).
    tgt_vd: 0; tu t=50 tang 2 m/s^2 toi dinh 4 tai t=52, giam 1 m/s^2: 0.5 tai t=55.5 (chua < 0.5), 0 tai t=56.
    Muc tieu dao ngang (lech E = 60*sin) o 100 m phia truoc de cat mep khung nhieu lan."""
    rows = []
    for i in range(181):
        t = 0.5 * i
        vn = min(max(t - 10.0, 0.0), 10.0)
        if 50.0 <= t <= 52.0:
            vd = 2.0 * (t - 50.0)
        elif 52.0 < t <= 56.0:
            vd = 4.0 - (t - 52.0) if dive_floor is None else 4.0 - (4.0 - dive_floor) / 4.0 * (t - 52.0)
        else:
            vd = 0.0 if (dive_floor is None or t < 56.0) else dive_floor
        rows.append(truth_row(t, n=100.0, e=60.0 * math.sin(2 * math.pi * t / 20.0), vn=vn, vd=vd))
    return rows


def scenario_gimbal():
    return [(0.5 * i, 90.0, 0) for i in range(181)]


def scenario_run(tmp_path, name="r", events=None, gimbal=True, result=None, dive_floor=None):
    return write_run(tmp_path, name, scenario_rows(dive_floor), gimbal=scenario_gimbal() if gimbal else None,
                     events=EV_DIVE if events is None else events, cfg=GIMBAL_ON if gimbal else {}, result=result)


def test_phases_with_dive_use_scorer_boundaries(rr, tmp_path):
    ph = rr.phases(rr.load_run(scenario_run(tmp_path)))
    assert list(ph) == ["tang_toc", "bam_on_dinh", "cam_xuong", "bay_bang", "giam_toc_cuoi"]
    assert ph["tang_toc"] == (10.0, 19.0)
    assert ph["bam_on_dinh"] == (19.0, 50.0)
    assert ph["cam_xuong"] == (50.0, 61.0)          # t_dive_end = 56.0 (tgt_vd < 0.5 nghiem ngat) + 5 s
    assert ph["bay_bang"] == (61.0, 70.0)
    assert ph["giam_toc_cuoi"] == (70.0, 80.0)


def test_phases_dive_after_parameter_extends_dive_phase(rr, tmp_path):
    ph = rr.phases(rr.load_run(scenario_run(tmp_path)), dive_after=2.0)
    assert ph["cam_xuong"] == (50.0, 58.0)
    assert ph["bay_bang"] == (58.0, 70.0)


def test_phases_dive_cut_is_capped_by_target_stop(rr, tmp_path):
    ev = dict(EV_DIVE, t_stop_target=57.0)
    ph = rr.phases(rr.load_run(scenario_run(tmp_path, events=ev)))
    assert ph["cam_xuong"] == (50.0, 57.0)
    assert ph["bay_bang"] == (57.0, 57.0)


def test_phases_without_dive_has_three_phases(rr, tmp_path):
    ev = {k: v for k, v in EV_DIVE.items() if k != "t_dive_cmd"}
    ph = rr.phases(rr.load_run(scenario_run(tmp_path, events=ev)))
    assert ph == {"tang_toc": (10.0, 19.0), "bam_on_dinh": (19.0, 70.0), "phanh_cuoi": (70.0, 80.0)}


def test_phases_end_defaults_to_last_truth_time_without_both_stopped(rr, tmp_path):
    ev = {k: v for k, v in EV_DIVE.items() if k not in ("t_dive_cmd", "t_both_stopped")}
    ph = rr.phases(rr.load_run(scenario_run(tmp_path, events=ev)))
    assert ph["phanh_cuoi"] == (70.0, 90.0)


@pytest.mark.parametrize("missing", ["t_go", "t_stop_target"])
def test_phases_missing_marker_gives_empty_dict(rr, tmp_path, missing):
    ev = {k: v for k, v in EV_DIVE.items() if k != missing}
    assert rr.phases(rr.load_run(scenario_run(tmp_path, events=ev))) == {}


def test_phases_dive_end_never_found_cuts_at_target_stop(rr, tmp_path):
    ph = rr.phases(rr.load_run(scenario_run(tmp_path, dive_floor=1.0)))
    assert ph["cam_xuong"] == (50.0, 70.0)
    assert ph["bay_bang"] == (70.0, 70.0)


def test_phases_speed_never_reaches_90_percent_uses_target_stop(rr, tmp_path):
    ev = {k: v for k, v in EV_DIVE.items() if k != "t_dive_cmd"}
    ev["speed"] = 20.0                      # muc tieu chi dat 10 m/s < 18
    ph = rr.phases(rr.load_run(scenario_run(tmp_path, events=ev)))
    assert ph == {"tang_toc": (10.0, 70.0), "bam_on_dinh": (70.0, 70.0), "phanh_cuoi": (70.0, 80.0)}


def test_phases_events_without_speed_use_target_stop_for_t90(rr, tmp_path):
    ev = {k: v for k, v in EV_DIVE.items() if k not in ("t_dive_cmd", "speed")}
    ph = rr.phases(rr.load_run(scenario_run(tmp_path, events=ev)))
    assert ph["tang_toc"] == (10.0, 70.0)


def test_phases_do_not_need_gimbal_csv(rr, tmp_path):
    ph = rr.phases(rr.load_run(scenario_run(tmp_path, gimbal=False)))
    assert ph["cam_xuong"] == (50.0, 61.0)


# ---------------------------------------------------------------- saturation_spans
def sat_run(rr, tmp_path, sats):
    g = [(0.5 * i, 90.0, s) for i, s in enumerate(sats)]
    return rr.load_run(write_run(tmp_path, "r", [truth_row(0.0)], gimbal=g, events={}))


def test_saturation_single_contiguous_span(rr, tmp_path):
    run = sat_run(rr, tmp_path, [0, 1, 1, 1, 0, 0])
    assert rr.saturation_spans(run) == [(0.5, 2.0)]


def test_saturation_broken_spans_are_separate(rr, tmp_path):
    run = sat_run(rr, tmp_path, [0, 1, 1, 0, 0, 1, 0, 0])
    assert rr.saturation_spans(run) == [(0.5, 1.5), (2.5, 3.0)]


def test_saturation_none(rr, tmp_path):
    assert rr.saturation_spans(sat_run(rr, tmp_path, [0, 0, 0, 0])) == []


def test_saturation_span_running_to_end_of_file_closes_at_last_row(rr, tmp_path):
    run = sat_run(rr, tmp_path, [0, 0, 1, 1])
    assert rr.saturation_spans(run) == [(1.0, 1.5)]


def test_saturation_whole_file_saturated(rr, tmp_path):
    assert rr.saturation_spans(sat_run(rr, tmp_path, [1, 1, 1])) == [(0.0, 1.0)]


def test_saturation_empty_without_gimbal_csv(rr, tmp_path):
    run = rr.load_run(write_run(tmp_path, "r", [truth_row(0.0)], events={}))
    assert rr.saturation_spans(run) == []


# ---------------------------------------------------------------- parse_result
RESULT_PASS = """scenario=none speed=10  truth rows=12522  duration=250.4 s
[PASS] co events.json: events.json co
khoang trong truth TOAN chuyen (tham khao, khong chan): max 0.032 s
[PASS] khoang trong truth toi da <= 0.2 s (trong cua so do): max gap trong cua so = 0.027 s
[tham khao] d3 max doan bay deu truoc lenh cam (t_ws..lenh cam): 17.97 m (doi chieu nguong 40 m)
[PASS] sai so TB < 3 m: 1.13 m
KET QUA: PASS
"""

RESULT_FAIL = """scenario=none speed=10  truth rows=100  duration=9.0 s
[PASS] co events.json: events.json co
[FAIL] muc tieu ra khoi khung trong pha cam <= 2.0 s: 3.50 s (2 lan, lien tuc dai nhat 2.10 s)
[PASS] khong bao gio < 6 m (toan chuyen bay): min = 12.59 m
KET QUA: FAIL
"""


def test_parse_result_pass_run(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)], result=RESULT_PASS)
    verdict, crit = rr.parse_result(d)
    assert verdict == "PASS"
    assert crit == [
        ("co events.json", "PASS", "events.json co"),
        ("khoang trong truth toi da <= 0.2 s (trong cua so do)", "PASS", "max gap trong cua so = 0.027 s"),
        ("sai so TB < 3 m", "PASS", "1.13 m"),
    ]


def test_parse_result_fail_run_keeps_failing_criterion_and_order(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)], result=RESULT_FAIL)
    verdict, crit = rr.parse_result(d)
    assert verdict == "FAIL"
    assert [c[1] for c in crit] == ["PASS", "FAIL", "PASS"]
    assert crit[1] == ("muc tieu ra khoi khung trong pha cam <= 2.0 s", "FAIL",
                       "3.50 s (2 lan, lien tuc dai nhat 2.10 s)")


def test_parse_result_splits_at_first_colon_space_only(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)], result="[FAIL] ten: chi tiet: them: nua\nKET QUA: FAIL\n")
    _, crit = rr.parse_result(d)
    assert crit == [("ten", "FAIL", "chi tiet: them: nua")]


def test_parse_result_verdict_with_trailing_text(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)], result="KET QUA: FAIL (truth.csv gan nhu rong)\n")
    assert rr.parse_result(d) == ("FAIL", [])


def test_parse_result_missing_file_gives_none_verdict_no_error(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)])
    assert rr.parse_result(d) == (None, [])


def test_parse_result_without_verdict_line_gives_none(rr, tmp_path):
    d = write_run(tmp_path, "r", [truth_row(0.0)], result="[PASS] a: b\n")
    verdict, crit = rr.parse_result(d)
    assert verdict is None
    assert crit == [("a", "PASS", "b")]


# ---------------------------------------------------------------- tuong thich voi bo cham
def test_out_of_frame_time_matches_analyze_closed_loop(rr, tmp_path):
    """Cung kich ban (muc tieu dao ngang qua mep khung): tong thoi gian/so lan ra khung va thoi gian ra khung theo
    tung pha phai bang so cua analyze_closed_loop.b4_metrics (tinh lai tu in_frame cua cong cu)."""
    from simtools import analyze_closed_loop as acl
    d = scenario_run(tmp_path)
    run = rr.load_run(d)
    t, _, _, ok = rr.target_pixels(run)
    a = SimpleNamespace(out=d, speed=10.0, rng=15.0, dive_after=5.0, window=120.0)
    res = {}
    acl.b4_metrics(a, acl.read_csv(os.path.join(d, "truth.csv")), [], dict(EV_DIVE), "none", res)
    assert res["out_total_s"] > 0 and res["out_total_n"] > 0      # kich ban thuc su co ra khung (khong pass rong)

    def out_stats(t0, t1):
        m = (t >= t0) & (t <= t1)
        oo = ~ok[m]
        dts = np.diff(t[m], append=t[m][-1])
        return int(np.sum(oo[1:] & ~oo[:-1])) + int(oo[0]), float(np.sum(dts[oo]))

    n_tot, s_tot = out_stats(EV_DIVE["t_go"], EV_DIVE["t_both_stopped"])
    assert n_tot == res["out_total_n"]
    assert s_tot == pytest.approx(res["out_total_s"], abs=1e-9)
    for name, (t0, t1) in rr.phases(run).items():
        n_ph, s_ph = out_stats(t0, t1)
        assert t1 - t0 == pytest.approx(res[name]["dur"], abs=1e-9), name
        assert n_ph == res[name]["out_n"], name
        assert s_ph == pytest.approx(res[name]["out_s"], abs=1e-9), name


# ---------------------------------------------------------------- khoi cho lop (b)
def test_render_run_writes_png(rr, tmp_path):
    d = scenario_run(tmp_path, result=RESULT_PASS)
    out = os.path.join(str(tmp_path), "o", "run.png")
    os.makedirs(os.path.dirname(out))
    rr.render_run(d, out)
    assert os.path.getsize(out) > 0
    with open(out, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_render_run_without_gimbal_csv_still_writes_png(rr, tmp_path):
    d = scenario_run(tmp_path, gimbal=False, result=RESULT_PASS)
    out = os.path.join(str(tmp_path), "fixed.png")
    rr.render_run(d, out)
    assert os.path.getsize(out) > 0


RESULT_FAIL_ONLY = "[FAIL] muc tieu ra khoi khung: 3.50 s\nKET QUA: FAIL\n"


def batch_html(rr, tmp_path, dirs, name="batch.html"):
    out = os.path.join(str(tmp_path), name)
    rr.render_batch(dirs, out)
    assert os.path.getsize(out) > 0
    return open(out, encoding="utf-8").read()


def test_render_batch_html_has_run_names_and_both_verdicts(rr, tmp_path):
    d1 = scenario_run(tmp_path, name="20260101_000001_a", result=RESULT_PASS)
    d2 = scenario_run(tmp_path, name="20260101_000002_b", result=RESULT_FAIL_ONLY)
    html = batch_html(rr, tmp_path, [d1, d2])
    assert "20260101_000001_a" in html and "20260101_000002_b" in html
    assert "PASS" in html and "FAIL" in html


def test_render_batch_of_passing_runs_never_says_fail(rr, tmp_path):
    d1 = scenario_run(tmp_path, name="20260101_000001_a", result=RESULT_PASS)
    d2 = scenario_run(tmp_path, name="20260101_000002_b", result=RESULT_PASS)
    html = batch_html(rr, tmp_path, [d1, d2])
    assert "PASS" in html
    assert "FAIL" not in html


def test_render_batch_of_failing_runs_never_says_pass(rr, tmp_path):
    d1 = scenario_run(tmp_path, name="20260101_000001_a", result=RESULT_FAIL_ONLY)
    html = batch_html(rr, tmp_path, [d1])
    assert "FAIL" in html
    assert "PASS" not in html


# ---------------------------------------------------------------- lan chay hong (helper bi giet): khong events.json, truth rat ngan
def broken_run(tmp_path, name="20260101_000009_broken", rows=1, gimbal=False):
    return write_run(tmp_path, name, [truth_row(0.5 * i) for i in range(rows)],
                     gimbal=[(0.0, 90.0, 0)] if gimbal else None)


def test_broken_run_has_no_phases(rr, tmp_path):
    run = rr.load_run(broken_run(tmp_path))
    assert rr.phases(run) == {}
    assert rr.parse_result(run.run_dir) == (None, [])


@pytest.mark.parametrize("rows,gimbal", [(1, False), (2, False), (1, True)])
def test_render_run_of_broken_run_still_writes_png(rr, tmp_path, rows, gimbal):
    d = broken_run(tmp_path, rows=rows, gimbal=gimbal)
    out = os.path.join(str(tmp_path), "broken.png")
    rr.render_run(d, out)
    assert os.path.getsize(out) > 0


def test_render_run_with_gimbal_gap_still_writes_png(rr, tmp_path):
    g = [(0.0, 90.0, 0), (0.5, 90.0, 1), (5.0, 90.0, 0), (5.5, 90.0, 0)]
    d = write_run(tmp_path, "gappy", [truth_row(0.5 * i) for i in range(12)], gimbal=g, events={}, cfg=GIMBAL_ON,
                  result=RESULT_PASS)
    out = os.path.join(str(tmp_path), "gappy.png")
    rr.render_run(d, out)
    assert os.path.getsize(out) > 0


def test_render_batch_with_broken_run_lists_it_without_verdict(rr, tmp_path):
    good = scenario_run(tmp_path, name="20260101_000001_good", result=RESULT_PASS)
    bad = broken_run(tmp_path)
    html = batch_html(rr, tmp_path, [good, bad])
    assert "20260101_000001_good" in html and "20260101_000009_broken" in html
    assert "FAIL" not in html      # lan hong khong co result.txt: khong duoc bia ra verdict


# ================================================================ VONG 2: loi 08 tim thay tren ma da co
import html as _html  # noqa: E402
import re  # noqa: E402
from urllib.parse import unquote  # noqa: E402

OLD_GIMBAL_CFG = {"camera": {"gimbal_enabled": True}}


def tail_rows(extra=None):
    """truth t = 0..3 buoc 0.5, muc tieu thang truoc trong khung; extra {t: kwargs} ghi de."""
    extra = extra or {}
    return [truth_row(0.5 * i, **extra.get(0.5 * i, {})) for i in range(7)]


def stats(rr, tmp_path, rows, gimbal, cfg, t0, t1, name="r"):
    d = write_run(tmp_path, name, rows, gimbal=gimbal, events={}, cfg=cfg)
    return rr.out_of_frame_stats(rr.load_run(d), t0, t1)


# ---------------------------------------------------------------- 1. mau khong do duoc khong phai "ra khung"
def test_out_stats_ignore_samples_after_last_gimbal_row(rr, tmp_path):
    # gimbal toi t=2.0; truth keo toi 3.0 (t=2.5, 3.0 khong do duoc), muc tieu luon trong khung khi do duoc
    assert stats(rr, tmp_path, tail_rows(), level_gimbal(90.0, 2.0), GIMBAL_ON, 0.0, 3.0) == (0, 0.0)


def test_out_stats_ignore_unmeasurable_gap_in_the_middle(rr, tmp_path):
    g = [(0.0, 90.0, 0), (0.5, 90.0, 0), (1.0, 90.0, 0), (2.0, 90.0, 0), (2.5, 90.0, 0), (3.0, 90.0, 0)]   # trong 1.0..2.0
    assert stats(rr, tmp_path, tail_rows(), g, GIMBAL_ON, 0.0, 3.0) == (0, 0.0)


def test_out_stats_count_real_exit_but_not_unmeasurable_tail(rr, tmp_path):
    rows = tail_rows({1.0: {"e": 60.0}})          # t=1.0 ra khung ben phai (60/15*1739 >> 728), 0.5 s toi mau ke
    assert stats(rr, tmp_path, rows, level_gimbal(90.0, 2.0), GIMBAL_ON, 0.0, 3.0) == (1, 0.5)


def test_out_stats_target_behind_camera_still_counts_as_out_of_frame(rr, tmp_path):
    # bo cham tinh mau sau camera la ra khung (ray z <= 1e-6): khong duoc loai cung voi mau khong do duoc
    rows = tail_rows({1.0: {"n": -15.0}})
    assert stats(rr, tmp_path, rows, level_gimbal(90.0, 3.0), GIMBAL_ON, 0.0, 3.0) == (1, 0.5)


def test_out_stats_fixed_camera_counts_normally(rr, tmp_path):
    rows = tail_rows({1.0: {"e": 60.0}})
    assert stats(rr, tmp_path, rows, None, {"camera": {"tilt_up_deg": 0.0}}, 0.0, 3.0) == (1, 0.5)


def test_out_stats_window_without_samples_is_none(rr, tmp_path):
    assert stats(rr, tmp_path, tail_rows(), None, {"camera": {"tilt_up_deg": 0.0}}, 10.0, 20.0) is None


# ---------------------------------------------------------------- 2. cau hinh bat khop ma khong dung duoc -> khong in so sai
def corrupt_gimbal_csv(d, body):
    with open(os.path.join(d, "gimbal.csv"), "w", newline="") as f:
        f.write(body)


def assert_all_unmeasurable(rr, run):
    t, u, v, ok = rr.target_pixels(run)
    assert len(t) == len(run.truth["t"])
    assert np.all(np.isnan(u)) and np.all(np.isnan(v))
    assert not ok.any()


def test_old_model_gimbal_flag_is_unsupported(rr, tmp_path):
    d = write_run(tmp_path, "r", tail_rows(), events={}, cfg=OLD_GIMBAL_CFG)
    run = rr.load_run(d)
    assert isinstance(run.unsupported, str) and run.unsupported
    assert_all_unmeasurable(rr, run)


def test_old_model_gimbal_flag_with_gimbal_csv_still_unsupported(rr, tmp_path):
    d = write_run(tmp_path, "r", tail_rows(), gimbal=level_gimbal(90.0, 3.0), events={}, cfg=OLD_GIMBAL_CFG)
    run = rr.load_run(d)
    assert run.unsupported
    assert_all_unmeasurable(rr, run)


def test_gimbal_enabled_but_gimbal_csv_missing_is_unsupported(rr, tmp_path):
    run = rr.load_run(write_run(tmp_path, "r", tail_rows(), events={}, cfg=GIMBAL_ON))
    assert isinstance(run.unsupported, str) and run.unsupported
    assert_all_unmeasurable(rr, run)


@pytest.mark.parametrize("body", [
    "t,mode\n0.0,track\n0.5,track\n",                                   # thieu cot delta_act_deg
    "t,delta_act_deg,sat\n0.0,nan,0\n0.5,90.0,0\n",                       # NaN
    "t,delta_act_deg,sat\n1.0,90.0,0\n0.5,90.0,0\n",                      # t khong tang
    "",                                                                   # rong
])
def test_gimbal_enabled_but_gimbal_csv_corrupt_is_unsupported(rr, tmp_path, body):
    d = write_run(tmp_path, "r", tail_rows(), gimbal=level_gimbal(90.0, 3.0), events={}, cfg=GIMBAL_ON)
    corrupt_gimbal_csv(d, body)
    run = rr.load_run(d)                       # khong nem loi
    assert run.unsupported
    assert_all_unmeasurable(rr, run)


def test_supported_runs_have_unsupported_none(rr, tmp_path):
    good = rr.load_run(write_run(tmp_path, "a", tail_rows(), gimbal=level_gimbal(90.0, 3.0), events={}, cfg=GIMBAL_ON))
    fixed = rr.load_run(write_run(tmp_path, "b", tail_rows(), events={}, cfg={"camera": {"tilt_up_deg": 0.0}}))
    no_cfg = rr.load_run(write_run(tmp_path, "c", tail_rows(), events={}))
    assert good.unsupported is None and fixed.unsupported is None and no_cfg.unsupported is None


def test_new_gimbal_flag_wins_over_old_flag_like_scorer(rr, tmp_path):
    cfg = {"gimbal": {"enabled": True}, "camera": {"gimbal_enabled": True}}
    run = rr.load_run(write_run(tmp_path, "r", tail_rows(), gimbal=level_gimbal(90.0, 3.0), events={}, cfg=cfg))
    assert run.unsupported is None
    _, u, v, ok = rr.target_pixels(run)
    assert ok.all() and np.allclose(u, CX, atol=1e-6)


def test_unsupported_run_renders_png_and_html_states_the_reason(rr, tmp_path):
    d = write_run(tmp_path, "20260101_000004_old", tail_rows(), events={}, cfg=OLD_GIMBAL_CFG, result=RESULT_PASS)
    rr.render_run(d, os.path.join(str(tmp_path), "old.png"))
    assert os.path.getsize(os.path.join(str(tmp_path), "old.png")) > 0
    html = batch_html(rr, tmp_path, [d], "old.html")
    assert _html.escape(rr.load_run(d).unsupported) in html


# ---------------------------------------------------------------- 3. render_batch bao ve tung lan
def bad_run_missing_column(tmp_path, name="20260101_000005_nocol"):
    d = write_run(tmp_path, name, tail_rows(), gimbal=level_gimbal(90.0, 3.0), events={}, cfg=GIMBAL_ON, result=RESULT_PASS)
    p = os.path.join(d, "truth.csv")
    with open(p, newline="") as f:
        rows = list(csv.reader(f))
    k = rows[0].index("tgt_n")
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows([r[:k] + r[k + 1:] for r in rows])
    return d


def bad_run_null_range(tmp_path, name="20260101_000006_nullrange"):
    cfg = {"gimbal": {"enabled": True}, "guidance": {"range_set_m": None}}
    return write_run(tmp_path, name, tail_rows(), gimbal=level_gimbal(90.0, 3.0), events={}, cfg=cfg, result=RESULT_PASS)


def html_rows(html):
    return re.findall(r"<tr.*?</tr>", html, re.S)


def img_files(html, out_dir):
    return [os.path.join(out_dir, unquote(_html.unescape(s))) for s in re.findall(r'<img[^>]*\ssrc="([^"]*)"', html)]


@pytest.mark.parametrize("make_bad", [bad_run_missing_column, bad_run_null_range])
def test_render_batch_survives_one_broken_run(rr, tmp_path, make_bad):
    good = scenario_run(tmp_path, name="20260101_000001_good", result=RESULT_PASS)
    bad = make_bad(tmp_path)
    out = os.path.join(str(tmp_path), "batch.html")
    rr.render_batch([good, bad], out)
    assert os.path.exists(out), "HTML khong duoc ghi vi mot lan chay hong"
    html = open(out, encoding="utf-8").read()
    rows = html_rows(html)
    good_rows = [r for r in rows if "20260101_000001_good" in r]
    bad_rows = [r for r in rows if os.path.basename(bad) in r]
    assert len(good_rows) == 1 and len(bad_rows) == 1
    assert "lỗi dựng hình" in bad_rows[0]
    assert "lỗi dựng hình" not in good_rows[0]
    assert any(os.path.basename(p).startswith("20260101_000001_good") and os.path.getsize(p) > 0
               for p in img_files(html, str(tmp_path)))


def test_render_batch_all_good_has_no_build_error_note(rr, tmp_path):
    good = scenario_run(tmp_path, name="20260101_000001_good", result=RESULT_PASS)
    assert "lỗi dựng hình" not in batch_html(rr, tmp_path, [good])


# ---------------------------------------------------------------- 4. gioi han khop hieu luc
def limits(rr, tmp_path, deltas, sats, cfg_gimbal=None, name="r"):
    g = [(0.5 * i, dd, s) for i, (dd, s) in enumerate(zip(deltas, sats))]
    cfg = {"gimbal": dict({"enabled": True}, **(cfg_gimbal or {}))}
    run = rr.load_run(write_run(tmp_path, name, [truth_row(0.0)], gimbal=g, events={}, cfg=cfg))
    return rr.effective_gimbal_limits(run)


def test_limits_default_without_cfg_and_without_saturation(rr, tmp_path):
    assert limits(rr, tmp_path, [60, 70, 80], [0, 0, 0]) == pytest.approx((10.0, 110.0))


def test_limits_inferred_from_upper_saturated_samples(rr, tmp_path):
    # lan cu chay tran 90 do: cfg khong ghi gioi han, gimbal.csv max = 90 va co sat
    assert limits(rr, tmp_path, [60, 70, 80, 85, 90, 90, 90, 75], [0, 0, 0, 0, 1, 1, 1, 0]) == pytest.approx((10.0, 90.0))


def test_limits_inferred_from_both_sides(rr, tmp_path):
    d = [30, 30, 50, 60, 70, 80, 95, 95]
    s = [1, 1, 0, 0, 0, 0, 1, 1]
    assert limits(rr, tmp_path, d, s) == pytest.approx((30.0, 95.0))


def test_limits_inferred_only_lower_bound_keeps_default_upper(rr, tmp_path):
    assert limits(rr, tmp_path, [20, 20, 50, 60, 70, 80], [1, 1, 0, 0, 0, 0]) == pytest.approx((20.0, 110.0))


def test_limits_cfg_explicit_wins_over_inference(rr, tmp_path):
    got = limits(rr, tmp_path, [60, 80, 90, 90], [0, 0, 1, 1], {"delta_min_deg": 20.0, "delta_max_deg": 100.0})
    assert got == pytest.approx((20.0, 100.0))


def test_limits_each_bound_resolved_separately(rr, tmp_path):
    got = limits(rr, tmp_path, [60, 70, 80, 85, 90, 90], [0, 0, 0, 0, 1, 1], {"delta_min_deg": 20.0})
    assert got == pytest.approx((20.0, 90.0))


def test_limits_fixed_camera_gives_defaults(rr, tmp_path):
    run = rr.load_run(write_run(tmp_path, "r", [truth_row(0.0)], events={}))
    assert rr.effective_gimbal_limits(run) == pytest.approx((10.0, 110.0))


# ---------------------------------------------------------------- 7. URL anh duoc ma hoa
def test_html_img_src_is_url_encoded_for_odd_run_names(rr, tmp_path):
    name = "20260101_000007_a#b c%d"
    d = scenario_run(tmp_path, name=name, result=RESULT_PASS)
    out_dir = os.path.join(str(tmp_path), "site")
    os.makedirs(out_dir)
    out = os.path.join(out_dir, "batch.html")
    rr.render_batch([d], out)
    html = open(out, encoding="utf-8").read()
    srcs = re.findall(r'<img[^>]*\ssrc="([^"]*)"', html)
    assert len(srcs) == 1
    raw = _html.unescape(srcs[0])
    assert "#" not in raw and " " not in raw and "?" not in raw
    path = os.path.join(out_dir, unquote(raw))
    assert os.path.getsize(path) > 0