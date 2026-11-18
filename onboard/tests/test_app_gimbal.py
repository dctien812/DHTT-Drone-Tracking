"""Buoc 5 thiet ke khop gat (.office/design-gimbal-steps-3-6.md): noi khop gat vao App, SimTruthSource, gimbal.csv.
TEST VIET TRUOC (pha do). Doi tuong gia: link MAVLink, nguon phat hien, cong khop (khong mo mang / SITL).

Giao dien test doi:
  App(cfg, source, link, logger=None, auto_engage=False, stop_file=None, clock=..., gimbal_port=None, gimbal_logger=None)
  build_source(args, cfg, gimbal_port=None); SimTruthSource(..., gimbal_port=None)
  dtrack.logger.GimbalLogger(path) (lop con CycleLogger, co close()); cot GIMBAL_COLUMNS ben duoi.
  main(): gimbal.csv cung thu muc voi --log; MOT cong dung chung cho build_source va App.

Quyet dinh giao dien (truong phong chot, vong sua 1):
  - GimbalController va supervisor/guidance nhan q THAN; chi tracker nhan q camera = camera_attitude(q_than, delta_act).
  - delta_act = port.angle(now) do o DAU chu ky (truoc port.command cua chu ky do).
  - delta_rate_dps = degrees(port.rate()); elev_ref_deg = sup.guidance.last_elev_ref_deg.
  - own=None: khong port.angle, khong port.command, khong ghi dong gimbal.csv.
  - App.__init__ nem ValueError khi gimbal.enabled ma thieu cong, hoac khi hai co khop cung bat.
  - Nhanh khop cu (camera.gimbal_enabled, GimbalModel) giu nguyen.
"""
import csv
import inspect
import json
import math
import os
import sys
from types import SimpleNamespace

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import dtrack.app as app_mod  # noqa: E402
from dtrack.app import App, build_source  # noqa: E402
from dtrack.config import AppConfig, GimbalConfig, make_camera  # noqa: E402
from dtrack.logger import CycleLogger  # noqa: E402
from dtrack.synthetic import SyntheticConfig  # noqa: E402
from dtrack.types import OwnState  # noqa: E402

OLD_APP_COLUMNS = [
    "t", "wall", "loop_dt", "hb_age", "pose_age", "engage", "armed", "mode",
    "pos_n", "pos_e", "pos_d", "vel_n", "vel_e", "vel_d", "qw", "qx", "qy", "qz",
    "trk_status", "los_n", "los_e", "los_d", "rate_n", "rate_e", "rate_d",
    "range", "range_sigma", "range_rate", "range_valid", "age", "n_det",
    "cmd_vn", "cmd_ve", "cmd_vd", "cmd_yaw", "sent", "state", "reason", "rtl",
]
GIMBAL_COLUMNS = ["t", "mode", "delta_cmd_deg", "delta_act_deg", "delta_rate_dps", "elev_los_deg",
                  "elev_aim_deg", "elev_ref_deg", "sat", "theta_deg"]

C15, S15 = math.cos(math.radians(15.0)), math.sin(math.radians(15.0))
Q_LEVEL = (1.0, 0.0, 0.0, 0.0)
Q_PITCH_M30 = (C15, 0.0, -S15, 0.0)        # pitch -30 do (mui chui 30 do, theta = +30): tinh tay
N_TICKS = 6


# ------------------------------------------------------------------ doi tuong gia
class FakeClock:
    """Dong ho gia: chi tien khi time.sleep (da thay) duoc goi -> moi chu ky dung 1/loop_hz."""

    def __init__(self, t0=100.0):
        self.t = t0

    def __call__(self):
        return self.t

    def sleep(self, d):
        self.t += max(0.0, d)


class FakeLink:
    """Thay MavlinkLink: tu the co dinh; sau n_ticks chu ky thi yeu cau App dung va tra own=None (phanh thoat ngay)."""

    def __init__(self, q=Q_LEVEL, n_ticks=N_TICKS, own_none=False, clock=None):
        self.q = q
        self.n_ticks = n_ticks
        self.own_none = own_none
        self.clock = clock
        self.polls = 0
        self.app = None
        self.sent = []

    def poll(self):
        self.polls += 1
        if self.polls == self.n_ticks and self.app is not None:
            self.app.request_stop()

    def own_state(self):
        if self.own_none or self.polls > self.n_ticks:
            return None
        return OwnState(t=0.0 if self.clock is None else self.clock(), pos_ned=(0.0, 0.0, -20.0), vel_ned=(0.0, 0.0, 0.0), q_world_body=self.q,
                        armed=True, mode="GUIDED")

    def heartbeat_age(self, now=None):
        return 0.1

    def pose_age(self, now=None):
        return 0.02

    def rc_engaged(self, ch, thr):
        return False

    def send_velocity(self, vel, yaw):
        self.sent.append((vel, yaw))

    def request_rtl(self):
        pass


