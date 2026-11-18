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
_FAIL_LIMIT, _FAIL_WINDOW = 5, 60.0          # theo từng IP
_GLOBAL_FAIL_LIMIT, _GLOBAL_BLOCK_S = 20, 60.0  # tổng cho cả máy chủ: 20 lần sai/phút -> khóa 60 s
_TRUST_TTL, _TRUST_MAX = 3600.0, 64          # IP đã đăng nhập đúng gần đây (chủ máy) vẫn vào được khi đang khóa
_STREAM_RESEND_S = 2.0                       # không có khung mới: gửi lại khung cuối chu kỳ này


class _FailLimiter:
    """Giới hạn đoán mật khẩu: theo từng IP và TỔNG cho cả máy chủ (chống đổi IP).
    Hạn mức theo IP áp dụng cho MỌI IP kể cả tin cậy (đang bị chặn thì mọi lần thử, kể cả đúng, nhận 429; mọi lần
    sai đều được đếm). Khi đang khóa TOÀN CỤC chỉ IP "tin cậy" (đã nhập ĐÚNG gần đây) mới được vào bằng mật khẩu đúng; IP lạ
    luôn nhận 429 dù đúng hay sai, để 429 không thành "máy dò" mật khẩu (nếu cho mọi mật khẩu đúng qua
    thì kẻ dò cứ thử tiếp: sai nhận 429, đúng nhận 200, giới hạn thành vô nghĩa)."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._mu = threading.Lock()
        self._fails: dict[str, list[float]] = {}
        self._all: list[float] = []
        self._global_until = 0.0
        self._trusted: dict[str, float] = {}

    def ip_blocked(self, ip: str) -> bool:
        with self._mu:
            return self._ip_until(ip) > self.clock()

    def global_blocked(self) -> bool:
        with self._mu:
            return self.clock() < self._global_until

    def retry_after(self, ip: str) -> int:
        with self._mu:
            return max(1, int(max(self._ip_until(ip), self._global_until) - self.clock() + 0.999))

    def _ip_until(self, ip: str) -> float:  # gọi khi đang giữ khóa; thời điểm hết chặn theo IP (<= now: không chặn)
        now = self.clock()
        lst = [t for t in self._fails.get(ip, []) if now - t < _FAIL_WINDOW]
        if lst:
            self._fails[ip] = lst
        else:
            self._fails.pop(ip, None)
        return lst[-_FAIL_LIMIT] + _FAIL_WINDOW if len(lst) >= _FAIL_LIMIT else 0.0

    def add(self, ip: str) -> None:
        with self._mu:
            now = self.clock()
            self._fails[ip] = [t for t in self._fails.get(ip, []) if now - t < _FAIL_WINDOW] + [now]
            self._all = [t for t in self._all if now - t < _FAIL_WINDOW] + [now]
            if len(self._all) >= _GLOBAL_FAIL_LIMIT:
                self._global_until, self._all = now + _GLOBAL_BLOCK_S, []

    def trust(self, ip: str) -> None:
        with self._mu:
            now = self.clock()
            self._trusted[ip] = now
            if len(self._trusted) > _TRUST_MAX:
                self._trusted = {k: v for k, v in self._trusted.items() if now - v < _TRUST_TTL}
                while len(self._trusted) > _TRUST_MAX:
                    self._trusted.pop(min(self._trusted, key=self._trusted.get))

    def is_trusted(self, ip: str) -> bool:
        with self._mu:
            t = self._trusted.get(ip)
            return t is not None and self.clock() - t < _TRUST_TTL


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
    app.extensions["labview.limiter"] = limiter
    loopback_only = not cfg.allow_network and is_loopback(cfg.host or "127.0.0.1")
    allowed_hosts = {h.lower() for h in cfg.allowed_hosts}

    def _deny(code, msg, headers=None):
        r = jsonify(error=msg)
        r.status_code = code
        for k, v in (headers or {}).items():
            r.headers[k] = v
        return r

    @app.before_request
    def _guard():
        ip = request.remote_addr or "?"
        # chống DNS rebinding: chỉ nghe localhost -> Host phải là localhost; chế độ mạng -> Host phải thuộc danh sách cho phép
        try:
            host = (urlsplit("//" + request.host).hostname or "").lower()
        except ValueError:
            host = ""
        if host not in (("localhost", "127.0.0.1", "::1") if loopback_only else allowed_hosts):
            return _deny(403, "host khong hop le")
        if require_auth:
            ip_b, glob_b = limiter.ip_blocked(ip), limiter.global_blocked()
            ok = False
            h = request.headers.get("Authorization", "")
            if h.startswith("Basic "):
                try:
                    user, _, pw = b64decode(h[6:], validate=True).decode("utf-8").partition(":")
                    ok = (hmac.compare_digest(user.encode(), AUTH_USER.encode())
                          & hmac.compare_digest(pw.encode(), password))
                except Exception:
                    ok = False
            if h and not ok:
                limiter.add(ip)  # mọi lần sai đều được đếm, kể cả khi đang bị chặn
            if ip_b or (glob_b and not (ok and limiter.is_trusted(ip))):
                return _deny(429, "thu lai sau", {"Retry-After": str(limiter.retry_after(ip))})
            if not ok:
                return _deny(401, "can xac thuc", {"WWW-Authenticate": 'Basic realm="labview", charset="UTF-8"'})
            if not glob_b:
                limiter.trust(ip)
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
        if request.method == "HEAD":  # chỉ trả tiêu đề, không chiếm chỗ (generator không bao giờ được lặp)
            return Response(mimetype="multipart/x-mixed-replace; boundary=frame")
        with clients_mu:
            if clients["n"] >= cfg.max_stream_clients:
                return _deny(503, "qua nhieu nguoi xem")
            clients["n"] += 1
        freed = []

        def release():  # idempotent: gọi từ generator và từ call_on_close (generator chưa chạy thì chỉ có cái sau)
            with clients_mu:
                if not freed:
                    freed.append(1)
                    clients["n"] -= 1

        def gen():
            seq, last = -1, None
            try:
                while not pipe.stopping:
                    seq2, jpg = pipe.wait_frame(seq, timeout=_STREAM_RESEND_S)
                    seq = seq2
                    if jpg is not None and jpg is not last:
                        last = jpg
                    elif pipe.done:  # nguồn đã kết thúc và khung cuối đã gửi: đóng luồng, trả chỗ
                        break
                    elif last is None:
                        continue
                    # không có khung mới thì gửi lại khung cuối: ghi vào ổ cắm hỏng sẽ ném lỗi, nhờ đó phát hiện người xem đã ngắt
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(last)).encode() + b"\r\n\r\n" + last + b"\r\n")
            finally:
                release()

        resp = Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
        resp.call_on_close(release)
        return resp

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
