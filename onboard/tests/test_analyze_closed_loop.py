"""Bo cham vong kin (simtools/analyze_closed_loop.py) tren du lieu truth.csv / app_log.csv TONG HOP: ca cam xuong dat,
qua gan, vot xa, ra khoi khung, dong thieu gia tri, san do cao; va ca phanh cuoi cua kich ban cu (chi in, khong cham)."""
import csv
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simtools import analyze_closed_loop as acl  # noqa: E402

T0, T_GO, T_WS, WINDOW = 1000.0, 1000.0, 1005.0, 20.0
T_DIVE, T_STOP, T_BOTH, T_END = 1035.0, 1050.0, 1058.0, 1062.0
RATE = 20.0
SPEED, DIVE_DEG, DROP, ALT0, DECEL = 10.0, 25.0, 40.0, 70.0, 1.5
ELEV = math.radians(4.0)            # goc nang muc tieu tu chaser; camera nghieng len 15 do
COLS = ["t", "tgt_n", "tgt_e", "tgt_alt", "tgt_vn", "tgt_ve", "tgt_vd", "ch_n", "ch_e", "ch_alt", "ch_vn", "ch_ve", "ch_vd",
        "ch_roll", "ch_pitch", "ch_yaw", "d3", "dh", "ch_armed", "ch_mode"]


def tri(t, a, b, c):
    """Xung tam giac 0..1..0 qua a,b,c."""
    if t <= a or t >= c:
        return 0.0
    return (t - a) / (b - a) if t < b else (c - t) / (c - b)