class EmptySource:
    def poll(self):
        return []

    def close(self):
        pass


class RecordingPort:
    """Cong khop gia: goc co dinh, ghi thu tu goi vao danh sach su kien chung."""

    def __init__(self, angle_rad, events=None, rate_rad_s=0.5, follow=False):
        self.angle_rad = angle_rad
        self.events = events if events is not None else []
        self.commands = []
        self.last_cmd = angle_rad
        self.rate_rad_s = rate_rad_s
        self.follow = follow          # True: goc that nhay ngay toi lenh (de phan biet do truoc/sau command)

    def angle(self, t):
        self.events.append(("angle", t))
        return self.angle_rad

    def command(self, t, delta_rad):
        self.events.append(("command", t))
        self.commands.append((t, delta_rad))
        self.last_cmd = delta_rad
        if self.follow:
            self.angle_rad = float(delta_rad)

    def rate(self):
        return self.rate_rad_s

    def reset(self):
        self.events.append(("reset", None))


def _gimbal_cfg():
    return AppConfig(gimbal=GimbalConfig(enabled=True))


def _spy(app, events):
    """Boc tracker.update va sup.step THAT de ghi thu tu va tu the camera dua cho tracker."""
    seen_q = []
    orig_upd, orig_step = app.tracker.update, app.sup.step

    def upd(dets, own, now):
        events.append(("tracker", now))
        seen_q.append(tuple(float(c) for c in own.q_world_body))
        return orig_upd(dets, own, now)

    def step(inp):
        events.append(("sup", inp.t))
        if inp.own is not None:
            events.append(("sup_q", tuple(float(c) for c in inp.own.q_world_body)))
        return orig_step(inp)

    app.tracker.update = upd
    app.sup.step = step
    return seen_q


def _run(app, link, monkeypatch, clock):
    link.app = app
    monkeypatch.setattr(app_mod.time, "sleep", clock.sleep)
    assert app.run() == 0


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


# ------------------------------------------- (1) co tat: hanh vi cu, khong gimbal.csv
def test_flag_off_tracker_gets_body_attitude_and_only_app_log(tmp_path, monkeypatch):
    clock, events, link = FakeClock(), [], FakeLink(q=Q_PITCH_M30)
    log = CycleLogger(str(tmp_path / "app_log.csv"))
    app = App(AppConfig(), EmptySource(), link, log, clock=clock)
    seen_q = _spy(app, events)
    _run(app, link, monkeypatch, clock)
    log.close()
    assert seen_q == [pytest.approx(Q_PITCH_M30, abs=1e-12)] * N_TICKS
    assert sorted(os.listdir(tmp_path)) == ["app_log.csv"]
    header, rows = _read_csv(tmp_path / "app_log.csv")
    assert header == OLD_APP_COLUMNS and len(rows) == N_TICKS


def test_flag_off_given_port_is_never_touched(monkeypatch):
    clock, events, link = FakeClock(), [], FakeLink(q=Q_PITCH_M30)
    port = RecordingPort(math.radians(60.0), events)
    app = App(AppConfig(), EmptySource(), link, clock=clock, gimbal_port=port)
    seen_q = _spy(app, events)
    _run(app, link, monkeypatch, clock)
    assert [e for e in events if e[0] in ("angle", "command", "reset")] == []
    assert seen_q == [pytest.approx(Q_PITCH_M30, abs=1e-12)] * N_TICKS


def _write_cfg(path, enabled):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"gimbal": {"enabled": enabled}}, f)


class MainLink(FakeLink):
    def __init__(self, cfg):
        super().__init__(own_none=True)
        self.target_system = 1

    def connect(self):
        pass

    def close(self):
        pass


