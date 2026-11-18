import base64
import math
import os
import socket

import numpy as np
import pytest

from labview.config import Config, ConfigError, validate
from labview.lock import Track
from labview.outputs import LockSink
from labview.pipeline import Pipeline
from labview.server import create_app
from labview.sources import Frame, FrameSource
from labview.__main__ import main

PW = "correct-horse-battery"
J = {"Content-Type": "application/json"}


class FakeSource(FrameSource):
    name, kind = "fake", "file"

    def open(self): pass
    def read(self): return None


class FakeDetector:
    def __init__(self): self.tracks = []
    def track(self, image): return list(self.tracks)
    def reset(self): pass


class Rec(LockSink):
    def __init__(self): self.reports = []
    def on_lock(self, r): self.reports.append(r)


def build(password=None, allow_network=False, **kw):
    cfg = validate(Config(source="file:x", password=password, allow_network=allow_network, max_width=0, **kw))
    det, rec = FakeDetector(), Rec()
    pipe = Pipeline(FakeSource(), det, cfg, sinks=[rec])
    det.tracks = [Track(7, (300.0, 200.0, 340.0, 230.0), 0.8), Track(8, (50.0, 50.0, 80.0, 70.0), 0.5)]
    pipe.process_frame(Frame(np.zeros((480, 640, 3), np.uint8), 0.0, 0))
    app = create_app(pipe, cfg)
    return app.test_client(), pipe, det, rec


def auth(pw=PW, user="lab"):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


# ---------------- chế độ localhost, không mật khẩu
def test_page_state_snapshot():
    c, *_ = build()
    r = c.get("/")
    assert r.status_code == 200 and "Content-Security-Policy" in r.headers
    assert c.get("/static/app.js").status_code == 200
    s = c.get("/api/state").get_json()
    assert s["running"] and len(s["tracks"]) == 2 and s["lock"]["active"] is False
    assert c.get("/snapshot.jpg").data[:2] == b"\xff\xd8"


def test_lock_by_click_release_flow_and_geometry():
    c, pipe, det, rec = build()
    # (320,215)px -> x=0.5, y=0.4479 : trong khung 7
    r = c.post("/api/lock", json={"x": 0.5, "y": 215 / 480})
    assert r.get_json() == {"ok": True, "track_id": 7}
    pipe.process_frame(Frame(np.zeros((480, 640, 3), np.uint8), 0.1, 1))
    L = c.get("/api/state").get_json()["lock"]
    assert L["active"] and L["track_id"] == 7 and L["visible"]
    fx = 320 / math.tan(math.radians(33))  # hfov mặc định 66 độ
    assert abs(L["yaw_deg"]) < 0.01
    assert L["pitch_deg"] == pytest.approx(math.degrees(math.atan((240 - 215) / fx)), abs=0.05)
    assert L["assumed_width_m"] == 0.30 and L["distance_m"] > 0
    assert rec.reports[-1] is not None and rec.reports[-1].track_id == 7
    assert c.post("/api/release", json={}).get_json()["released"] is True
    pipe.process_frame(Frame(np.zeros((480, 640, 3), np.uint8), 0.2, 2))  # trạng thái công bố theo khung kế
    assert c.get("/api/state").get_json()["lock"]["active"] is False


def test_click_outside_all_boxes_does_not_lock():
    c, *_ = build()
    r = c.post("/api/lock", json={"x": 0.9, "y": 0.9})
    assert r.status_code == 200 and r.get_json()["ok"] is False
    assert c.get("/api/state").get_json()["lock"]["active"] is False


def test_lock_best_and_by_id():
    c, *_ = build()
    assert c.post("/api/lock", json={"best": True}).get_json()["track_id"] == 7
    assert c.post("/api/lock", json={"track_id": 8}).get_json()["ok"] is True
    assert c.post("/api/lock", json={"track_id": 99}).get_json()["ok"] is False


def test_auto_release_through_pipeline():
    c, pipe, det, _ = build()
    now = [10.0]
    pipe.lock._clock = lambda: now[0]
    c.post("/api/lock", json={"track_id": 7})
    det.tracks = []
    now[0] += 2.5
    pipe.process_frame(Frame(np.zeros((480, 640, 3), np.uint8), 0.2, 2))
    s = c.get("/api/state").get_json()
    assert s["lock"]["active"] is False and s["notice"] and "TU BO KHOA" in s["notice"]


@pytest.mark.parametrize("body", [
    {}, {"x": 0.5}, {"x": "a", "y": 0.5}, {"x": 2, "y": 0.5}, {"x": True, "y": 0.5},
    {"x": float("nan"), "y": 0.5}, {"track_id": -1}, {"track_id": "7"}, {"track_id": 1.5},
    {"track_id": 7, "x": 0.1, "y": 0.1}, {"best": False}, [1, 2], "x",
])
def test_input_validation(body):
    c, *_ = build()
    r = c.post("/api/lock", json=body)
    assert r.status_code == 400


