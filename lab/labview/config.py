"""Cấu hình và kiểm tra an toàn khi khởi động."""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = str(REPO / "vision" / "weights" / "ft_v8n_best.pt")
MIN_PASSWORD_LEN = 8
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
    click_margin_px: float = 12.0
    loop: bool = True
    pace: bool = True
    jpeg_quality: int = 80
    cam_width: int = 1280
    cam_height: int = 720
    cam_fps: int = 30
    host: Optional[str] = None
    port: int = 8080
    allow_network: bool = False
    password: Optional[str] = field(default=None, repr=False)
    max_stream_clients: int = 4
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
    if not (1 <= cfg.port <= 65535):
        raise ConfigError("port khong hop le")
    if not (0.0 <= cfg.conf <= 1.0):
        raise ConfigError("conf phai trong [0,1]")
    if cfg.real_width_m <= 0 or cfg.lost_timeout_s <= 0:
        raise ConfigError("real_width_m va lost_timeout_s phai > 0")
    if not (1 <= cfg.jpeg_quality <= 100):
        raise ConfigError("jpeg_quality phai trong [1,100]")
    cfg.threads = max(1, min(cfg.threads, 8))
    return cfg
