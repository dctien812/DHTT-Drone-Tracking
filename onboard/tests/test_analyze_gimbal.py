"""Buoc 6 thiet ke khop gat (.office/design-gimbal-steps-3-6.md): bo cham doc goc khop THAT tu gimbal.csv.
TEST VIET TRUOC (pha do). Doi ten bo duoi .wip khi ky su bat dau viet ma.

Giao dien cac test nay khoa (simtools/analyze_closed_loop.py):
  a) load_gimbal_csv(path) -> (t, delta_act_rad, sat): ba mang cung do dai; doc cot delta_act_deg (KHONG phai
     delta_cmd_deg) doi sang rad; sat la bool (file ghi "1"/"0" nhu quy uoc int(bool) cua dtrack/logger.py).
  b) app_cfg.json (JSON thua) co gimbal.enabled = true: Rbc = make_camera(0) (bo qua camera.tilt_up_deg),
     q_cam = camera_attitude(q_than, np.interp(T, t_gimbal, delta_act)). gimbal.csv nam cung thu muc voi truth.csv.
     np.interp theo THOI GIAN (khong theo chi so dong; gimbal.csv thuc ghi 30 Hz, truth 20 Hz), kep hai dau.
  c) gimbal.csv khong doc duoc: thieu file, thieu cot t/delta_act_deg, co NaN, t khong tang ngat, hoac > 2% mau truth
     trong [t_go, t_end] nam ngoai [t_gimbal[0], t_gimbal[-1]] -> b4_metrics nem loi -> main() in "B4 loi: ...",
     tieu chi "ra khoi khung trong pha cam" (ca cam) FAIL "khong do duoc", khong crash.
  c2) (quyet dinh vong sua 1) Khi gimbal.enabled: main() LUON cham dung MOT tieu chi co nhan chua chuoi "gimbal.csv"
     (dong "[PASS] ...gimbal.csv..." / "[FAIL] ...gimbal.csv...: khong do duoc ..."), o MOI kich ban ke ca khong cam;
     FAIL thi ma thoat 1 va "KET QUA: FAIL". gimbal.enabled tat: khong co dong tieu chi nao chua "gimbal.csv".
  d) res["gimbal"] (dong B4JSON) la dict, thong ke toan chuyen tren cac mau truth trong [t_go, t_end]:
       delta_min, delta_max, delta_med (do), rate_max (do/s), n_sat_enter (so canh sat False->True; mau dau cua
       [t_go, t_end] da sat=1 thi TINH la mot lan vao), n_sat (so mau sat),
       phases: {ten_pha: {delta_med, delta_min, delta_max (do), theta_med, theta_max (do), spd_med (m/s)}}
     theta = -pitch cua TRUTH (khong dung cot theta_deg cua gimbal.csv). Mot dong bat dau "B4 khop gat (chu dong)".
  e) Khong co gimbal.enabled: ket qua y het ma cu (so vang chup tu ma truoc buoc 6), gimbal.csv neu co bi bo qua.

Du lieu: dung make_run cua test_analyze_closed_loop (chaser sau muc tieu, goc nang LOS = +4 do, roll = yaw = 0).
Hinh hoc (roll 0): truc quang trong than (sin d, 0, -cos d); voi pitch p, goc nang truc quang = 90 - d + p (do).
Muc tieu dung tam khung khi d = 90 + p - 4 = 86 - theta (theta = -p). Vi du theta 40 -> d 46; theta 11 -> d 75.
Nua FOV doc = atan(544/1739) = 17.4 do: lech > 17.4 do theo goc nang thi ra khung.
"""
import csv
import json
import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, ".."), os.getcwd(), os.path.join(os.getcwd(), "tests"), HERE):
    sys.path.insert(0, p)

from simtools import analyze_closed_loop as acl  # noqa: E402
from test_analyze_closed_loop import RATE, T0, T_END, make_run, run, verdict  # noqa: E402

GCOLS = ["t", "mode", "delta_cmd_deg", "delta_act_deg", "delta_rate_dps", "elev_los_deg", "elev_aim_deg",
         "elev_ref_deg", "sat", "theta_deg"]
ELEV_DEG = 4.0
GIMBAL_ON = {"gimbal": {"enabled": True}}


def centered_delta(theta_deg):
    return 90.0 - theta_deg - ELEV_DEG


def pitch_of(theta_fn):
    return lambda t: -math.radians(theta_fn(t))


