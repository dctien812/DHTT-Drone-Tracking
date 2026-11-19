"""Noi day khoi tim lai muc tieu vao App (.office/design-search.md muc (a) "Moi chu ky", (h)). PHA DO TDD.

Giao dien test khoa:
  - cfg.search (SearchConfig) bat -> bat buoc cfg.gimbal.enabled (nhu validate()).
  - App(..., search_logger=None): tham so moi (ghi search.csv, mot dong/chu ky khi co out.search).
  - App.run: SupervisorInput(..., gimbal_delta_rad=delta_act) voi delta_act = goc khop THUC do duoc o dau chu ky
    (port.angle), KHONG phai goc lenh.
  - App.run: gimbal_ctrl.step(now, q_body, track, scan_delta_rad=out.search.scan_delta_rad); out.search None -> None.
  - main(): search.enabled -> tao search.csv (header = SEARCH_COLUMNS) canh --log, dong sau khi chay; tat -> khong tao.
  - search tat (mac dinh): khong co search.csv, scan_delta_rad luon None, app_log.csv giu cot cu.
Dung doi tuong gia cua test_app_gimbal.py (khong mang, khong SITL). Supervisor dung that; chi mot so ca thay ket qua
sup.step bang ban sao co them .search (SimpleNamespace) de tach rieng phan noi day khoi supervisor.
"""
import csv
import dataclasses
import math
import os
import sys
from types import SimpleNamespace

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, ".."), HERE):
    sys.path.insert(0, p)

import dtrack.app as app_mod  # noqa: E402
from dtrack.app import App  # noqa: E402
from dtrack.config import AppConfig, GimbalConfig  # noqa: E402
from dtrack.logger import CycleLogger  # noqa: E402
from test_app_gimbal import (EmptySource, FakeClock, FakeLink, MainLink, N_TICKS, OLD_APP_COLUMNS,  # noqa: E402
                             RecordingPort, _read_csv, _run)

SEARCH_COLUMNS = ["t", "ep_id", "ep_s", "phase", "run_s", "closed", "climb_m", "scan_delta_deg", "yaw_cmd_deg", "r_hat"]
GIMBAL_COLUMNS = ["t", "mode", "delta_cmd_deg", "delta_act_deg", "delta_rate_dps", "elev_los_deg",
                  "elev_aim_deg", "elev_ref_deg", "sat", "theta_deg"]
SCAN_RAD = 0.7


def search_cfg():
    from dtrack.config import SearchConfig          # chua co -> ImportError (ly do do)
    return AppConfig(gimbal=GimbalConfig(enabled=True), search=SearchConfig(enabled=True))


def gimbal_only_cfg():
    return AppConfig(gimbal=GimbalConfig(enabled=True))


def fake_search_info(scan):
    return SimpleNamespace(ep_id=1, ep_s=2.5, phase=1, run_s=0.0, closed=False, climb_m=0.0, scan_delta_rad=scan, r_hat=None)


def stub_search(app, scan):
    """Boc sup.step that: tra ban sao ket qua kem .search; ghi lai cac SupervisorInput."""
    orig = app.sup.step
    seen = []

    def step(inp):
        seen.append(inp)
        out = orig(inp)
        d = {f.name: getattr(out, f.name) for f in dataclasses.fields(out)}
        d.pop("search", None)
        return SimpleNamespace(**d, search=None if scan is None else fake_search_info(scan))

    app.sup.step = step
    return seen


def spy_gimbal_step(app):
    """Ghi (a, kw) moi lan gimbal_ctrl.step; goi ham that voi 3 tham so cu (khong phu thuoc chu ky moi)."""
    orig = app.gimbal_ctrl.step
    calls = []

    def step(*a, **kw):
        calls.append((a, kw))
        return orig(*a[:3])

    app.gimbal_ctrl.step = step
    return calls


def scan_arg(call):
    a, kw = call
    return kw.get("scan_delta_rad", a[3] if len(a) > 3 else None)


# ------------------------------------------------------------ (1) goc khop thuc -> SupervisorInput
def test_search_on_supervisor_input_gets_actual_gimbal_angle(monkeypatch):
    """Cong tra 60 do (goc THUC), controller lenh 90 do (init): gimbal_delta_rad phai la goc thuc 60 do."""
    clock, link = FakeClock(), FakeLink()
    app = App(search_cfg(), EmptySource(), link, clock=clock, gimbal_port=RecordingPort(math.radians(60.0)))
    seen = stub_search(app, None)
    _run(app, link, monkeypatch, clock)
    vals = [getattr(i, "gimbal_delta_rad", "THIEU truong gimbal_delta_rad") for i in seen if i.own is not None]
    assert len(vals) == N_TICKS, vals
    assert vals == [pytest.approx(math.radians(60.0), abs=1e-9)] * len(vals), vals


# ------------------------------------------------------------ (2) scan_delta_rad -> gimbal_ctrl.step
def test_search_on_scan_delta_from_supervisor_output_goes_to_gimbal_controller(monkeypatch):
    clock, link = FakeClock(), FakeLink()
    app = App(search_cfg(), EmptySource(), link, clock=clock, gimbal_port=RecordingPort(math.radians(60.0)))
    stub_search(app, SCAN_RAD)
    calls = spy_gimbal_step(app)
    _run(app, link, monkeypatch, clock)
    assert len(calls) >= 1
    assert [scan_arg(c) for c in calls] == [pytest.approx(SCAN_RAD, abs=1e-12)] * len(calls), calls


