"""Nguồn hình Raspberry Pi Camera (picamera2/libcamera), chọn bằng --source picamera2.

`picamera2` chỉ import trong open() (import muộn) để chương trình vẫn chạy trên PC không có thư viện.
Trên Pi: gói hệ thống `python3-picamera2`, venv tạo với --system-site-packages (xem README).
CHƯA thử trên phần cứng: các giả định về API ghi ở README.
"""
from __future__ import annotations

import time
from typing import Optional

from .sources import Frame, FrameSource

FOCUS_MODES = ("infinity", "continuous", "manual")
# Giá trị AfMode của libcamera (controls.AfModeEnum): Manual=0, Auto=1, Continuous=2.
AF_MANUAL, AF_CONTINUOUS = 0, 2


def focus_controls(focus: str, lens_position: Optional[float]) -> dict:
    """Điều khiển lấy nét gửi cho libcamera. LensPosition tính bằng diop (0 = vô cực, 1/khoảng cách m)."""
    if focus == "infinity":
        return {"AfMode": AF_MANUAL, "LensPosition": 0.0}
    if focus == "continuous":
        return {"AfMode": AF_CONTINUOUS}
    if focus == "manual":
        if lens_position is None or lens_position < 0:
            raise ValueError("--focus manual can --lens-position >= 0 (diop; 0 = vo cuc)")
        return {"AfMode": AF_MANUAL, "LensPosition": float(lens_position)}
    raise ValueError(f"--focus phai la mot trong {', '.join(FOCUS_MODES)}")


class Picamera2Source(FrameSource):
    """Camera Pi qua picamera2. Trả khung BGR. Luôn lấy khung mới nhất: queue=False và ít bộ đệm
    (capture_array chờ khung kế tiếp, không giữ hàng đợi khung cũ)."""

    kind = "camera"
    live = True

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30,
                 focus: str = "infinity", lens_position: Optional[float] = None, camera_num: int = 0):
        self.w, self.h, self.req_fps, self.camera_num = width, height, fps, camera_num
        self.controls = focus_controls(focus, lens_position)   # kiểm tham số ngay khi tạo
        self.name = f"picamera2:{camera_num}"
        self._cam = None
        self._started = False
        self._idx = 0

    def open(self) -> None:
        try:
            from picamera2 import Picamera2
        except ImportError as e:
            raise RuntimeError(
                "Khong co thu vien picamera2. Tren Raspberry Pi OS: sudo apt install python3-picamera2, "
                "va tao venv voi --system-site-packages (khong cai bang pip). Tren PC dung --source file:/camera:") from e
        cam = None
        try:
            if not Picamera2.global_camera_info():
                raise RuntimeError("khong thay camera nao")
            cam = Picamera2(self.camera_num)
            # "RGB888" cua picamera2 co thu tu byte trong bo nho la B,G,R = dung thu tu cua OpenCV.
            cfg = cam.create_video_configuration(
                main={"size": (self.w, self.h), "format": "RGB888"},
                buffer_count=2, queue=False,
                controls=dict(self.controls, FrameRate=float(self.req_fps)))
            cam.configure(cfg)
            cam.start()
            self._cam, self._started = cam, True
        except Exception as e:
            if cam is not None:
                self._cam = cam
                self.close()
            raise RuntimeError(
                f"Khong mo duoc Pi camera ({e}). Kiem tra cap CSI, camera da duoc nhan (rpicam-hello --list-cameras), "
                "va khong co chuong trinh khac dang dung camera") from e
        self.fps = float(self.req_fps)

    def read(self) -> Optional[Frame]:
        if self._cam is None:
            return None
        try:
            img = self._cam.capture_array("main")
        except Exception:
            return None
        self._idx += 1
        return Frame(img, time.monotonic(), self._idx - 1)

    def close(self) -> None:
        cam, self._cam = self._cam, None
        if cam is None:
            return
        for fn in ((cam.stop,) if self._started else ()) + (cam.close,):
            try:
                fn()
            except Exception:
                pass
        self._started = False
