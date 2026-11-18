"""Pipeline hai luồng: đọc hình (thread 1) -> suy luận + khóa + vẽ + mã hóa JPEG (thread 2).

Ý tưởng lấy từ AI-6/YOLOv8/video_processor.py: camera và suy luận chạy độc lập, giữa hai
luồng chỉ có "khung mới nhất" (không xếp hàng) để độ trễ thấp; khung cũ bị bỏ khi suy luận chậm.
Luồng thứ ba (HTTP) chỉ đọc kết quả đã công bố qua Pipeline.snapshot()/wait_frame().
"""
from __future__ import annotations

import collections
import datetime as dt
import logging
import threading
import time
from typing import Optional, Sequence

import cv2
import numpy as np

from . import geometry, overlay
from .config import Config
from .detector import Detector
from .lock import LockManager, LockStatus, ReacquireParams, Track
from .outputs import LockReport, LockSink
from .sources import Frame, FrameSource

log = logging.getLogger("labview")

try:  # tùy chọn
    import psutil
except Exception:  # pragma: no cover
    psutil = None


class Pipeline:
    def __init__(self, source: FrameSource, detector: Detector, cfg: Config,
                 sinks: Sequence[LockSink] = ()):
        self.source, self.detector, self.cfg = source, detector, cfg
        self.sinks = list(sinks)
        self.events: collections.deque = collections.deque(maxlen=30)
        self.lock = LockManager(cfg.lost_timeout_s, on_event=self._on_event,
                                reacquire=ReacquireParams(cfg.reacquire, cfg.reacq_gate, cfg.reacq_gate_per_s,
                                                          cfg.reacq_size_min, cfg.reacq_size_max))
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        # khung mới nhất giữa hai luồng
        self._slot_cv = threading.Condition()
        self._slot: Optional[Frame] = None
        self._pending_reset = False
        self._ended = False
        self._done = False   # nguồn hết VÀ khung cuối đã xử lý xong
        # kết quả công bố
        self._pub_cv = threading.Condition()
        self._seq = 0
        self._jpeg: Optional[bytes] = None
        self._tracks: list[Track] = []
        self._frame_wh = (0, 0)
        self._state: dict = self._empty_state()
        # đo hiệu năng
        self._pub_times: collections.deque = collections.deque(maxlen=120)
        self._infer_ms: collections.deque = collections.deque(maxlen=60)
        self._lat_ms: collections.deque = collections.deque(maxlen=60)
        self._k: Optional[geometry.Intrinsics] = None
        self._k_wh = (0, 0)
        self._notice: Optional[tuple[str, float]] = None
        self._proc = psutil.Process() if psutil else None
        self._cpu = 0.0
        self._cpu_t = 0.0
        if self._proc:
            self._proc.cpu_percent(None)

    # ------------------------------------------------------------ vòng đời
    def start(self) -> None:
        self.source.open()
        for name, fn in (("capture", self._capture_loop), ("infer", self._infer_loop)):
            t = threading.Thread(target=fn, name=f"labview-{name}", daemon=True)
            t.start()
            self._threads.append(t)
        self._on_event(f"Bat dau: nguon {self.source.name}")

    def stop(self) -> None:
        self._stop.set()
        with self._slot_cv:
            self._slot_cv.notify_all()
        with self._pub_cv:
            self._pub_cv.notify_all()
        for t in self._threads:
            t.join(timeout=5)
        self.source.close()
        for s in self.sinks:
            try:
                s.close()
            except Exception:  # pragma: no cover
                log.exception("sink.close loi")

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    @property
    def done(self) -> bool:
        return self._done

    # ------------------------------------------------------------ sự kiện
    def _on_event(self, msg: str) -> None:
        ts = dt.datetime.now().astimezone().isoformat(timespec="milliseconds")
        self.events.append({"ts": ts, "msg": msg})
        log.info(msg)
        if msg.startswith("TU BO KHOA"):
            self._notice = (msg, time.monotonic())

    # ------------------------------------------------------------ luồng 1
    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            fr = self.source.read()
            if fr is None:
                if not self.source.live and self.cfg.loop and self.source.restart():
                    self._pending_reset = True
                    continue
                self._ended = True
                self._on_event("Het nguon hinh" if not self.source.live else "Mat nguon hinh (camera loi)")
                with self._slot_cv:
                    self._slot_cv.notify_all()
                return
            with self._slot_cv:
                self._slot = fr
                self._slot_cv.notify()

    # ------------------------------------------------------------ luồng 2
    def _infer_loop(self) -> None:
        while not self._stop.is_set():
            with self._slot_cv:
                if self._slot is None:
                    self._slot_cv.wait(timeout=0.5)
                fr, self._slot = self._slot, None
            if fr is None:
                if self._ended:
                    self._publish_state_only()
                    return
                continue
            try:
                self.process_frame(fr)
            except Exception:
                log.exception("Loi xu ly khung")
                time.sleep(0.2)

    def _publish_state_only(self) -> None:
        with self._pub_cv:
            self._done = True
            self._state = dict(self._state, ended=True, running=False)
            self._seq += 1
            self._pub_cv.notify_all()

    # ------------------------------------------------------------ xử lý một khung
    def _intrinsics(self, w: int, h: int) -> geometry.Intrinsics:
        if self._k is None or self._k_wh != (w, h):
            c = self.cfg
            self._k = geometry.Intrinsics.build(w, h, c.hfov_deg, c.fx, c.fy, c.cx, c.cy)
            self._k_wh = (w, h)
        return self._k

    def process_frame(self, fr: Frame) -> None:
        """Xử lý đồng bộ một khung (luồng suy luận gọi; test gọi trực tiếp)."""
        t0 = time.monotonic()
        img = fr.image
        mw = self.cfg.max_width
        if mw and img.shape[1] > mw:
            s = mw / img.shape[1]
            img = cv2.resize(img, (mw, max(1, int(round(img.shape[0] * s)))), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        if self._pending_reset:
            self._pending_reset = False
            self.detector.reset()
            self.lock.release("video lap lai")
        tracks = self.detector.track(img)
        t1 = time.monotonic()
        status = self.lock.update(tracks)
        k = self._intrinsics(w, h)
        report = self._report(status, k, fr.ts)
        for s in self.sinks:
            try:
                s.on_lock(report)
            except Exception:
                log.exception("sink loi")
        overlay.draw(img, tracks, status.track_id if status.active else None, k.cx, k.cy, status)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.cfg.jpeg_quality])
        if not ok:
            return
        now = time.monotonic()
        self._infer_ms.append((t1 - t0) * 1000.0)
        self._lat_ms.append((now - fr.ts) * 1000.0)
        self._pub_times.append(now)
        state = self._build_state(fr, w, h, tracks, status, report, now)
        with self._pub_cv:
            self._jpeg, self._tracks, self._frame_wh = buf.tobytes(), tracks, (w, h)
            self._state = state
            self._seq += 1
            self._pub_cv.notify_all()

    def _report(self, st: LockStatus, k: geometry.Intrinsics, ts: float) -> Optional[LockReport]:
        if not (st.active and st.track):
            return None
        yaw, pitch = geometry.angle_offsets(k, st.track.box)
        dist = geometry.estimate_distance(k, st.track.box, self.cfg.real_width_m)
        return LockReport(st.track.id, yaw, pitch, dist, self.cfg.real_width_m, st.track.conf, ts)

    def _build_state(self, fr, w, h, tracks, st, rep, now) -> dict:
        pts = self._pub_times
        fps = 0.0
        if len(pts) >= 2 and pts[-1] > pts[0]:
            fps = (len(pts) - 1) / (pts[-1] - pts[0])
        if self._proc and now - self._cpu_t >= 1.0:
            self._cpu, self._cpu_t = self._proc.cpu_percent(None), now
        lock = {"active": st.active}
        if st.active:
            lock.update(track_id=st.track_id, since_s=round(now - st.since, 1),
                        visible=st.track is not None, lost_for_s=round(st.lost_for_s, 1),
                        assumed_width_m=self.cfg.real_width_m, state=st.state, reacquired=st.reacquired)
            if rep:
                lock.update(yaw_deg=round(rep.yaw_deg, 2), pitch_deg=round(rep.pitch_deg, 2),
                            distance_m=None if rep.distance_m is None else round(rep.distance_m, 1),
                            conf=round(rep.conf, 2))
        notice = None
        if self._notice and now - self._notice[1] < 5.0:
            notice = self._notice[0]
        return {
            "running": True, "ended": False,
            "ts": dt.datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "frame_index": fr.index,
            "source": {"name": self.source.name, "kind": self.source.kind, "width": w, "height": h},
            "fps": round(fps, 1),
            "infer_ms": round(sum(self._infer_ms) / len(self._infer_ms), 1),
            "latency_ms": round(sum(self._lat_ms) / len(self._lat_ms), 1),
            "cpu_percent": round(self._cpu, 0),
            "tracks": [{"id": t.id, "conf": round(t.conf, 2), "box": [round(v, 1) for v in t.box]} for t in tracks],
            "lock": lock, "notice": notice,
            "events": list(self.events)[-12:],
        }

    def _empty_state(self) -> dict:
        return {"running": False, "ended": False, "tracks": [], "lock": {"active": False},
                "fps": 0, "infer_ms": 0, "latency_ms": 0, "cpu_percent": 0, "notice": None,
                "events": [], "source": {"name": self.source.name, "kind": self.source.kind, "width": 0, "height": 0}}

    # ------------------------------------------------------------ API cho máy chủ
    def snapshot(self) -> tuple[int, dict, Optional[bytes]]:
        with self._pub_cv:
            state = dict(self._state, events=list(self.events)[-12:])
            return self._seq, state, self._jpeg

    def wait_frame(self, last_seq: int, timeout: float = 2.0) -> tuple[int, Optional[bytes]]:
        with self._pub_cv:
            if self._seq == last_seq and not self._stop.is_set() and not self._done:
                self._pub_cv.wait(timeout=timeout)
            return self._seq, self._jpeg

    def frame_size(self) -> tuple[int, int]:
        with self._pub_cv:
            return self._frame_wh

    def lock_at_norm(self, x: float, y: float) -> Optional[int]:
        """Khóa theo tọa độ bấm chuẩn hóa [0,1] trên ảnh."""
        with self._pub_cv:
            w, h = self._frame_wh
            tracks = list(self._tracks)
        if w == 0:
            return None
        return self.lock.lock_point(x * w, y * h, tracks, self.cfg.click_margin_px)

    def lock_track_id(self, tid: int) -> bool:
        with self._pub_cv:
            tracks = list(self._tracks)
        return self.lock.lock_id(tid, tracks)

    def lock_best(self) -> Optional[int]:
        with self._pub_cv:
            tracks = list(self._tracks)
        return self.lock.lock_best(tracks)

    def release(self) -> bool:
        return self.lock.release("thu cong")