def write_cfg(d, raw):
    with open(os.path.join(d, "app_cfg.json"), "w") as f:
        json.dump(raw, f)


def write_gimbal(d, delta_fn, theta_fn, sat_fn=lambda t: False, cmd_fn=None, t_from=T0, t_to=T_END, times=None,
                 cols=GCOLS, edit_rows=None):
    """gimbal.csv; mac dinh cung moc thoi gian voi truth.csv (20 Hz) trong [t_from, t_to]; times: luoi rieng.
    delta_rate_dps = |delta - delta truoc|/dt. cols: bo cot (thieu cot -> bo gia tri). edit_rows(rows): lam hong du lieu."""
    if times is None:
        n = int(round((T_END - T0) * RATE))
        times = [T0 + i / RATE for i in range(n + 1)]
    rows, prev, tp = [], None, None
    for t in times:
        if not (t_from - 1e-9 <= t <= t_to + 1e-9):
            continue
        dl = delta_fn(t)
        rate = 0.0 if prev is None else abs(dl - prev) / (t - tp)
        prev, tp = dl, t
        cmd = dl if cmd_fn is None else cmd_fn(t)
        full = {"t": "%.4f" % t, "mode": "track", "delta_cmd_deg": "%.4f" % cmd, "delta_act_deg": "%.4f" % dl,
                "delta_rate_dps": "%.4f" % rate, "elev_los_deg": "%.4f" % ELEV_DEG, "elev_aim_deg": "%.4f" % ELEV_DEG,
                "elev_ref_deg": "", "sat": "1" if sat_fn(t) else "0", "theta_deg": "%.4f" % theta_fn(t)}
        rows.append([full[c] for c in cols])
    if edit_rows is not None:
        edit_rows(rows)
    with open(os.path.join(d, "gimbal.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


def gimbal_crit(out):
    """Dong tieu chi duy nhat ([PASS]/[FAIL]) co chua 'gimbal.csv'; tra (verdict, dong) hoac (None, None) neu khong co."""
    ls = [ln for ln in out.splitlines() if ln.startswith(("[PASS]", "[FAIL]")) and "gimbal.csv" in ln]
    assert len(ls) <= 1, ls
    return (ls[0][1:5], ls[0]) if ls else (None, None)


def b4json(out):
    line = next(ln for ln in out.splitlines() if ln.startswith("B4JSON "))
    return json.loads(line[len("B4JSON "):])


# ---------- a) load_gimbal_csv ----------

def test_load_gimbal_csv_reads_actual_angle_in_radians_and_sat_flags(tmp_path):
    p = tmp_path / "gimbal.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(GCOLS)
        for t, cmd, act, sat in ((1.0, 0.0, 90.0, "0"), (2.0, 0.0, 45.0, "1"), (3.0, 0.0, 10.0, "0")):
            w.writerow([t, "track", cmd, act, 0.0, 4.0, 4.0, "", sat, 11.0])
    t, d, s = acl.load_gimbal_csv(str(p))
    assert np.allclose(t, [1.0, 2.0, 3.0])
    assert np.allclose(d, [math.pi / 2, math.pi / 4, math.radians(10.0)])     # delta_act_deg, khong phai delta_cmd_deg
    assert [bool(x) for x in s] == [False, True, False]


# ---------- hanh vi (1): truth + gimbal.csv khop -> ra khung bang 0 ----------

def test_matching_gimbal_log_keeps_target_in_frame(tmp_path, capsys):
    """theta 40 do, delta 46 do: truc quang trung LOS. Camera co dinh (tilt 15 cua ma cu) lech 29 do -> ra khung ca chuyen."""
    th = lambda t: 40.0
    d = make_run(tmp_path, pitch_fn=pitch_of(th))
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: centered_delta(th(t)), th)
    rc, out = run(d, capsys)
    assert verdict(out, "ra khoi khung trong pha cam") == "PASS", out
    assert b4json(out)["out_total_n"] == 0, out
    assert gimbal_crit(out)[0] == "PASS", out
    assert rc == 0, out


def theta_ramp(t):
    """theta doc tuyen tinh 10 -> 72 do tren 1000..1062 (1 do/s); delta can = 86 - theta (76 -> 14, trong [10, 90])."""
    return 10.0 + (t - T0)


def test_gimbal_csv_at_30hz_out_of_phase_is_interpolated_by_time(tmp_path, capsys):
    """gimbal.csv 30 Hz lech pha: t_k = 999.99 + k/30 (toi > 1062), truth 20 Hz. Noi suy theo t -> sai < 0.02 do,
    out_total_n == 0. Lay theo CHI SO dong (delta[i] = dong i): dong i co t = 999.99 + i/30 trong khi truth i co
    t = 1000 + i/20, lech i/60 s -> lech goc (i/60) do; vuot 17.4 do (nua FOV doc) khi i > 1044 (t > 1052.2 < t_end 1058)
    -> ra khung. (Doc 30 -> 50 do cua ban giao viec chi cho lech toi da 20.7 s * 0.32 do/s = 6.7 do, khong ra khung,
    nen dung doc 1 do/s.)"""
    d = make_run(tmp_path, pitch_fn=pitch_of(theta_ramp))
    write_cfg(d, GIMBAL_ON)
    times = [999.99 + k / 30.0 for k in range(int(62.1 * 30) + 2)]
    write_gimbal(d, lambda t: centered_delta(theta_ramp(t)), theta_ramp, times=times)
    rc, out = run(d, capsys)
    assert b4json(out)["out_total_n"] == 0, out
    assert gimbal_crit(out)[0] == "PASS", out
    assert rc == 0, out


def test_gimbal_enabled_ignores_camera_tilt_in_cfg(tmp_path, capsys):
    """gimbal.enabled -> Rbc = make_camera(0) du app_cfg ghi camera.tilt_up_deg 22. Chon 22 de ca hai cach sai deu ra khung:
    khop + tilt 22 lech 22 do; camera co dinh tilt 22 o theta 40: truc quang -40 + 22 = -18 do, lech LOS +4 la 22 do (> 17.4)."""
    th = lambda t: 40.0
    d = make_run(tmp_path, pitch_fn=pitch_of(th))
    write_cfg(d, {"gimbal": {"enabled": True}, "camera": {"tilt_up_deg": 22.0}})
    write_gimbal(d, lambda t: centered_delta(th(t)), th)
    _, out = run(d, capsys)
    assert b4json(out)["out_total_n"] == 0, out


# ---------- hanh vi (2): delta lech 40 do -> ra khung va FAIL ----------

def test_actual_angle_off_by_40_deg_goes_out_of_frame_and_fails(tmp_path, capsys):
    """Lenh dung (46 do) nhung goc THAT lech +40 do trong 1036..1040 (81 mau = 4.05 s, pha cam): chi doan do ra khung."""
    th = lambda t: 40.0
    d = make_run(tmp_path, pitch_fn=pitch_of(th))
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: centered_delta(40.0) + (40.0 if 1036.0 <= t <= 1040.0 else 0.0), th,
                 cmd_fn=lambda t: centered_delta(40.0))
    rc, out = run(d, capsys)
    assert verdict(out, "ra khoi khung trong pha cam") == "FAIL", out
    assert verdict(out, "ra khoi khung trong pha bay bang") == "PASS", out
    assert verdict(out, "giam toc cuoi: ra khoi khung") == "PASS", out
    r = b4json(out)
    assert r["out_total_n"] == 1, out
    assert 3.9 <= r["out_total_s"] <= 4.2, out
    assert rc == 1