def _run_main(tmp_path, monkeypatch, enabled):
    """main() voi link gia va build_source gia; stop-file da ton tai -> vong lap thoat ngay (0 chu ky)."""
    cfgdir, logdir = tmp_path / "cfg", tmp_path / "logs"
    cfgdir.mkdir(), logdir.mkdir()
    _write_cfg(str(cfgdir / "c.json"), enabled)
    (cfgdir / "stop").write_text("x")
    rec = {}

    def fake_build_source(*a, **kw):
        rec["bs_args"], rec["bs_kw"] = a, kw
        return EmptySource()

    orig_init = App.__init__

    def init(self, *a, **kw):
        ba = inspect.signature(orig_init).bind(self, *a, **kw)
        rec["app_port"] = ba.arguments.get("gimbal_port")
        orig_init(self, *a, **kw)

    monkeypatch.setattr(app_mod, "MavlinkLink", MainLink)
    monkeypatch.setattr(app_mod, "build_source", fake_build_source)
    monkeypatch.setattr(App, "__init__", init)
    rc = app_mod.main(["--config", str(cfgdir / "c.json"), "--source", "sim", "--auto-engage",
                       "--log", str(logdir / "app_log.csv"), "--stop-file", str(cfgdir / "stop")])
    assert rc == 0
    return logdir, rec


def test_main_flag_off_writes_no_gimbal_csv(tmp_path, monkeypatch):
    logdir, _ = _run_main(tmp_path, monkeypatch, enabled=False)
    assert sorted(os.listdir(logdir)) == ["app_log.csv"]


def test_main_flag_on_writes_gimbal_csv_next_to_log(tmp_path, monkeypatch):
    logdir, _ = _run_main(tmp_path, monkeypatch, enabled=True)
    assert sorted(os.listdir(logdir)) == ["app_log.csv", "gimbal.csv"]
    header, rows = _read_csv(logdir / "gimbal.csv")
    assert header == GIMBAL_COLUMNS and rows == []


def test_main_flag_on_shares_one_port_between_source_and_app(tmp_path, monkeypatch):
    _, rec = _run_main(tmp_path, monkeypatch, enabled=True)
    a, kw = rec["bs_args"], rec["bs_kw"]
    src_port = kw["gimbal_port"] if "gimbal_port" in kw else (a[2] if len(a) > 2 else None)
    assert src_port is not None
    assert rec.get("app_port") is src_port


# ------------------------------------------- (2) co bat: thu tu va tu the camera
def test_flag_on_order_angle_tracker_sup_command_each_cycle(monkeypatch):
    clock, events, link = FakeClock(), [], FakeLink()
    port = RecordingPort(math.radians(60.0), events)
    app = App(_gimbal_cfg(), EmptySource(), link, clock=clock, gimbal_port=port)
    _spy(app, events)
    _run(app, link, monkeypatch, clock)
    ev = [e for e in events if e[0] not in ("sup_q", "reset")]     # reset luc khoi tao: khong rang buoc
    assert [e[0] for e in ev] == ["angle", "tracker", "sup", "command"] * N_TICKS
    for i in range(N_TICKS):              # cung mot 'now' trong mot chu ky
        ts = {e[1] for e in ev[4 * i:4 * i + 4]}
        assert len(ts) == 1


def test_flag_on_tracker_gets_camera_attitude_from_port_angle(monkeypatch):
    # than nam ngang, delta 60 do: q_cam = q_body * Ry(30 do) = (cos 15, 0, sin 15, 0) (tinh tay)
    clock, events, link = FakeClock(), [], FakeLink(q=Q_LEVEL)
    app = App(_gimbal_cfg(), EmptySource(), link, clock=clock,
              gimbal_port=RecordingPort(math.radians(60.0), events))
    seen_q = _spy(app, events)
    _run(app, link, monkeypatch, clock)
    assert seen_q == [pytest.approx((C15, 0.0, S15, 0.0), abs=1e-9)] * N_TICKS


def test_flag_on_commands_controller_output_init_delta_when_searching(monkeypatch):
    # khong co phat hien -> SEARCH chua khoa -> lenh delta_init (90 do mac dinh)
    clock, link = FakeClock(), FakeLink()
    port = RecordingPort(math.radians(60.0))
    app = App(_gimbal_cfg(), EmptySource(), link, clock=clock, gimbal_port=port)
    _run(app, link, monkeypatch, clock)
    assert [d for _, d in port.commands] == [pytest.approx(math.radians(90.0), abs=1e-9)] * N_TICKS


