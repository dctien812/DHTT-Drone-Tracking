"""Cot log search.csv (.office/design-search.md muc (h)). PHA DO TDD cho SEARCH_COLUMNS / SearchLogger.

Giao dien test khoa (dtrack/logger.py):
  SEARCH_COLUMNS = ["t", "ep_id", "ep_s", "phase", "run_s", "closed", "climb_m", "scan_delta_deg", "yaw_cmd_deg", "r_hat"]
  SearchLogger(path) la lop con cua CycleLogger (mau GimbalLogger): columns = SEARCH_COLUMNS, close(), tao thu muc cha.
  SearchLogger.log(t, ep_id, ep_s, phase, run_s, closed, climb_m, scan_delta_deg, yaw_cmd_deg, r_hat): DUNG THU TU CAT, mot dong/lan goi;
    None -> o trong; float -> "%.4f" (nhu _f cua logger.py); closed ghi 1/0 (quy uoc int(bool) cua logger.py).
Ca bao ve (PASS ngay): COLUMNS cua app_log.csv va GIMBAL_COLUMNS khong doi.
"""
import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

EXPECTED = ["t", "ep_id", "ep_s", "phase", "run_s", "closed", "climb_m", "scan_delta_deg", "yaw_cmd_deg", "r_hat"]
OLD_APP_COLUMNS = [
    "t", "wall", "loop_dt", "hb_age", "pose_age", "engage", "armed", "mode",
    "pos_n", "pos_e", "pos_d", "vel_n", "vel_e", "vel_d", "qw", "qx", "qy", "qz",
    "trk_status", "los_n", "los_e", "los_d", "rate_n", "rate_e", "rate_d",
    "range", "range_sigma", "range_rate", "range_valid", "age", "n_det",
    "cmd_vn", "cmd_ve", "cmd_vd", "cmd_yaw", "sent", "state", "reason", "rtl",
]
OLD_GIMBAL_COLUMNS = ["t", "mode", "delta_cmd_deg", "delta_act_deg", "delta_rate_dps", "elev_los_deg",
                      "elev_aim_deg", "elev_ref_deg", "sat", "theta_deg"]


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def test_search_columns_exact_order():
    from dtrack.logger import SEARCH_COLUMNS
    assert SEARCH_COLUMNS == EXPECTED


def test_search_logger_is_cycle_logger_with_search_columns():
    from dtrack.logger import CycleLogger, SEARCH_COLUMNS, SearchLogger
    assert issubclass(SearchLogger, CycleLogger)
    assert SearchLogger.columns == SEARCH_COLUMNS


def test_search_logger_writes_readable_csv_rows_in_column_order(tmp_path):
    from dtrack.logger import SearchLogger
    p = tmp_path / "sub" / "search.csv"                 # thu muc cha chua co
    lg = SearchLogger(str(p))
    lg.log(100.5, 1, 4.25, 1, 0.0, False, 0.0, 57.2958, 12.5, 18.75)
    lg.log(100.55, 1, 4.3, 2, 0.5, False, 1.5, 60.0, -3.0, None)
    lg.log(101.0, 0, None, None, None, True, 0.0, None, None, None)
    lg.close()
    header, rows = _read(p)
    assert header == EXPECTED
    assert len(rows) == 3
    r = dict(zip(header, rows[0]))
    assert float(r["t"]) == pytest.approx(100.5, abs=1e-3)
    assert int(float(r["ep_id"])) == 1
    assert float(r["ep_s"]) == pytest.approx(4.25, abs=1e-3)
    assert int(float(r["phase"])) == 1
    assert float(r["run_s"]) == pytest.approx(0.0, abs=1e-3)
    assert r["closed"] in ("0", "False")
    assert float(r["scan_delta_deg"]) == pytest.approx(57.2958, abs=1e-3)
    assert float(r["yaw_cmd_deg"]) == pytest.approx(12.5, abs=1e-3)
    assert float(r["r_hat"]) == pytest.approx(18.75, abs=1e-3)
    r1 = dict(zip(header, rows[1]))
    assert int(float(r1["phase"])) == 2 and float(r1["climb_m"]) == pytest.approx(1.5, abs=1e-3)
    assert r1["r_hat"] == ""                            # None -> o trong
    r2 = dict(zip(header, rows[2]))
    assert r2["closed"] in ("1", "True")
    assert (r2["ep_s"], r2["phase"], r2["run_s"], r2["scan_delta_deg"], r2["yaw_cmd_deg"], r2["r_hat"]) == ("",) * 6


def test_search_logger_with_no_rows_has_header_only(tmp_path):
    from dtrack.logger import SearchLogger
    p = tmp_path / "search.csv"
    SearchLogger(str(p)).close()
    header, rows = _read(p)
    assert header == EXPECTED and rows == []


# ---------------------------------------------------------------- ca bao ve
def test_app_log_columns_unchanged():
    from dtrack.logger import COLUMNS, CycleLogger
    assert COLUMNS == OLD_APP_COLUMNS
    assert CycleLogger.columns == OLD_APP_COLUMNS


def test_gimbal_columns_unchanged():
    from dtrack.logger import GIMBAL_COLUMNS, GimbalLogger
    assert GIMBAL_COLUMNS == OLD_GIMBAL_COLUMNS
    assert GimbalLogger.columns == OLD_GIMBAL_COLUMNS