def make_run(tmp, d_fn=lambda t: 25.0, pitch_fn=None, nan_rows=0, app_rc=0, dive=True):
    """Ghi thu muc ket qua tong hop. d_fn(t) = d3 chaser-muc tieu (chaser o phia sau, thap hon muc tieu goc ELEV)."""
    tilt = math.radians(15.0)
    rows, prev = [], None
    n_rows = int((T_END - T0) * RATE)
    # quy dao muc tieu tich phan tang dan
    n, alt, dt = 0.0, ALT0, 1.0 / RATE
    vd_dive = SPEED * math.sin(math.radians(DIVE_DEG))
    t_dive_len = DROP / vd_dive
    for i in range(n_rows + 1):
        t = T0 + i * dt
        vn, vd = SPEED, 0.0
        if dive and T_DIVE <= t < T_DIVE + t_dive_len:
            vn, vd = SPEED * math.cos(math.radians(DIVE_DEG)), vd_dive
        elif t >= T_STOP:
            vn = max(0.0, SPEED - DECEL * (t - T_STOP))
        if t >= T_DIVE + t_dive_len and dive:
            vd = 0.0
        d = d_fn(t)
        cn, calt = n - d * math.cos(ELEV), alt - d * math.sin(ELEV)
        pitch = ELEV - tilt if pitch_fn is None else pitch_fn(t)
        rows.append([t, n, 0.0, alt, vn, 0.0, vd, cn, 0.0, calt, 0.0, 0.0, 0.0, 0.0, pitch, 0.0,
                     d, d * math.cos(ELEV), 1, 4])
        n += vn * dt
        alt -= vd * dt
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, "truth.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for k, r in enumerate(rows):
            out = ["%.4f" % r[0]] + ["%.4f" % x for x in r[1:18]] + [r[18], r[19]]
            if nan_rows and k in (700, 701, 702)[:nan_rows]:
                out[3], out[16] = "", ""        # tgt_alt, d3 trong -> NaN
            w.writerow(out)
    with open(os.path.join(tmp, "app_log.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "loop_dt", "trk_status", "range", "range_valid", "sent", "mode", "state", "rtl"])
        for i in range(int((T_END - T0) * 30)):
            w.writerow(["%.4f" % (T0 + i / 30.0), "0.033", "track", "25.0", "1", "1", "GUIDED", "track", "0"])
    ev = {"scenario": "none", "speed": SPEED, "straight": True, "t_go": T_GO, "t_ws": T_WS,
          "t_stop_target": T_STOP, "t_both_stopped": T_BOTH}
    if dive:
        ev.update({"t_dive_cmd": T_DIVE, "dive_deg": DIVE_DEG, "dive_drop_m": DROP})
    json.dump(ev, open(os.path.join(tmp, "events.json"), "w"))
    open(os.path.join(tmp, "app.rc"), "w").write("%d\n" % app_rc)
    return str(tmp)


def run(tmp, capsys, *extra):
    sys.argv = ["analyze_closed_loop.py", str(tmp), "--speed", "10", "--range", "25", "--window", "%g" % WINDOW, *extra]
    rc = acl.main()
    return rc, capsys.readouterr().out


def verdict(out, label):
    line = next(ln for ln in out.splitlines() if label in ln)
    return line.split("]")[0].lstrip("[")


def test_dive_ok(tmp_path, capsys):
    rc, out = run(make_run(tmp_path), capsys)
    assert rc == 0, out
    assert "KET QUA: PASS" in out
    for lab in ("muc tieu thuc su cam xuong", "pha cam: d3 min", "trong va sau cu cam", "ra khoi khung trong pha cam",
                "do cao chaser >= san", "giam toc cuoi: d3 min", "giam toc cuoi: ra khoi khung"):
        assert verdict(out, lab) == "PASS", (lab, out)
    assert "B4 pha cam_xuong" in out and "B4 pha giam_toc_cuoi" in out


def test_dive_too_close(tmp_path, capsys):
    rc, out = run(make_run(tmp_path, d_fn=lambda t: 25.0 - 16.0 * tri(t, 1036.0, 1039.0, 1042.0)), capsys)
    assert rc == 1
    assert verdict(out, "pha cam: d3 min") == "FAIL"
    assert verdict(out, "trong va sau cu cam") == "PASS"


def test_dive_overshoot_far(tmp_path, capsys):
    rc, out = run(make_run(tmp_path, d_fn=lambda t: 25.0 + 27.0 * tri(t, 1044.0, 1046.0, 1049.0)), capsys)
    assert rc == 1
    assert verdict(out, "trong va sau cu cam") == "FAIL"
    assert verdict(out, "pha cam: d3 min") == "PASS"


def test_dive_target_out_of_frame(tmp_path, capsys):
    tilt = math.radians(15.0)
    rc, out = run(make_run(tmp_path, pitch_fn=lambda t: math.radians(60) if 1036.0 <= t <= 1040.0 else ELEV - tilt), capsys)
    assert rc == 1
    assert verdict(out, "ra khoi khung trong pha cam") == "FAIL"
    assert verdict(out, "pha cam: d3 min") == "PASS"


def test_rows_with_missing_values_are_dropped(tmp_path, capsys):
    rc, out = run(make_run(tmp_path, nan_rows=3), capsys)
    assert "bo 3 dong truth.csv thieu" in out
    assert rc == 0, out
    assert "min d3 toan chuyen bay = 25.00 m" in out or "min d3 toan chuyen bay = 24.9" in out or "min d3 toan chuyen bay = 25" in out


def test_missing_value_helper():
    rows = [{"t": "1", "d3": "5"}, {"t": "2", "d3": ""}, {"t": "", "d3": "7"}, {"t": "4", "d3": "x"}]
    good, n_bad = acl.drop_bad_rows(rows)
    assert n_bad == 3 and [r["t"] for r in good] == ["1"]
    assert min(float(r["d3"]) for r in good) == 5.0


def test_altitude_floor_is_scored(tmp_path, capsys):
    rc, out = run(make_run(tmp_path), capsys, "--alt-floor", "50")
    assert rc == 1
    assert verdict(out, "do cao chaser >= san") == "FAIL"


def test_dive_not_executed_fails(tmp_path, capsys):
    """Co lenh cam nhung muc tieu khong ha (SITL cat toc do xuong): phai FAIL, khong duoc im lang."""
    d = make_run(tmp_path)
    ev = json.load(open(os.path.join(d, "events.json")))
    ev["dive_drop_m"] = 400.0
    json.dump(ev, open(os.path.join(d, "events.json"), "w"))
    rc, out = run(d, capsys)
    assert rc == 1 and verdict(out, "muc tieu thuc su cam xuong") == "FAIL"


def test_old_scenario_final_brake_is_info_unless_score_final(tmp_path, capsys):
    """Kich ban cu (khong cam): pha phanh cuoi chi IN (ket qua cu giu nguyen); --score-final moi cham."""
    d = make_run(tmp_path, d_fn=lambda t: 25.0 + 27.0 * tri(t, 1051.0, 1053.0, 1056.0), dive=False)
    rc, out = run(d, capsys)
    assert rc == 0 and "tham khao" in out and "KHONG dat tham khao" in out
    rc2, out2 = run(d, capsys, "--score-final")
    assert rc2 == 1 and verdict(out2, "giam toc cuoi: d3 max") == "FAIL"