# ---------- hanh vi (3): thieu gimbal.csv / phu thoi gian khong du -> FAIL, khong crash ----------

def test_missing_gimbal_csv_fails_without_crash(tmp_path, capsys):
    """Tu the mac dinh (theta 11): camera co dinh cua ma cu van thay muc tieu -> ma cu PASS am tham."""
    d = make_run(tmp_path)
    write_cfg(d, GIMBAL_ON)
    rc, out = run(d, capsys)
    assert "B4 loi" in out, out
    assert verdict(out, "ra khoi khung trong pha cam") == "FAIL", out
    assert "khong do duoc" in next(ln for ln in out.splitlines() if "ra khoi khung trong pha cam" in ln)
    assert rc == 1


def _assert_gimbal_unreadable(out, rc):
    v, line = gimbal_crit(out)
    assert v == "FAIL", out
    assert "khong do duoc" in line, line
    assert "KET QUA: FAIL" in out and rc == 1, out


def test_missing_gimbal_csv_fails_in_non_dive_run(tmp_path, capsys):
    """Ca khong cam (phanh_cuoi chi in, khong cham): thieu gimbal.csv van phai FAIL qua tieu chi 'gimbal.csv'."""
    d = make_run(tmp_path, dive=False)
    write_cfg(d, GIMBAL_ON)
    rc, out = run(d, capsys)
    _assert_gimbal_unreadable(out, rc)


