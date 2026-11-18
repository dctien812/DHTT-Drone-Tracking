"""Cấu hình và kiểm tra an toàn khi khởi động."""
from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = str(REPO / "vision" / "weights" / "ft_v8n_best.pt")
MIN_PASSWORD_LEN = 12
PASSWORD_ENV = "LABVIEW_PASSWORD"


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    source: str = "file:"
    weights: str = DEFAULT_WEIGHTS
    imgsz: int = 640
    conf: float = 0.25
    tracker: str = "bytetrack.yaml"
    threads: int = 4
    max_width: int = 960            # thu nhỏ khung rộng hơn mức này (0 = giữ nguyên)
    hfov_deg: float = 66.0          # FOV ngang; Camera Module 3 Wide ~102 độ (xem README)
    fx: Optional[float] = None
    fy: Optional[float] = None
    cx: Optional[float] = None
    cy: Optional[float] = None
    real_width_m: float = 0.30
    lost_timeout_s: float = 2.0
    reacquire: bool = True          # tự gán lại khóa cho track mới khi ID đang khóa biến mất
    reacq_gate: float = 1.0         # cổng khoảng cách cơ bản, tính theo cạnh lớn của khung bao cuối
    reacq_gate_per_s: float = 1.5   # cổng nở thêm bấy nhiêu "cạnh khung bao" cho mỗi giây mất dấu
    reacq_size_min: float = 0.5     # tỉ lệ bề rộng (mới / cuối) tối thiểu
    reacq_size_max: float = 2.0     # tỉ lệ bề rộng (mới / cuối) tối đa
    reacq_min_conf: Optional[float] = None  # conf tối thiểu của ứng viên; None = bằng --conf (ngưỡng hiển thị)
    click_margin_px: float = 12.0
    loop: bool = True
    pace: bool = True
    jpeg_quality: int = 80
    cam_width: int = 1280
    cam_height: int = 720
    cam_fps: int = 30
    cam_focus: str = "infinity"     # picamera2: infinity | continuous | manual
    cam_lens_position: Optional[float] = None   # diop, chi dung khi cam_focus = manual
    host: Optional[str] = None
    port: int = 8080
    allow_network: bool = False
    password: Optional[str] = field(default=None, repr=False)
    max_stream_clients: int = 4
    allowed_hosts: list = field(default_factory=list)  # tiêu đề Host cho phép ở chế độ mạng (thêm vào mặc định)
    log_file: Optional[str] = None


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_password(password_file: Optional[str]) -> Optional[str]:
    """Mật khẩu chỉ lấy từ file (do người vận hành chỉ định, nên đặt ngoài git) hoặc biến môi trường."""
    if password_file:
        p = Path(password_file).expanduser()
        if not p.is_file():
            raise ConfigError("Khong doc duoc file mat khau")
        if os.name == "posix" and (p.stat().st_mode & 0o077):
            raise ConfigError("File mat khau nhom/nguoi khac doc duoc: chay chmod 600 <file>")
        pw = p.read_text(encoding="utf-8").strip()
        return pw or None
    return os.environ.get(PASSWORD_ENV) or None


def validate(cfg: Config) -> Config:
    """Chuẩn hóa host và áp quy tắc bảo mật; ném ConfigError nếu vi phạm."""
    if cfg.host is None:
        cfg.host = "0.0.0.0" if cfg.allow_network else "127.0.0.1"
    if not cfg.allow_network and not is_loopback(cfg.host):
        raise ConfigError("Nghe ngoai 127.0.0.1 phai bat co --allow-network (va dat mat khau)")
    if cfg.allow_network:
        if not cfg.password:
            raise ConfigError(f"Che do mang can mat khau: dat bien moi truong {PASSWORD_ENV} hoac dung --password-file")
        if len(cfg.password) < MIN_PASSWORD_LEN:
            raise ConfigError(f"Mat khau toi thieu {MIN_PASSWORD_LEN} ky tu")
        hosts = {h.strip().lower() for h in cfg.allowed_hosts if h and h.strip()}
        hosts |= {"localhost", socket.gethostname().lower()}
        if cfg.host not in ("0.0.0.0", "::"):  # địa chỉ "nghe mọi giao diện" không phải tên mà khách gõ
            hosts.add(cfg.host.lower())
        cfg.allowed_hosts = sorted(hosts)
    if not (1 <= cfg.port <= 65535):
        raise ConfigError("port khong hop le")
    if not (0.0 <= cfg.conf <= 1.0):
        raise ConfigError("conf phai trong [0,1]")
    if cfg.real_width_m <= 0 or cfg.lost_timeout_s <= 0:
        raise ConfigError("real_width_m va lost_timeout_s phai > 0")
    if cfg.reacq_gate <= 0 or cfg.reacq_gate_per_s < 0 or not (0 < cfg.reacq_size_min <= 1.0 <= cfg.reacq_size_max):
        raise ConfigError("reacq: gate > 0, gate_per_s >= 0, 0 < size_min <= 1 <= size_max")
    if not (1 <= cfg.jpeg_quality <= 100):
        raise ConfigError("jpeg_quality phai trong [1,100]")
    cfg.threads = max(1, min(cfg.threads, 8))
    return cfg