# ------------------------------------------- (3) own None: khong lenh khop
def test_flag_on_no_command_when_own_state_missing(monkeypatch):
    clock, link = FakeClock(), FakeLink(own_none=True)
    port = RecordingPort(math.radians(60.0))
    app = App(_gimbal_cfg(), EmptySource(), link, clock=clock, gimbal_port=port)
    _run(app, link, monkeypatch, clock)
    assert app.stats["ticks"] == N_TICKS
    assert port.commands == []


# ------------------------------------------- (4) bat ma thieu cong -> ValueError
def test_flag_on_without_port_raises_value_error():
    with pytest.raises(ValueError):
        App(_gimbal_cfg(), EmptySource(), FakeLink())


# ------------------------------------------- (8) hai co khop cung bat -> loi
def test_both_gimbal_flags_on_app_raises_value_error():
    cfg = _gimbal_cfg()
    cfg.camera.gimbal_enabled = True
    with pytest.raises(ValueError):
        App(cfg, EmptySource(), FakeLink(), gimbal_port=RecordingPort(math.radians(90.0)))


# ------------------------------------------- (5) gimbal.csv: cot, so dong, gia tri
def _run_gimbal_log(tmp_path, monkeypatch, q):
    from dtrack.logger import GimbalLogger
    clock, link = FakeClock(), FakeLink(q=q)
    glog = GimbalLogger(str(tmp_path / "gimbal.csv"))
    alog = CycleLogger(str(tmp_path / "app_log.csv"))
    app = App(_gimbal_cfg(), EmptySource(), link, alog, clock=clock,
              gimbal_port=RecordingPort(math.radians(60.0)), gimbal_logger=glog)
    _run(app, link, monkeypatch, clock)
    glog.close(), alog.close()
    return app


def test_gimbal_csv_has_columns_and_one_row_per_cycle(tmp_path, monkeypatch):
    app = _run_gimbal_log(tmp_path, monkeypatch, Q_PITCH_M30)
    header, rows = _read_csv(tmp_path / "gimbal.csv")
    assert header == GIMBAL_COLUMNS
    assert len(rows) == N_TICKS == app.stats["ticks"]


def test_gimbal_csv_values_delta_and_theta(tmp_path, monkeypatch):
    # cong tra 60 do; lenh init 90 do; than pitch -30 do -> theta = asin(R[2,0]) = +30 do (tinh tay)
    _run_gimbal_log(tmp_path, monkeypatch, Q_PITCH_M30)
    header, rows = _read_csv(tmp_path / "gimbal.csv")
    r = dict(zip(header, rows[-1]))
    assert r["mode"] == "init"
    assert float(r["delta_act_deg"]) == pytest.approx(60.0, abs=1e-3)
    assert float(r["delta_cmd_deg"]) == pytest.approx(90.0, abs=1e-3)
    assert float(r["theta_deg"]) == pytest.approx(30.0, abs=1e-3)


def test_app_log_columns_unchanged_when_gimbal_on(tmp_path, monkeypatch):
    _run_gimbal_log(tmp_path, monkeypatch, Q_LEVEL)
    header, rows = _read_csv(tmp_path / "app_log.csv")
    assert header == OLD_APP_COLUMNS and len(rows) == N_TICKS


def test_gimbal_csv_delta_rate_is_degrees_per_second(tmp_path, monkeypatch):
    # RecordingPort.rate() = 0.5 rad/s -> 28.6479 do/s
    _run_gimbal_log(tmp_path, monkeypatch, Q_LEVEL)
    header, rows = _read_csv(tmp_path / "gimbal.csv")
    assert [float(dict(zip(header, r))["delta_rate_dps"]) for r in rows] == \
        [pytest.approx(28.6479, abs=1e-3)] * N_TICKS


Q_PITCH_M10 = (math.cos(math.radians(5.0)), 0.0, -math.sin(math.radians(5.0)), 0.0)


def test_gimbal_csv_theta_for_pitch_minus_10(tmp_path, monkeypatch):
    _run_gimbal_log(tmp_path, monkeypatch, Q_PITCH_M10)
    header, rows = _read_csv(tmp_path / "gimbal.csv")
    assert float(dict(zip(header, rows[-1]))["theta_deg"]) == pytest.approx(10.0, abs=1e-3)