def test_missing_gimbal_csv_fails_gimbal_criterion_in_dive_run(tmp_path, capsys):
    d = make_run(tmp_path)
    write_cfg(d, GIMBAL_ON)
    rc, out = run(d, capsys)
    _assert_gimbal_unreadable(out, rc)


def _nan_row(rows):
    rows[500][GCOLS.index("delta_act_deg")] = "nan"


def _swap_times(rows):
    i = GCOLS.index("t")
    rows[300][i], rows[301][i] = rows[301][i], rows[300][i]


def _dup_time(rows):
    i = GCOLS.index("t")
    rows[301][i] = rows[300][i]


@pytest.mark.parametrize("dive", [False, True])
@pytest.mark.parametrize("kind", ["no_delta_act_col", "no_t_col", "nan_delta", "time_not_increasing", "time_repeated"])
def test_broken_gimbal_csv_fails_gimbal_criterion(tmp_path, capsys, kind, dive):
    th = lambda t: 11.0
    d = make_run(tmp_path, pitch_fn=pitch_of(th), dive=dive)
    write_cfg(d, GIMBAL_ON)
    kw = {"no_delta_act_col": {"cols": [c for c in GCOLS if c != "delta_act_deg"]},
          "no_t_col": {"cols": [c for c in GCOLS if c != "t"]},
          "nan_delta": {"edit_rows": _nan_row},
          "time_not_increasing": {"edit_rows": _swap_times},
          "time_repeated": {"edit_rows": _dup_time}}[kind]
    write_gimbal(d, lambda t: centered_delta(th(t)), th, **kw)
    rc, out = run(d, capsys)
    _assert_gimbal_unreadable(out, rc)
    assert "B4 loi" in out, out


@pytest.mark.parametrize("t_from,t_to,ok", [
    (1001.5, T_END, False),   # 1000.00..1001.45 = 30/1161 mau trong [t_go 1000, t_end 1058] = 2.6% > 2%
    (1001.35, T_END, False),  # 1000.00..1001.30 = 27/1161 = 2.33% > 2%
    (1001.0, T_END, True),    # 1000.00..1000.95 = 20/1161 = 1.72%
    (1000.5, T_END, True),    # 10/1161 = 0.86%
    (T0, 1058.0, True),       # het dung t_end; 1058..1062 ngoai [t_go, t_end] khong tinh
    (T0, 1056.0, False),      # 1056.05..1058.00 = 40/1161 = 3.4%
])
def test_gimbal_csv_time_coverage_over_2_percent_missing_fails(tmp_path, capsys, t_from, t_to, ok):
    """Mau ngoai khoang file dung gia tri kep hai dau cua np.interp (delta van dung 46 do vi theta khong doi)."""
    th = lambda t: 40.0
    d = make_run(tmp_path, pitch_fn=pitch_of(th))
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: centered_delta(th(t)), th, t_from=t_from, t_to=t_to)
    rc, out = run(d, capsys)
    assert verdict(out, "ra khoi khung trong pha cam") == ("PASS" if ok else "FAIL"), out
    assert ("B4 loi" in out) == (not ok), out
    assert gimbal_crit(out)[0] == ("PASS" if ok else "FAIL"), out
    assert rc == (0 if ok else 1), out


# ---------- hanh vi (4): so lan / so mau cham gioi han theo chuoi sat dung san ----------

def test_saturation_counts_match_prebuilt_sat_sequence(tmp_path, capsys):
    """sat=1 (delta 90) o ba khoi: [1010, 1011] = 21 mau, [1020, 1020.5] = 11 mau, [1030, 1030] = 1 mau; con lai 0.
    Mau dau la 0 -> n_sat_enter = so canh 0->1 = 3; n_sat = 21 + 11 + 1 = 33 (moi khoi deu trong [t_go, t_end],
    gimbal.csv trung moc truth nen dem tren dong gimbal hay tren mau truth deu ra cung so)."""
    th = lambda t: 11.0
    blocks = ((1010.0, 1011.0), (1020.0, 1020.5), (1030.0, 1030.0))
    sat = lambda t: any(a - 1e-6 <= t <= b + 1e-6 for a, b in blocks)
    d = make_run(tmp_path, pitch_fn=pitch_of(th), dive=False)
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: 90.0 if sat(t) else centered_delta(11.0), th, sat_fn=sat)
    _, out = run(d, capsys)
    g = b4json(out)["gimbal"]
    assert isinstance(g, dict), out
    assert g["n_sat_enter"] == 3, g
    assert g["n_sat"] == 33, g