def test_search_on_without_search_info_passes_none_scan(monkeypatch):
    """out.search = None (khong co dot mat) -> scan_delta_rad None: bo dieu khien chay nhanh TRACK/COAST nhu thuong."""
    clock, link = FakeClock(), FakeLink()
    app = App(search_cfg(), EmptySource(), link, clock=clock, gimbal_port=RecordingPort(math.radians(60.0)))
    stub_search(app, None)
    calls = spy_gimbal_step(app)
    _run(app, link, monkeypatch, clock)
    assert len(calls) >= 1
    assert [scan_arg(c) for c in calls] == [None] * len(calls)


# ------------------------------------------------------------ (3) search.csv
class SpySearchLogger:
    def __init__(self):
        self.rows = []

    def log(self, *a, **kw):
        self.rows.append((a, kw))

    def close(self):
        pass


def test_search_logger_gets_one_row_per_cycle_with_scan_angle_in_degrees(monkeypatch):
    clock, link = FakeClock(), FakeLink()
    lg = SpySearchLogger()
    app = App(search_cfg(), EmptySource(), link, clock=clock, gimbal_port=RecordingPort(math.radians(60.0)),
              search_logger=lg)
    stub_search(app, SCAN_RAD)
    _run(app, link, monkeypatch, clock)
    assert len(lg.rows) == app.stats["ticks"] == N_TICKS
    for a, kw in lg.rows:
        vals = [v for v in list(a) + list(kw.values()) if isinstance(v, float)]
        assert any(v == pytest.approx(math.degrees(SCAN_RAD), abs=1e-6) for v in vals), (a, kw)


def _write_cfg(path, gimbal, search):
    import json
    raw = {"gimbal": {"enabled": gimbal}}
    if search is not None:
        raw["search"] = {"enabled": search}
        if search:
            raw["guidance"] = {"blind_floor_m": 8.0}    # bat tim lai bat buoc co san khoang cach luc mu
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f)


def _run_main(tmp_path, monkeypatch, gimbal, search):
    """main() voi link/nguon gia; stop-file co san -> 0 chu ky (nhu test_app_gimbal._run_main)."""
    cfgdir, logdir = tmp_path / "cfg", tmp_path / "logs"
    cfgdir.mkdir(), logdir.mkdir()
    _write_cfg(str(cfgdir / "c.json"), gimbal, search)
    (cfgdir / "stop").write_text("x")
    monkeypatch.setattr(app_mod, "MavlinkLink", MainLink)
    monkeypatch.setattr(app_mod, "build_source", lambda *a, **kw: EmptySource())
    rc = app_mod.main(["--config", str(cfgdir / "c.json"), "--source", "sim", "--auto-engage",
                       "--log", str(logdir / "app_log.csv"), "--stop-file", str(cfgdir / "stop")])
    assert rc == 0
    return logdir


def test_main_search_on_writes_search_csv_next_to_log(tmp_path, monkeypatch):
    logdir = _run_main(tmp_path, monkeypatch, gimbal=True, search=True)
    assert sorted(os.listdir(logdir)) == ["app_log.csv", "gimbal.csv", "search.csv"]
    header, rows = _read_csv(logdir / "search.csv")
    assert header == SEARCH_COLUMNS and rows == []


# ------------------------------------------------------------ ca bao ve: tat (mac dinh) -> hanh vi cu
def test_main_search_off_writes_no_search_csv(tmp_path, monkeypatch):
    logdir = _run_main(tmp_path, monkeypatch, gimbal=True, search=False)
    assert sorted(os.listdir(logdir)) == ["app_log.csv", "gimbal.csv"]


def test_main_without_search_key_writes_no_search_csv(tmp_path, monkeypatch):
    logdir = _run_main(tmp_path, monkeypatch, gimbal=True, search=None)
    assert sorted(os.listdir(logdir)) == ["app_log.csv", "gimbal.csv"]


def test_main_gimbal_and_search_off_writes_only_app_log(tmp_path, monkeypatch):
    logdir = _run_main(tmp_path, monkeypatch, gimbal=False, search=None)
    assert sorted(os.listdir(logdir)) == ["app_log.csv"]


def test_search_off_gimbal_controller_never_gets_scan_and_app_log_unchanged(tmp_path, monkeypatch):
    clock, link = FakeClock(), FakeLink()
    log = CycleLogger(str(tmp_path / "app_log.csv"))
    app = App(gimbal_only_cfg(), EmptySource(), link, log, clock=clock, gimbal_port=RecordingPort(math.radians(60.0)))
    calls = spy_gimbal_step(app)
    _run(app, link, monkeypatch, clock)
    log.close()
    assert len(calls) == N_TICKS
    assert [scan_arg(c) for c in calls] == [None] * N_TICKS
    header, rows = _read_csv(tmp_path / "app_log.csv")
    assert header == OLD_APP_COLUMNS and len(rows) == N_TICKS
    assert sorted(os.listdir(tmp_path)) == ["app_log.csv"]


def test_search_off_command_gimbal_loop_still_init_delta(monkeypatch):
    """Cung ca cua test_app_gimbal: khong phat hien -> lenh khop delta_init 90 do moi chu ky (khong bi quet)."""
    clock, link = FakeClock(), FakeLink()
    port = RecordingPort(math.radians(60.0))
    app = App(gimbal_only_cfg(), EmptySource(), link, clock=clock, gimbal_port=port)
    _run(app, link, monkeypatch, clock)
    assert [d for _, d in port.commands] == [pytest.approx(math.radians(90.0), abs=1e-9)] * N_TICKS
