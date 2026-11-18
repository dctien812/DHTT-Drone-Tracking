"""Nguồn hình Raspberry Pi Camera (picamera2/libcamera), chọn bằng --source picamera2.

`picamera2` chỉ import trong open() (import muộn) để chương trình vẫn chạy trên PC không có thư viện.
Trên Pi: gói hệ thống `python3-picamera2`, venv tạo với --system-site-packages (xem README).
CHƯA thử trên phần cứng: các giả định về API ghi ở README.

Một luồng "grabber" gọi capture_array liên tục; read() chỉ chờ khung mới có hết giờ. Nhờ vậy: lỗi nhất thời được
thử lại, camera đứng hình thì read() trả None sau `frame_timeout_s` (pipeline báo "mất nguồn hình"), và close()
không phụ thuộc capture_array đang chặn hay không.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from .sources import Frame, FrameSource

log = logging.getLogger("labview")

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
    """Camera Pi qua picamera2. Trả khung BGR. Luôn lấy khung mới nhất: queue=False, vài bộ đệm,
    read() trả khung mới nhất chưa đọc (khung cũ bị bỏ)."""

    kind = "camera"
    live = True
    max_retries = 3            # số lần thử lại liên tiếp với lỗi nhất thời trước khi coi là mất nguồn
    retry_delay_s = 0.1        # chờ retry_delay_s * (số lần lỗi liên tiếp) giữa các lần thử
    teardown_timeout_s = 3.0   # tối đa chờ cam.stop()/close()
    fps_window = 30            # số khung để đo fps thực

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30,
                 focus: str = "infinity", lens_position: Optional[float] = None, camera_num: int = 0,
                 buffers: int = 4, frame_timeout_s: float = 5.0):
        self.w, self.h, self.req_fps, self.camera_num = width, height, fps, camera_num
        self.controls = focus_controls(focus, lens_position)   # kiểm tham số ngay khi tạo
        if not (2 <= buffers <= 16):
            raise ValueError("--cam-buffers phai trong [2,16]")
        if focus != "manual" and lens_position is not None:
            log.warning("--lens-position %s bi bo qua vi --focus la %s (chi dung voi --focus manual)", lens_position, focus)
        self.buffers, self.frame_timeout_s = buffers, frame_timeout_s
        self.name = f"picamera2:{camera_num}"
        self._cam = None
        self._started = False
        self._idx = 0
        self._lock = threading.Lock()          # bảo vệ _cam/_started/_thread khi open/close
        self._cv = threading.Condition()       # khung mới nhất giữa grabber và read()
        self._closing = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest = None
        self._seq = self._seen = 0
        self._failed = False

    def open(self) -> None:
        try:
            from picamera2 import Picamera2
        except ImportError as e:
            raise RuntimeError(
                "Khong co thu vien picamera2. Tren Raspberry Pi OS: sudo apt install python3-picamera2, "
                "va tao venv voi --system-site-packages (khong cai bang pip). Tren PC dung --source file:/camera:") from e
        cam = None
        self._closing.clear()
        self._failed, self._latest, self._seq, self._seen = False, None, 0, 0
        try:
            if not Picamera2.global_camera_info():
                raise RuntimeError("khong thay camera nao")
            cam = Picamera2(self.camera_num)
            # "RGB888" cua picamera2 co thu tu byte trong bo nho la B,G,R = dung thu tu cua OpenCV.
            cfg = cam.create_video_configuration(
                main={"size": (self.w, self.h), "format": "RGB888"},
                buffer_count=self.buffers, queue=False,
                controls=dict(self.controls, FrameRate=float(self.req_fps)))
            cam.configure(cfg)
            self._log_actual_config(cam)
            cam.start()
            with self._lock:
                self._cam, self._started = cam, True
        except Exception as e:
            if cam is not None:
                with self._lock:
                    self._cam = cam
                self.close()
            raise RuntimeError(
                f"Khong mo duoc Pi camera ({e}). Kiem tra cap CSI, camera da duoc nhan (rpicam-hello --list-cameras), "
                "va khong co chuong trinh khac dang dung camera") from e
        self.fps = float(self.req_fps)   # tam thoi = yeu cau; grabber do lai fps thuc sau fps_window khung
        self._thread = threading.Thread(target=self._grab_loop, args=(cam,), name="labview-picam", daemon=True)
        self._thread.start()

    def _log_actual_config(self, cam) -> None:
        """Doc cau hinh THUC sau configure (GIA DINH: cam.camera_configuration()["main"]["size"] cua picamera2).
        Khong doc duoc thi bo qua: kich thuoc cung duoc kiem lai tren khung dau tien."""
        try:
            size = tuple(int(v) for v in cam.camera_configuration()["main"]["size"])
        except Exception as e:
            log.debug("Khong doc duoc camera_configuration (%s: %s)", type(e).__name__, e)
            return
        if size != (self.w, self.h):
            log.warning("Camera cau hinh %dx%d khac yeu cau %dx%d: dung kich thuoc thuc", *size, self.w, self.h)
            self.w, self.h = size

    # ------------------------------------------------------------ luồng grabber
    def _grab_loop(self, cam) -> None:
        errors, n, t0, size_ok = 0, 0, 0.0, False
        while not self._closing.is_set():
            try:
                img = cam.capture_array("main")
            except Exception as e:
                if self._closing.is_set():
                    return
                errors += 1
                log.warning("capture_array loi (%d/%d lien tiep): %s: %s", errors, self.max_retries, type(e).__name__, e,
                            exc_info=errors == 1)
                if errors > self.max_retries:
                    log.error("Camera loi lien tuc: coi la mat nguon hinh")
                    with self._cv:
                        self._failed = True
                        self._cv.notify_all()
                    return
                self._closing.wait(self.retry_delay_s * errors)
                continue
            errors = 0
            now = time.monotonic()
            if not size_ok:
                size_ok = True
                h, w = img.shape[:2]
                if (w, h) != (self.w, self.h):
                    log.warning("Khung that %dx%d khac yeu cau %dx%d: dung kich thuoc thuc", w, h, self.w, self.h)
                    self.w, self.h = w, h
            n += 1
            if n == 1:
                t0 = now
            elif n == self.fps_window:
                measured = (n - 1) / max(now - t0, 1e-6)
                self.fps = measured
                (log.warning if abs(measured - self.req_fps) > 0.15 * self.req_fps else log.info)(
                    "fps thuc do duoc %.1f (yeu cau %d)", measured, self.req_fps)
            with self._cv:
                self._latest = (img, now)
                self._seq += 1
                self._cv.notify_all()

    def read(self) -> Optional[Frame]:
        """Khung mới nhất chưa đọc. None khi đã đóng, grabber báo lỗi liên tục, hoặc quá frame_timeout_s không có khung."""
        if self._thread is None:
            return None
        deadline = time.monotonic() + self.frame_timeout_s
        with self._cv:
            while self._seq == self._seen and not self._failed and not self._closing.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    log.error("Khong co khung nao trong %.1f s: coi la mat nguon hinh", self.frame_timeout_s)
                    return None
                self._cv.wait(remaining)
            if self._seq == self._seen:
                return None
            img, ts = self._latest
            self._seen = self._seq
        self._idx += 1
        return Frame(img, ts, self._idx - 1)

    def close(self) -> None:
        """An toan khi capture_array dang chan: khong cho vo han, khong dung _cam tu luong khac."""
        self._closing.set()
        with self._cv:
            self._cv.notify_all()
        with self._lock:
            cam, self._cam = self._cam, None
            started, self._started = self._started, False
            th, self._thread = self._thread, None
        if th is not None and th is not threading.current_thread():
            th.join(timeout=1.0)   # grabber ket trong capture_array thi bo qua, la luong daemon
        if cam is None:
            return

        def teardown():
            for fn in ((cam.stop,) if started else ()) + (cam.close,):
                try:
                    fn()
                except Exception:
                    log.exception("Loi khi dong camera (%s)", getattr(fn, "__name__", fn))

        t = threading.Thread(target=teardown, name="labview-picam-close", daemon=True)
        t.start()
        t.join(timeout=self.teardown_timeout_s)
        if t.is_alive():
            log.error("cam.stop()/close() khong xong sau %.1f s: bo qua, tiep tuc thoat", self.teardown_timeout_s)