def test_saturation_at_first_sample_counts_as_one_entry(tmp_path, capsys):
    """Quyet dinh vong sua 1: mau dau cua [t_go, t_end] (t = 1000) da sat=1 thi TINH la mot lan vao.
    Khoi [1000, 1002] = 41 mau, [1010, 1011] = 21 mau -> n_sat_enter = 1 + 1 = 2, n_sat = 62."""
    th = lambda t: 11.0
    blocks = ((1000.0, 1002.0), (1010.0, 1011.0))
    sat = lambda t: any(a - 1e-6 <= t <= b + 1e-6 for a, b in blocks)
    d = make_run(tmp_path, pitch_fn=pitch_of(th), dive=False)
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: 90.0 if sat(t) else centered_delta(11.0), th, sat_fn=sat)
    _, out = run(d, capsys)
    g = b4json(out)["gimbal"]
    assert isinstance(g, dict), out
    assert g["n_sat_enter"] == 2, g
    assert g["n_sat"] == 62, g


# ---------- hanh vi (5): khong co khoa gimbal -> ket qua bang cu ----------

def _old_run(tmp_path):
    """Du lieu cua test_dive_target_out_of_frame: pitch 60 do trong 1036..1040 -> ra khung o ma cu."""
    return make_run(tmp_path, pitch_fn=lambda t: math.radians(60) if 1036.0 <= t <= 1040.0 else math.radians(ELEV_DEG - 15.0))


def _stray_gimbal(d):
    """gimbal.csv lech hoan toan (delta 10 do): neu bi doc thi ket qua phai khac."""
    write_gimbal(d, lambda t: 10.0, lambda t: 11.0)


# so vang chup tu ma TRUOC buoc 6 (2026-11-18) tren _old_run; xem bao cao 07
GOLD_NONE = {"gimbal": False, "tilt": 15.0, "out_total_n": 1, "out_total_s": 4.05, "cam_xuong_out_s": 4.05}
GOLD_OLD_GM = {"gimbal": {"delta_min": -50.0, "delta_max": 11.000789666511807, "rate_max": 300.00000000000006},
               "tilt": 15.0, "out_total_n": 1, "out_total_s": 4.15, "cam_xuong_out_s": 4.15}


def _check_gold(r, gold):
    assert r["tilt"] == gold["tilt"]
    assert r["out_total_n"] == gold["out_total_n"]
    assert r["out_total_s"] == pytest.approx(gold["out_total_s"], abs=1e-6)
    assert r["cam_xuong"]["out_s"] == pytest.approx(gold["cam_xuong_out_s"], abs=1e-6)
    if isinstance(gold["gimbal"], dict):
        assert set(r["gimbal"]) == set(gold["gimbal"])
        for k, v in gold["gimbal"].items():
            assert r["gimbal"][k] == pytest.approx(v, abs=1e-6), k
    else:
        assert r["gimbal"] is gold["gimbal"]


@pytest.mark.parametrize("cfg", [None, {"gimbal": {"enabled": False}}, {"guidance": {"range_set_m": 25.0}}])
def test_without_gimbal_enabled_result_equals_old_and_ignores_gimbal_csv(tmp_path, capsys, cfg):
    d = _old_run(tmp_path)
    if cfg is not None:
        write_cfg(d, cfg)
    _stray_gimbal(d)
    rc, out = run(d, capsys)
    _check_gold(b4json(out), GOLD_NONE)
    assert verdict(out, "ra khoi khung trong pha cam") == "FAIL" and rc == 1
    assert "B4 loi" not in out and "B4 khop gat (chu dong)" not in out
    assert gimbal_crit(out) == (None, None), out


def test_old_gimbal_model_path_unchanged_and_ignores_gimbal_csv(tmp_path, capsys):
    d = _old_run(tmp_path)
    write_cfg(d, {"camera": {"gimbal_enabled": True}})
    _stray_gimbal(d)
    _, out = run(d, capsys)
    _check_gold(b4json(out), GOLD_OLD_GM)
    assert "B4 khop gat (chu dong)" not in out
    assert gimbal_crit(out) == (None, None), out