def test_post_requires_json_content_type_and_same_origin():
    c, *_ = build()
    assert c.post("/api/lock", data="x=1", content_type="application/x-www-form-urlencoded").status_code == 415
    assert c.post("/api/release", data="").status_code == 415
    r = c.post("/api/lock", json={"best": True}, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    r = c.post("/api/lock", json={"best": True}, headers={"Origin": "http://localhost"})  # Host của test client là localhost
    assert r.status_code == 200


def test_bad_host_header_rejected_in_loopback_mode():
    c, *_ = build()
    assert c.get("/api/state", headers={"Host": "evil.example"}).status_code == 403


def test_get_on_post_endpoint_and_other_methods():
    c, *_ = build()
    assert c.get("/api/lock").status_code == 405
    assert c.put("/api/lock", json={}).status_code in (405,)


def test_unknown_paths_do_not_read_files():
    c, *_ = build()
    for p in ("/static/../server.py", "/static/index.html", "/../config.py", "/etc/passwd", "/%2e%2e/config.py"):
        assert c.get(p).status_code == 404


# ---------------- chế độ mạng + mật khẩu
def test_network_mode_requires_auth_for_everything():
    c, *_ = build(password=PW, allow_network=True)
    assert c.get("/").status_code == 401
    assert c.get("/api/state").status_code == 401
    assert c.get("/stream.mjpg").status_code == 401
    assert c.post("/api/lock", json={"best": True}).status_code == 401
    assert c.post("/api/release", json={}).status_code == 401


def test_network_mode_wrong_password_rejected_and_right_accepted():
    c, pipe, *_ = build(password=PW, allow_network=True)
    assert c.post("/api/lock", json={"best": True}, headers=auth("wrong-password")).status_code == 401
    assert c.post("/api/lock", json={"best": True}, headers=auth(user="root")).status_code == 401
    assert c.post("/api/lock", json={"best": True}, headers={"Authorization": "Basic !!!"}).status_code == 401
    assert pipe.lock.locked_id() is None
    assert c.post("/api/lock", json={"best": True}, headers=auth()).status_code == 200
    assert pipe.lock.locked_id() == 7
    assert c.get("/api/state", headers=auth()).status_code == 200


def test_network_mode_bruteforce_throttled():
    c, *_ = build(password=PW, allow_network=True)
    for _ in range(5):
        assert c.get("/api/state", headers=auth("bad-bad-bad")).status_code == 401
    assert c.get("/api/state", headers=auth()).status_code == 429


def test_password_never_in_config_repr():
    cfg = Config(password=PW)
    assert PW not in repr(cfg)


# ---------------- khởi động
def test_network_mode_refuses_without_password():
    with pytest.raises(ConfigError):
        validate(Config(allow_network=True, password=None))
    with pytest.raises(ConfigError):
        validate(Config(allow_network=True, password="short"))
    validate(Config(allow_network=True, password=PW))


def test_non_loopback_host_needs_flag():
    with pytest.raises(ConfigError):
        validate(Config(host="0.0.0.0"))
    assert validate(Config()).host == "127.0.0.1"
    assert validate(Config(allow_network=True, password=PW)).host == "0.0.0.0"


def test_main_exits_2_in_network_mode_without_password(monkeypatch, capsys):
    monkeypatch.delenv("LABVIEW_PASSWORD", raising=False)
    assert main(["--source", "file:x.mp4", "--allow-network"]) == 2
    assert "mat khau" in capsys.readouterr().err.lower()


def test_main_password_from_env_and_file(monkeypatch, tmp_path):
    from labview.__main__ import parse
    monkeypatch.setenv("LABVIEW_PASSWORD", PW)
    assert parse(["--source", "file:x", "--allow-network"]).password == PW
    monkeypatch.delenv("LABVIEW_PASSWORD")
    f = tmp_path / "pw.txt"
    f.write_text(PW + "\n")
    f.chmod(0o600)
    assert parse(["--source", "file:x", "--allow-network", "--password-file", str(f)]).password == PW


# ---------------- (A) giới hạn tổng, mật khẩu, file mật khẩu
def ip(n):
    return {"REMOTE_ADDR": n}


def get(c, hdr=None, addr="127.0.0.1", path="/api/state"):
    return c.get(path, headers=hdr or {}, environ_overrides=ip(addr))


def test_global_limit_across_many_ips_and_owner_still_gets_in():
    c, *_ = build(password=PW, allow_network=True)
    lim = c.application.extensions["labview.limiter"]
    now = [1000.0]
    lim.clock = lambda: now[0]
    assert get(c, auth(), "10.9.9.9").status_code == 200           # chủ đăng nhập đúng trước khi bị dò
    for i in range(20):                                              # 20 IP khác nhau, mỗi IP chỉ 1 lần sai
        assert get(c, auth("guess-%02d-xxxxxx" % i), "10.0.0.%d" % i).status_code == 401
    assert get(c, auth("guess-xx-xxxxxx"), "10.0.1.1").status_code == 429      # IP mới, sai: 429
    assert get(c, None, "10.0.1.2").status_code == 429                           # chưa xác thực: 429
    assert get(c, auth(), "10.0.1.3").status_code == 429                         # IP lạ nhập ĐÚNG vẫn 429 (không thành máy dò)
    assert get(c, auth(), "10.9.9.9").status_code == 200                         # chủ (IP đã tin cậy) vẫn vào được
    assert get(c, auth("wrong-wrong-wrong"), "10.9.9.9").status_code == 429     # nhưng sai thì vẫn 429
    now[0] += 61
    assert get(c, auth("wrong-wrong-wrong"), "10.0.1.4").status_code == 401     # hết 60 s: mở lại
    assert get(c, auth(), "10.0.1.3").status_code == 200


def test_owner_not_locked_out_by_own_typos():
    c, *_ = build(password=PW, allow_network=True)
    now = [1000.0]
    c.application.extensions["labview.limiter"].clock = lambda: now[0]
    assert get(c, auth()).status_code == 200
    for _ in range(5):
        assert get(c, auth("typo-typo-typo")).status_code == 401
    r = get(c, auth("typo-typo-typo"))
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert get(c, auth()).status_code == 429                                       # đang bị chặn theo IP: đúng cũng 429
    now[0] += 61
    assert get(c, auth()).status_code == 200                                       # hết chặn: vào được


def test_password_min_length_12():
    with pytest.raises(ConfigError):
        validate(Config(allow_network=True, password="a" * 11))
    validate(Config(allow_network=True, password="a" * 12))


@pytest.mark.skipif(os.name != "posix", reason="quyền kiểu Unix")
def test_password_file_must_not_be_group_or_world_readable(tmp_path):
    from labview.config import load_password
    f = tmp_path / "pw.txt"
    f.write_text(PW + "\n")
    f.chmod(0o644)
    with pytest.raises(ConfigError):
        load_password(str(f))
    f.chmod(0o640)
    with pytest.raises(ConfigError):
        load_password(str(f))
    f.chmod(0o600)
    assert load_password(str(f)) == PW
    f.chmod(0o400)
    assert load_password(str(f)) == PW


# ---------------- (C) tiêu đề Host ở chế độ mạng
def test_network_mode_host_allowlist():
    c, *_ = build(password=PW, allow_network=True)
    assert c.get("/api/state", headers={**auth(), "Host": "evil.example"}).status_code == 403
    assert c.get("/api/state", headers={**auth(), "Host": "evil.example:8080"}).status_code == 403
    assert c.get("/api/state", headers={**auth(), "Host": "[::1"}).status_code == 403
    assert c.get("/api/state", headers={**auth(), "Host": "localhost:8080"}).status_code == 200
    assert c.get("/api/state", headers={**auth(), "Host": socket.gethostname()}).status_code == 200
    assert c.get("/api/state", headers={"Host": "evil.example"}).status_code == 403   # 403 trước cả yêu cầu xác thực


def test_allowed_hosts_defaults_and_extra():
    cfg = validate(Config(allow_network=True, password=PW, host="192.168.1.50", allowed_hosts=["Lab.Local"]))
    assert {"192.168.1.50", "localhost", socket.gethostname().lower(), "lab.local"} <= set(cfg.allowed_hosts)
    cfg = validate(Config(allow_network=True, password=PW))  # nghe mọi giao diện: 0.0.0.0 không phải tên khách gõ
    assert "0.0.0.0" not in cfg.allowed_hosts and "localhost" in cfg.allowed_hosts
    c, *_ = build(password=PW, allow_network=True, host="192.168.1.50", allowed_hosts=["lab.local"])
    for h, code in (("192.168.1.50:8080", 200), ("lab.local", 200), ("192.168.1.51", 403)):
        assert c.get("/api/state", headers={**auth(), "Host": h}).status_code == code


def test_warn_when_allow_network_without_host(monkeypatch, capsys):
    from labview.__main__ import parse
    monkeypatch.setenv("LABVIEW_PASSWORD", PW)
    parse(["--source", "file:x", "--allow-network"])
    assert "--host" in capsys.readouterr().err
    parse(["--source", "file:x", "--allow-network", "--host", "192.168.1.50"])
    assert capsys.readouterr().err == ""


def test_password_file_rejected_by_main(monkeypatch, tmp_path, capsys):
    if os.name != "posix":
        pytest.skip("quyền kiểu Unix")
    monkeypatch.delenv("LABVIEW_PASSWORD", raising=False)
    f = tmp_path / "pw.txt"
    f.write_text(PW)
    f.chmod(0o644)
    assert main(["--source", "file:x.mp4", "--allow-network", "--password-file", str(f)]) == 2
    assert "chmod 600" in capsys.readouterr().err


# ---------------- (B) luồng MJPEG trả lại chỗ
def test_stream_slots_released_when_source_ended():
    c, pipe, *_ = build(max_stream_clients=2)
    pipe._done = True  # nguồn hết, khung cuối đã công bố
    for _ in range(6):  # nhiều hơn số chỗ tối đa: nếu rò chỗ thì lần 3 trở đi nhận 503
        r = c.get("/stream.mjpg")
        assert r.status_code == 200 and r.data.count(b"--frame") == 1


def test_stream_resends_last_frame_and_frees_slot_on_disconnect(monkeypatch):
    monkeypatch.setattr("labview.server._STREAM_RESEND_S", 0.05)
    c, pipe, *_ = build(max_stream_clients=1)
    for _ in range(4):  # nguồn "đứng" (không hết, không khung mới): người xem ngắt rồi mở lại
        r = c.get("/stream.mjpg", buffered=False)
        assert r.status_code == 200
        it = iter(r.response)
        chunks = [next(it) for _ in range(3)]
        assert all(b"--frame" in ch and b"\xff\xd8" in ch for ch in chunks) and chunks[0] == chunks[2]
        r.close()


def test_state_reports_reacquired_lock_through_pipeline():
    c, pipe, det, _ = build()
    now = [10.0]
    pipe.lock._clock = lambda: now[0]
    c.post("/api/lock", json={"track_id": 7})
    fr = lambda i: Frame(np.zeros((480, 640, 3), np.uint8), 0.0, i)
    det.tracks = []                       # ID 7 biến mất
    now[0] += 0.1
    pipe.process_frame(fr(1))
    L = c.get("/api/state").get_json()["lock"]
    assert L["active"] and L["visible"] is False and L["state"] == "searching" and L["reacquired"] == 0
    det.tracks = [Track(20, (301.0, 201.0, 341.0, 231.0), 0.7)]  # ID mới ngay vị trí cũ
    now[0] += 0.1
    pipe.process_frame(fr(2))
    L = c.get("/api/state").get_json()["lock"]
    assert L["track_id"] == 20 and L["visible"] and L["state"] == "reacquired" and L["reacquired"] == 1
    assert c.get("/snapshot.jpg").data[:2] == b"\xff\xd8"


def test_trusted_ip_over_ip_limit_cannot_bruteforce():
    c, *_ = build(password=PW, allow_network=True)
    now = [1000.0]
    c.application.extensions["labview.limiter"].clock = lambda: now[0]
    assert get(c, auth()).status_code == 200            # đăng nhập đúng một lần -> IP tin cậy
    for _ in range(5):
        assert get(c, auth("typo-typo-typo")).status_code == 401
    codes = [get(c, auth("guess-%03d-xxxxx" % i)).status_code for i in range(299)]
    codes.append(get(c, auth()).status_code)            # lần cuối là mật khẩu ĐÚNG
    assert codes == [429] * 300                         # 0 lần 200 trong thời gian chặn
    now[0] += 61
    assert get(c, auth()).status_code == 200            # hết chặn: đúng thì vào


# ---------------- (B1) HEAD và ngoại lệ không làm rò chỗ
def test_head_stream_does_not_take_slots():
    c, pipe, *_ = build(max_stream_clients=2)
    pipe._done = True
    for _ in range(10):
        r = c.head("/stream.mjpg")
        assert r.status_code == 200
    assert c.get("/stream.mjpg").status_code == 200


def test_stream_slot_released_on_exception_in_generator(monkeypatch):
    c, pipe, *_ = build(max_stream_clients=1)
    def boom(*a, **k): raise RuntimeError("loi giua chung")
    real = pipe.wait_frame
    monkeypatch.setattr(pipe, "wait_frame", boom)
    for _ in range(3):
        with pytest.raises(Exception):
            c.get("/stream.mjpg")
    monkeypatch.setattr(pipe, "wait_frame", real)
    pipe._done = True
    assert c.get("/stream.mjpg").status_code == 200


def test_warn_for_explicit_all_interfaces_host(monkeypatch, capsys):
    from labview.__main__ import parse
    monkeypatch.setenv("LABVIEW_PASSWORD", PW)
    parse(["--source", "file:x", "--allow-network", "--host", "0.0.0.0"])
    err = capsys.readouterr().err
    assert "403" in err and "--allowed-host" in err