# ------------------------------------------- (3b) own None co gimbal_logger: khong do, khong lenh, khong dong
def test_own_none_no_angle_no_command_no_gimbal_row(tmp_path, monkeypatch):
    from dtrack.logger import GimbalLogger
    clock, events, link = FakeClock(), [], FakeLink(own_none=True)
    port = RecordingPort(math.radians(60.0), events)
    glog = GimbalLogger(str(tmp_path / "gimbal.csv"))
    app = App(_gimbal_cfg(), EmptySource(), link, clock=clock, gimbal_port=port, gimbal_logger=glog)
    _run(app, link, monkeypatch, clock)
    glog.close()
    header, rows = _read_csv(tmp_path / "gimbal.csv")
    assert app.stats["ticks"] == N_TICKS
    assert [e for e in events if e[0] in ("angle", "command")] == []
    assert header == GIMBAL_COLUMNS and rows == []


# ------------------------------------------- (2b) dang bam (TRACK): gia tri cot, q than/q camera
REL_M10 = (25.0 * math.cos(math.radians(10.0)), 0.0, 25.0 * math.sin(math.radians(10.0)))   # 25 m, 10 do duoi ngang


class GeomSource:
    """Nguon hinh gia co hinh hoc: muc tieu dung yen o rel (NED, so voi chaser), chieu qua camera that
    q_cam = camera_attitude(q_than, goc khop hien tai cua cong) - doc thang port.angle_rad, khong goi angle()."""

    def __init__(self, clock, port, q_body, rel=REL_M10):
        from dtrack.synthetic import SyntheticDetector
        self.clock, self.port, self.q_body, self.rel = clock, port, q_body, rel
        self.det = SyntheticDetector(make_camera(0.0, 1739.0), SyntheticConfig(**NOISELESS))

    def poll(self):
        from dtrack.gimbal import camera_attitude
        t = self.clock()
        q = tuple(float(c) for c in camera_attitude(self.q_body, self.port.angle_rad))
        own = OwnState(t=t, pos_ned=(0.0, 0.0, 0.0), vel_ned=(0.0, 0.0, 0.0), q_world_body=q)
        return self.det.process(t, self.rel, own)

    def close(self):
        pass


def _run_track(tmp_path, monkeypatch, q_body, hold_offset_deg, delta_init_deg, port_init_deg, n=20, follow=True):
    from dtrack.config import GuidanceConfig
    from dtrack.logger import GimbalLogger
    clock, events = FakeClock(), []
    cfg = AppConfig(guidance=GuidanceConfig(elev_ramp_enabled=True),
                    gimbal=GimbalConfig(enabled=True, hold_offset_deg=hold_offset_deg, delta_init_deg=delta_init_deg))
    port = RecordingPort(math.radians(port_init_deg), events, rate_rad_s=0.0, follow=follow)
    link = FakeLink(q=q_body, n_ticks=n, clock=clock)
    glog = GimbalLogger(str(tmp_path / "gimbal.csv"))
    app = App(cfg, GeomSource(clock, port, q_body), link, clock=clock, auto_engage=True,
              gimbal_port=port, gimbal_logger=glog)
    seen_q = _spy(app, events)
    _run(app, link, monkeypatch, clock)
    glog.close()
    header, rows = _read_csv(tmp_path / "gimbal.csv")
    assert header == GIMBAL_COLUMNS and len(rows) == n
    return app, [dict(zip(header, r)) for r in rows], events, seen_q


# than pitch -30 (theta 30), muc tieu 10 do duoi ngang, hold_offset 2 -> aim -8 -> delta = 90 - 30 + 8 = 68 do (tinh tay).
# Neu bo dieu khien nhan q CAMERA (pitch -30 + 90 - delta_act ~ -5) thi can delta ~93 -> ket 90, sat: khac 68.
def _pitched_track(tmp_path, monkeypatch):
    return _run_track(tmp_path, monkeypatch, Q_PITCH_M30, hold_offset_deg=2.0, delta_init_deg=65.0, port_init_deg=60.0)


def test_track_rows_log_elev_los_aim_and_delta_from_body_q(tmp_path, monkeypatch):
    _, rows, _, _ = _pitched_track(tmp_path, monkeypatch)
    trk = [r for r in rows if r["mode"] == "track"]
    assert len(trk) >= 5
    r = trk[-1]
    assert float(r["elev_los_deg"]) == pytest.approx(-10.0, abs=0.3)
    assert float(r["elev_aim_deg"]) - float(r["elev_los_deg"]) == pytest.approx(2.0, abs=1e-3)
    assert float(r["delta_cmd_deg"]) == pytest.approx(68.0, abs=0.5)
    assert r["sat"] in ("0", "False", "false")