# ---------- hanh vi (6): thong ke toan chuyen va theo pha dung gia tri tay ----------

def theta6(t):
    """theta (do) theo t. Ca khong cam: pha tang_toc [1000,1000], bam_on_dinh [1000,1050], phanh_cuoi [1050,1058]."""
    if 1020.0 - 1e-6 <= t <= 1021.0 + 1e-6:
        return 20.0
    if 1055.0 - 1e-6 <= t <= 1055.5 + 1e-6:
        return 30.0
    if t > 1051.0 + 1e-6:
        return 25.0
    return 11.0


def _stats_run(tmp_path, capsys):
    d = make_run(tmp_path, pitch_fn=pitch_of(theta6), dive=False)
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: centered_delta(theta6(t)), theta6)
    rc, out = run(d, capsys)
    return out


def test_gimbal_overall_delta_stats_hand_values(tmp_path, capsys):
    """delta = 86 - theta: theta 11 -> 75, 20 -> 66, 25 -> 61, 30 -> 56.
    Mau truth 1000..1062 (1241): 75 x 1000 (t <= 1051 tru 21 mau gai 1020..1021), 66 x 21, 61 x 209, 56 x 11.
    min 56, max 75; trung vi = 75 (75 chiem > nua; gioi han [t_go, t_end] = 1161 mau cung ra 75).
    rate_max: buoc lon nhat 75 -> 61 tai 1051 -> 1051.05: 14 do / 0.05 s = 280 do/s (cot delta_rate_dps ghi cung so)."""
    out = _stats_run(tmp_path, capsys)
    g = b4json(out)["gimbal"]
    assert isinstance(g, dict), out
    assert g["delta_min"] == pytest.approx(56.0, abs=0.01)
    assert g["delta_max"] == pytest.approx(75.0, abs=0.01)
    assert g["delta_med"] == pytest.approx(75.0, abs=0.01)
    assert g["rate_max"] == pytest.approx(280.0, rel=0.01)
    assert g["n_sat_enter"] == 0 and g["n_sat"] == 0


def test_gimbal_per_phase_stats_hand_values(tmp_path, capsys):
    """bam_on_dinh [1000,1050], 1001 mau: theta 11 x 980, 20 x 21 -> theta trung vi 11, max 20;
       delta 75 x 980, 66 x 21 -> trung vi 75, min 66, max 75; toc do muc tieu 10 m/s ca pha -> trung vi 10.
    phanh_cuoi [1050,1058], 161 mau: theta 11 x 21 (1050.00..1051.00), 30 x 11 (1055.0..1055.5), 25 x 129
       -> sap xep, mau thu 81 (chi so 80) roi vao khoi 25: trung vi 25, max 30; delta trung vi 61, min 56, max 75.
       toc do vn = max(0, 10 - 1.5 (t - 1050)) giam dan, trung vi tai t = 1054: 10 - 6 = 4.0 m/s
       (neu pha lay nua mo thi 160 mau, trung vi ~4.04; dung sai 0.1)."""
    out = _stats_run(tmp_path, capsys)
    ph = b4json(out)["gimbal"]["phases"]
    b, f = ph["bam_on_dinh"], ph["phanh_cuoi"]
    assert (b["theta_med"], b["theta_max"]) == (pytest.approx(11.0, abs=0.01), pytest.approx(20.0, abs=0.01)), b
    assert (b["delta_med"], b["delta_min"], b["delta_max"]) == (
        pytest.approx(75.0, abs=0.01), pytest.approx(66.0, abs=0.01), pytest.approx(75.0, abs=0.01)), b
    assert b["spd_med"] == pytest.approx(10.0, abs=0.01), b
    assert (f["theta_med"], f["theta_max"]) == (pytest.approx(25.0, abs=0.01), pytest.approx(30.0, abs=0.01)), f
    assert (f["delta_med"], f["delta_min"], f["delta_max"]) == (
        pytest.approx(61.0, abs=0.01), pytest.approx(56.0, abs=0.01), pytest.approx(75.0, abs=0.01)), f
    assert f["spd_med"] == pytest.approx(4.0, abs=0.1), f


