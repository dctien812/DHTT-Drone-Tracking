"""Giao diện nguồn hình (FrameSource) và các cài đặt.

Thêm nguồn mới (vd. picamera2 trên Pi 5): viết lớp con FrameSource rồi đăng ký trong
`make_source`; lõi (pipeline/máy chủ) không cần sửa.
"""
from __future__ import annotations

import abc
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class Frame:
    image: np.ndarray   # BGR
    ts: float           # time.monotonic() lúc đọc xong khung
    index: int


class FrameSource(abc.ABC):
    name: str = "source"
    kind: str = "unknown"
    live: bool = False       # True: camera (không có "hết video")
    fps: float = 0.0

    @abc.abstractmethod
    def open(self) -> None: ...

    @abc.abstractmethod
    def read(self) -> Optional[Frame]:
        """Khung kế tiếp; None khi hết nguồn (file) hoặc lỗi."""

    def close(self) -> None:
        pass

    def restart(self) -> bool:
        """Chạy lại từ đầu (chỉ file). Trả False nếu không hỗ trợ."""
        return False


class VideoFileSource(FrameSource):
    """Đọc file video, phát theo tốc độ thật (pace=True) để giống camera: suy luận chậm
    thì pipeline bỏ khung cũ thay vì phát chậm."""

    kind = "file"

    def __init__(self, path: str, pace: bool = True):
        self.path, self.pace = path, pace
        self.name = path.replace("\\", "/").rsplit("/", 1)[-1]
        self._cap: Optional[cv2.VideoCapture] = None
        self._idx = 0
        self._t0 = 0.0

    def open(self) -> None:
        self._cap = cv2.VideoCapture(self.path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Khong mo duoc video: {self.name}")
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 30.0
        self._idx, self._t0 = 0, time.monotonic()

    def read(self) -> Optional[Frame]:
        if self._cap is None:
            return None
        if self.pace:
            due = self._t0 + self._idx / self.fps
            delay = due - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        ok, img = self._cap.read()
        if not ok:
            return None
        self._idx += 1
        return Frame(img, time.monotonic(), self._idx - 1)

    def restart(self) -> bool:
        if self._cap is None:
            return False
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._idx, self._t0 = 0, time.monotonic()
        return True

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class OpenCVCameraSource(FrameSource):
    """Webcam / V4L2 (kiểu mở theo AI-6 video_processor._open_camera: V4L2, MJPG, buffer 1,
    grab() rồi retrieve() để luôn lấy khung mới nhất)."""

    kind = "camera"
    live = True

    def __init__(self, device: str = "0", width: int = 1280, height: int = 720, fps: int = 30):
        self.device, self.w, self.h, self.req_fps = device, width, height, fps
        self.name = f"camera:{device}"
        self._cap: Optional[cv2.VideoCapture] = None
        self._idx = 0

    def open(self) -> None:
        dev = self.device
        if dev.startswith("/dev/"):
            cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
        elif dev.isdigit():
            cap = cv2.VideoCapture(int(dev), cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") and _is_linux() else cv2.CAP_ANY)
        else:
            raise ValueError("camera phai la chi so (0) hoac /dev/videoN")
        if not cap.isOpened():
            raise RuntimeError(f"Khong mo duoc camera {dev}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        cap.set(cv2.CAP_PROP_FPS, self.req_fps)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.fps = cap.get(cv2.CAP_PROP_FPS) or float(self.req_fps)
        self._cap = cap

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.grab():
            return None
        ok, img = self._cap.retrieve()
        if not ok:
            return None
        self._idx += 1
        return Frame(img, time.monotonic(), self._idx - 1)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def _is_linux() -> bool:
    import sys
    return sys.platform.startswith("linux")


def make_source(spec: str, *, pace: bool = True, width: int = 1280, height: int = 720, fps: int = 30,
                focus: str = "infinity", lens_position: Optional[float] = None, buffers: int = 4) -> FrameSource:
    """spec: 'file:<duong_dan>' | 'camera:<chi_so|/dev/videoN>' | 'picamera2'."""
    kind, _, arg = spec.partition(":")
    if kind == "file" and arg:
        return VideoFileSource(arg, pace=pace)
    if kind == "camera":
        return OpenCVCameraSource(arg or "0", width, height, fps)
    if kind == "picamera2":
        from .picam import Picamera2Source   # import muon: tranh vong import, picamera2 chi nap khi open()
        return Picamera2Source(width, height, fps, focus, lens_position, buffers=buffers)
    raise ValueError("--source phai la file:<duong_dan>, camera:<chi_so> hoac picamera2")