def test_track_controller_uses_body_q_with_port_stuck_at_60(tmp_path, monkeypatch):
    # cong KHONG theo lenh, giu delta 60: q camera = pitch thuan (-30 + 30) = 0 do. Bo dieu khien dung q than:
    # delta = 90 - 30 + 8 = 68, sat 0. Neu dung q camera: can 90 - 0 + 8 = 98 -> ket 90, sat 1 (tinh tay).
    _, rows, _, _ = _run_track(tmp_path, monkeypatch, Q_PITCH_M30, hold_offset_deg=2.0, delta_init_deg=65.0,
                               port_init_deg=60.0, follow=False)
    trk = [r for r in rows if r["mode"] == "track"]
    assert len(trk) >= 10
    for r in trk:
        assert float(r["delta_act_deg"]) == pytest.approx(60.0, abs=1e-3)
        assert float(r["delta_cmd_deg"]) == pytest.approx(68.0, abs=0.5)
        assert r["sat"] in ("0", "False", "false")


def test_track_elev_ref_logged_from_guidance_ramp(tmp_path, monkeypatch):
    app, rows, _, _ = _pitched_track(tmp_path, monkeypatch)
    ref = app.sup.guidance.last_elev_ref_deg
    assert ref is not None
    assert float(rows[-1]["elev_ref_deg"]) == pytest.approx(ref, abs=1e-3)


def test_supervisor_gets_body_q_and_tracker_gets_camera_q(tmp_path, monkeypatch):
    _, rows, events, seen_q = _pitched_track(tmp_path, monkeypatch)
    sup_q = [e[1] for e in events if e[0] == "sup_q"]
    assert sup_q == [pytest.approx(Q_PITCH_M30, abs=1e-12)] * len(rows)
    for r, q in zip(rows, seen_q):      # q camera = pitch thuan (-30 + 90 - delta_act) do (tinh tay)
        p = math.radians(60.0 - float(r["delta_act_deg"]))
        assert q == pytest.approx((math.cos(p / 2), 0.0, math.sin(p / 2), 0.0), abs=2e-6)


def test_delta_act_is_measured_at_cycle_start_before_command(tmp_path, monkeypatch):
    _, rows, _, _ = _pitched_track(tmp_path, monkeypatch)
    assert float(rows[0]["delta_act_deg"]) == pytest.approx(60.0, abs=1e-3)
    for prev, cur in zip(rows, rows[1:]):
        assert float(cur["delta_act_deg"]) == pytest.approx(float(prev["delta_cmd_deg"]), abs=1e-3)
    assert float(rows[1]["delta_act_deg"]) == pytest.approx(65.0, abs=1e-3)     # chu ky 0: lenh init 65


def test_track_level_body_target_below_saturates_at_90(tmp_path, monkeypatch):
    # theta 0, muc tieu -10 do: can delta = 100 do > 90 -> ket 90, sat (thiet ke: Quyet dinh chung)
    _, rows, _, _ = _run_track(tmp_path, monkeypatch, Q_LEVEL, hold_offset_deg=0.0, delta_init_deg=90.0,
                               port_init_deg=90.0)
    trk = [r for r in rows if r["mode"] == "track"]
    assert len(trk) >= 5
    assert trk[-1]["sat"] in ("1", "True", "true")
    assert float(trk[-1]["delta_cmd_deg"]) == pytest.approx(90.0, abs=1e-3)


# ------------------------------------------- nhanh khop cu (camera.gimbal_enabled, GimbalModel) giu nguyen
def test_old_gimbal_model_branch_unchanged(monkeypatch):
    # GimbalModel cu khoi dong da on dinh pitch (hanh trinh 50 > 30): q cho tracker = than bo pitch = (1,0,0,0)
    from dtrack.config import CameraConfig
    clock, events = FakeClock(), []
    link = FakeLink(q=Q_PITCH_M30, clock=clock)
    app = App(AppConfig(camera=CameraConfig(gimbal_enabled=True)), EmptySource(), link, clock=clock)
    seen_q = _spy(app, events)
    _run(app, link, monkeypatch, clock)
    assert seen_q == [pytest.approx(Q_LEVEL, abs=1e-9)] * N_TICKS
    assert [e[1] for e in events if e[0] == "sup_q"] == [pytest.approx(Q_PITCH_M30, abs=1e-12)] * N_TICKS