def test_theta_stats_come_from_truth_pitch_not_gimbal_column(tmp_path, capsys):
    """Cung du lieu _stats_run nhung cot theta_deg cua gimbal.csv co y ghi sai (-7 do moi dong).
    Ky vong y het test_gimbal_per_phase_stats_hand_values: theta lay tu pitch cua truth."""
    d = make_run(tmp_path, pitch_fn=pitch_of(theta6), dive=False)
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: centered_delta(theta6(t)), lambda t: -7.0)
    _, out = run(d, capsys)
    ph = b4json(out)["gimbal"]["phases"]
    b, f = ph["bam_on_dinh"], ph["phanh_cuoi"]
    assert (b["theta_med"], b["theta_max"]) == (pytest.approx(11.0, abs=0.01), pytest.approx(20.0, abs=0.01)), b
    assert (f["theta_med"], f["theta_max"]) == (pytest.approx(25.0, abs=0.01), pytest.approx(30.0, abs=0.01)), f


def test_overall_stats_use_only_t_go_to_t_end(tmp_path, capsys):
    """theta 11 ca chuyen; delta 75 (dung tam) toi 1058 = t_end, sau do (1058.05..1062, 80 mau ngoai cua so) ghi 20 do
    va sat=1. Tinh tren [t_go, t_end]: min = max = trung vi = 75, n_sat = n_sat_enter = 0.
    (Tinh tren ca file / ca truth thi min 20, n_sat 80.)"""
    th = lambda t: 11.0
    late = lambda t: t > 1058.0 + 1e-6
    d = make_run(tmp_path, pitch_fn=pitch_of(th), dive=False)
    write_cfg(d, GIMBAL_ON)
    write_gimbal(d, lambda t: 20.0 if late(t) else centered_delta(11.0), th, sat_fn=late)
    _, out = run(d, capsys)
    g = b4json(out)["gimbal"]
    assert isinstance(g, dict), out
    assert (g["delta_min"], g["delta_max"], g["delta_med"]) == (
        pytest.approx(75.0, abs=0.01), pytest.approx(75.0, abs=0.01), pytest.approx(75.0, abs=0.01)), g
    assert g["n_sat"] == 0 and g["n_sat_enter"] == 0, g


def test_active_gimbal_summary_line_printed(tmp_path, capsys):
    out = _stats_run(tmp_path, capsys)
    assert any(ln.startswith("B4 khop gat (chu dong)") for ln in out.splitlines()), out


# ---------- vong sua ma buoc 6, luot 1: lo GIUA file, dong cuoi cat do, thieu cot sat ----------
# Quyet dinh: mau truth trong [t_go, t_end] KHONG duoc phu khi nam ngoai [t_gimbal[0], t_gimbal[-1]] HOAC nam trong
# khoang trong giua hai dong gimbal.csv lien tiep dai > 0.5 s. Tong > 2% -> tieu chi gimbal.csv FAIL "khong do duoc",
# in "B4 loi", ma thoat 1. Lo <= 0.5 s noi suy binh thuong.
# Luoi gimbal.csv lech nua buoc so voi truth: t_k = 999.975 + k/20 (khong dong nao trung mau truth, khoi mo ho bien).
# Lo dai L giua hai dong con lai chua dung L/0.05 mau truth (0.6 s -> 12, 0.4 s -> 8, 25 s -> 500).
# Ca cam: [t_go 1000, t_end 1058] = 1161 mau truth; 2% = 23.2 mau. theta 40 / delta 46 khong doi nen noi suy qua lo
# van cho goc dung: chi phep kiem do phu quyet dinh PASS/FAIL.

HALF_GRID = [T0 - 0.025 + k / RATE for k in range(int(round((T_END - T0) * RATE)) + 2)]   # 999.975 .. 1062.025


def write_holey(d, holes=(), t_from=HALF_GRID[0], edit_rows=None, cols=GCOLS):
    """gimbal.csv theta 40 / delta 46 tren HALF_GRID, bo cac dong co start < t < start + L voi (start, L) trong holes."""
    th = lambda t: 40.0
    times = [t for t in HALF_GRID if not any(s + 1e-6 < t < s + L - 1e-6 for s, L in holes)]
    write_gimbal(d, lambda t: centered_delta(th(t)), th, times=times, t_from=t_from, edit_rows=edit_rows, cols=cols)


def _holey_run(tmp_path, capsys, dive=True, ev_set=None, **kw):
    d = make_run(tmp_path, pitch_fn=pitch_of(lambda t: 40.0), dive=dive, ev_set=ev_set)
    write_cfg(d, GIMBAL_ON)
    write_holey(d, **kw)
    return run(d, capsys)


