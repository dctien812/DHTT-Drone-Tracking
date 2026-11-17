"""Máy chủ web (Flask): trang điều khiển, luồng MJPEG, trạng thái JSON, khóa/hủy.

Bảo mật: chỉ phục vụ file tĩnh cố định nạp sẵn từ gói (không đọc file theo đường dẫn
người dùng); không điểm cuối nào chạy lệnh hệ thống; POST bắt buộc JSON + kiểm Origin +
xác thực; có mật khẩu thì mọi điểm cuối (kể cả GET) đều đòi xác thực HTTP Basic.
"""
from __future__ import annotations

import hmac
import math
import threading
import time
from base64 import b64decode
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, Response, abort, jsonify, request

from .config import Config, is_loopback
from .pipeline import Pipeline

STATIC_DIR = Path(__file__).parent / "static"
_ASSETS = {  # đường dẫn cố định -> (tên file, content-type)
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
}
CSP = ("default-src 'none'; img-src 'self'; script-src 'self'; style-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
AUTH_USER = "lab"
_FAIL_LIMIT, _FAIL_WINDOW = 5, 60.0


class _FailLimiter:
    def __init__(self):
        self._mu = threading.Lock()
        self._fails: dict[str, list[float]] = {}

    def blocked(self, ip: str) -> bool:
        with self._mu:
            now = time.monotonic()
            lst = [t for t in self._fails.get(ip, []) if now - t < _FAIL_WINDOW]
            self._fails[ip] = lst
            return len(lst) >= _FAIL_LIMIT

    def add(self, ip: str) -> None:
        with self._mu:
            self._fails.setdefault(ip, []).append(time.monotonic())


def _num(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not (lo <= v <= hi):
        return None
    return float(v)


def create_app(pipe: Pipeline, cfg: Config) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 2048
    assets = {p: ((STATIC_DIR / f).read_bytes(), ct) for p, (f, ct) in _ASSETS.items()}
    password = (cfg.password or "").encode("utf-8") or None
    require_auth = password is not None
    limiter = _FailLimiter()
    clients = {"n": 0}
    clients_mu = threading.Lock()
    loopback_only = not cfg.allow_network and is_loopback(cfg.host or "127.0.0.1")

    def _deny(code, msg, headers=None):
        r = jsonify(error=msg)
        r.status_code = code
        for k, v in (headers or {}).items():
            r.headers[k] = v
        return r

    @app.before_request
    def _guard():
        ip = request.remote_addr or "?"
        if loopback_only:  # chống DNS rebinding khi chỉ nghe localhost
            host = urlsplit("//" + request.host).hostname
            if host not in ("localhost", "127.0.0.1", "::1"):
                return _deny(403, "host khong hop le")
        if require_auth:
            if limiter.blocked(ip):
                return _deny(429, "thu lai sau", {"Retry-After": "60"})
            ok = False
            h = request.headers.get("Authorization", "")
            if h.startswith("Basic "):
                try:
                    user, _, pw = b64decode(h[6:], validate=True).decode("utf-8").partition(":")
                    ok = (hmac.compare_digest(user.encode(), AUTH_USER.encode())
                          & hmac.compare_digest(pw.encode(), password))
                except Exception:
                    ok = False
            if not ok:
                if h:
                    limiter.add(ip)
                return _deny(401, "can xac thuc", {"WWW-Authenticate": 'Basic realm="labview", charset="UTF-8"'})
        if request.method == "POST":
            if request.mimetype != "application/json":
                return _deny(415, "can Content-Type application/json")
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc != request.host:
                return _deny(403, "origin khong hop le")
        elif request.method not in ("GET", "HEAD"):
            return _deny(405, "method khong ho tro")
        return None

    @app.after_request
    def _headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def _asset(path):
        body, ct = assets[path]
        return Response(body, mimetype=ct.split(";")[0], headers={"Content-Type": ct})

    for p in assets:
        app.add_url_rule(p, endpoint="asset" + p.replace("/", "_"), view_func=(lambda p=p: _asset(p)))

    @app.get("/api/state")
    def api_state():
        _, state, _ = pipe.snapshot()
        return jsonify(state)

    @app.get("/snapshot.jpg")
    def snapshot():
        _, _, jpg = pipe.snapshot()
        if jpg is None:
            abort(503)
        return Response(jpg, mimetype="image/jpeg")

    @app.get("/stream.mjpg")
    def stream():
        with clients_mu:
            if clients["n"] >= cfg.max_stream_clients:
                return _deny(503, "qua nhieu nguoi xem")
            clients["n"] += 1

        def gen():
            seq = -1
            try:
                while not pipe.stopping:
                    seq2, jpg = pipe.wait_frame(seq, timeout=2.0)
                    if seq2 == seq or jpg is None:
                        continue
                    seq = seq2
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            finally:
                with clients_mu:
                    clients["n"] -= 1

        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.post("/api/lock")
    def api_lock():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _deny(400, "body phai la JSON object")
        keys = set(data)
        if keys == {"x", "y"}:
            x, y = _num(data["x"], 0.0, 1.0), _num(data["y"], 0.0, 1.0)
            if x is None or y is None:
                return _deny(400, "x,y phai la so trong [0,1]")
            tid = pipe.lock_at_norm(x, y)
            if tid is None:
                return jsonify(ok=False, reason="khong co khung nao tai diem bam"), 200
            return jsonify(ok=True, track_id=tid)
        if keys == {"track_id"}:
            t = data["track_id"]
            if isinstance(t, bool) or not isinstance(t, int) or not (0 <= t < 2**31):
                return _deny(400, "track_id phai la so nguyen khong am")
            if not pipe.lock_track_id(t):
                return jsonify(ok=False, reason="track_id khong ton tai"), 200
            return jsonify(ok=True, track_id=t)
        if keys == {"best"} and data["best"] is True:
            tid = pipe.lock_best()
            if tid is None:
                return jsonify(ok=False, reason="chua co vat the nao"), 200
            return jsonify(ok=True, track_id=tid)
        return _deny(400, "can dung mot trong: {x,y} | {track_id} | {best:true}")

    @app.post("/api/release")
    def api_release():
        data = request.get_json(silent=True)
        if data not in ({}, None) and not isinstance(data, dict):
            return _deny(400, "body khong hop le")
        return jsonify(ok=True, released=pipe.release())

    return app