# ------------------------------------------- (6) SimTruthSource voi cong khop
class FakeReader:
    """Thay SimStateReader (ranh gioi MAVLink). Tuple SIM_STATE tu bang lop; thoi diem nhan = dong ho cua nguon."""
    states = {}

    def __init__(self, url, rate_hz=50.0, clock=None, connect_timeout=60.0):
        self.url, self.clock = url, clock

    @property
    def last(self):
        return (self.clock(),) + tuple(FakeReader.states[self.url])

    def poll(self):
        pass

    def close(self):
        pass


NOISELESS = dict(frame_rate_hz=30.0, latency_s=0.0, center_sigma_px=0.0, size_sigma_px=0.0,
                 p_miss=0.0, p_false=0.0, clip_to_frame=True)


def _setup_truth(monkeypatch):
    """Muc tieu 25 m phia Bac, cung do cao; than chaser pitch -30 do (mui chui), yaw 0.
    delta 60 do: truc quang trong than = 30 do tren mui -> nam ngang, dung vao muc tieu (tinh tay)."""
    import simtools.sim_truth_source as sts
    from dtrack.mavlink_io import latlon_to_ned
    monkeypatch.setattr(sts, "SimStateReader", FakeReader)
    lat0, lon0 = -35.0, 149.0
    n0, _ = latlon_to_ned(lat0, lon0, lat0 + 1e-4, lon0)
    FakeReader.states = {"T": (lat0 + 1e-4 * 25.0 / n0, lon0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                         "C": (lat0, lon0, 100.0, 0.0, 0.0, 0.0, 0.0, math.radians(-30.0), 0.0)}
    return sts


def _poll_n(src, clock, n=5):
    out = []
    for _ in range(n):
        clock.t += 1.0 / 30.0
        out.extend(src.poll())
    return out


def _truth_source(sts, clock, delta_deg):
    return sts.SimTruthSource(target_url="T", chaser_url="C", camera=make_camera(0.0, 1739.0),
                              synth=SyntheticConfig(**NOISELESS), clock=clock,
                              gimbal_port=RecordingPort(math.radians(delta_deg)))


def test_sim_source_target_on_boresight_lands_at_image_center(monkeypatch):
    sts, clock = _setup_truth(monkeypatch), FakeClock()
    dets = _poll_n(_truth_source(sts, clock, 60.0), clock)
    assert len(dets) >= 4
    for d in dets:
        assert (d.cx, d.cy) == pytest.approx((728.0, 544.0), abs=2.0)


def test_sim_source_delta_off_by_20deg_puts_target_out_of_frame(monkeypatch):
    # delta 80 do: truc quang 20 do tren duong ngang; muc tieu 20 do duoi truc > nua FOV dung atan(544/1739)=17.4 do
    sts, clock = _setup_truth(monkeypatch), FakeClock()
    assert _poll_n(_truth_source(sts, clock, 80.0), clock) == []


# ------------------------------------------- (7) build_source
def test_build_source_two_args_still_works(monkeypatch):
    sts = _setup_truth(monkeypatch)
    args = SimpleNamespace(source="sim", sim_target="T", sim_chaser="C", sim_seed=7, sim_blackout_file=None)
    src = build_source(args, AppConfig())
    assert isinstance(src, sts.SimTruthSource)
    src.poll()
    src.close()


def test_build_source_passes_gimbal_port_to_sim_source(monkeypatch):
    # cfg bat khop -> camera.tilt_up_deg = 0; cong 60 do + than pitch -30 do -> muc tieu o giua anh
    # nguon cua build_source dung dong ho that va nhieu mac dinh (nhu test_target_shape): lay trung vi
    import time
    _setup_truth(monkeypatch)
    args = SimpleNamespace(source="sim", sim_target="T", sim_chaser="C", sim_seed=7, sim_blackout_file=None)
    src = build_source(args, _gimbal_cfg(), gimbal_port=RecordingPort(math.radians(60.0)))
    dets, t_end = [], time.monotonic() + 5.0
    while len(dets) < 15 and time.monotonic() < t_end:
        dets.extend(src.poll())
        time.sleep(0.004)
    assert len(dets) >= 15
    cx = sorted(d.cx for d in dets)[len(dets) // 2]
    cy = sorted(d.cy for d in dets)[len(dets) // 2]
    assert (cx, cy) == pytest.approx((728.0, 544.0), abs=8.0)