def _assert_gimbal_ok(out, rc):
    assert gimbal_crit(out)[0] == "PASS", out
    assert "B4 loi" not in out, out
    assert rc == 0, out


@pytest.mark.parametrize("dive", [True, False])
def test_mid_file_25s_hole_fails(tmp_path, capsys, dive):
    """Lo 1010.025 -> 1035.025 (25 s) trong [t_go, t_end]: 500/1161 mau = 43% khong phu -> FAIL o ca cam va khong cam."""
    rc, out = _holey_run(tmp_path, capsys, dive=dive, holes=((1010.025, 25.0),))
    _assert_gimbal_unreadable(out, rc)
    assert "B4 loi" in out, out


def test_short_holes_0_4s_are_interpolated(tmp_path, capsys):
    """Bon lo 0.4 s (<= 0.5 s) tai 1015.025, 1025.025, 1040.025, 1045.025: noi suy, PASS.
    (Neu dem nham ca lo ngan: 4 x 8 = 32/1161 = 2.76% > 2% -> se FAIL.)"""
    holes = tuple((s, 0.4) for s in (1015.025, 1025.025, 1040.025, 1045.025))
    rc, out = _holey_run(tmp_path, capsys, holes=holes)
    _assert_gimbal_ok(out, rc)


def test_holes_plus_late_start_1_7_percent_passes(tmp_path, capsys):
    """Lo 0.6 s tai 1020.025 (12 mau) + file bat dau 1000.375 (truth 1000.00..1000.35 ngoai file = 8 mau)
    -> 20/1161 = 1.72% <= 2% -> PASS."""
    rc, out = _holey_run(tmp_path, capsys, holes=((1020.025, 0.6),), t_from=1000.375)
    _assert_gimbal_ok(out, rc)


def test_holes_plus_late_start_2_3_percent_fails(tmp_path, capsys):
    """Hai lo 0.6 s tai 1020.025, 1030.025 (2 x 12 = 24 mau) + file bat dau 1000.125 (truth 1000.00, .05, .10 = 3 mau)
    -> 27/1161 = 2.33% > 2% -> FAIL. (Chi dem hai dau file: 3 mau = 0.26% -> ma chi kiem hai dau se PASS nham.)"""
    rc, out = _holey_run(tmp_path, capsys, holes=((1020.025, 0.6), (1030.025, 0.6)), t_from=1000.125)
    _assert_gimbal_unreadable(out, rc)
    assert "B4 loi" in out, out


def test_long_hole_entirely_before_t_go_passes(tmp_path, capsys):
    """events t_go = 1010 (truth van tu 1000). Lo 999.975 -> 1009.025 (9.05 s, 181 mau truth deu < t_go): khong tinh.
    [t_go, t_end] = 1010..1058 = 961 mau, deu nam giua cac dong lien tiep cach 0.05 s -> 0% -> PASS."""
    rc, out = _holey_run(tmp_path, capsys, ev_set={"t_go": 1010.0}, holes=((999.975, 9.05),))
    _assert_gimbal_ok(out, rc)


def _truncate_last(rows):
    rows[-1] = rows[-1][:3]          # "1062.0250,track,46.0000": app bi dung khi dang ghi dong cuoi


def _truncate_middle(rows):
    rows[500] = rows[500][:3]        # dong 500 (t = 1024.975) thieu truong, giua file


def test_truncated_last_row_is_ignored(tmp_path, capsys):
    """Dong cuoi cat do -> bo dong do; cac dong con lai phu den 1061.975 > t_end 1058 -> PASS."""
    rc, out = _holey_run(tmp_path, capsys, edit_rows=_truncate_last)
    _assert_gimbal_ok(out, rc)


def test_truncated_middle_row_fails(tmp_path, capsys):
    rc, out = _holey_run(tmp_path, capsys, edit_rows=_truncate_middle)
    _assert_gimbal_unreadable(out, rc)


def test_missing_sat_column_passes_with_zero_sat(tmp_path, capsys):
    rc, out = _holey_run(tmp_path, capsys, cols=[c for c in GCOLS if c != "sat"])
    _assert_gimbal_ok(out, rc)
    g = b4json(out)["gimbal"]
    assert g["n_sat"] == 0 and g["n_sat_enter"] == 0, g
