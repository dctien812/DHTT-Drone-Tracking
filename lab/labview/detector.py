"""Giao diện bộ nhận diện + theo dõi ID, và cài đặt bằng Ultralytics YOLO."""
from __future__ import annotations

import abc
import os
from typing import Sequence

import numpy as np

from .lock import Track


class Detector(abc.ABC):
    @abc.abstractmethod
    def track(self, image: np.ndarray) -> list[Track]: ...

    def reset(self) -> None:
        """Xóa trạng thái tracker (khi phát lại video từ đầu)."""


class YoloTracker(Detector):
    def __init__(self, weights: str, imgsz: int = 640, conf: float = 0.25,
                 tracker: str = "bytetrack.yaml", device: str = "cpu", threads: int = 4):
        # Không để Ultralytics kiểm tra mạng / tự cài gói: chương trình không mở kết nối ra ngoài.
        os.environ.setdefault("YOLO_OFFLINE", "1")
        import torch
        from ultralytics import YOLO
        import cv2
        self._torch, self._threads, self._threads_set = torch, max(1, threads), False
        cv2.setNumThreads(1)  # tránh OpenCV tranh lõi với torch (PC nhiều lõi dùng chung với việc khác)
        self._model = YOLO(weights, task="detect")
        self.imgsz, self.conf, self.tracker, self.device = imgsz, conf, tracker, device

    def reset(self) -> None:
        pred = getattr(self._model, "predictor", None)
        if pred is not None and getattr(pred, "trackers", None):
            for t in pred.trackers:
                t.reset()

    def track(self, image: np.ndarray) -> list[Track]:
        res = self._model.track(image, persist=True, conf=self.conf, imgsz=self.imgsz,
                                tracker=self.tracker, device=self.device, verbose=False)[0]
        if not self._threads_set:
            # Ultralytics đặt lại số luồng torch = 8 khi dựng predictor (lần gọi đầu); đặt lại sau đó,
            # nếu không các luồng OpenMP nhàn rỗi quay vòng chiếm ~8 lõi.
            self._torch.set_num_threads(self._threads)
            self._threads_set = True
        b = res.boxes
        if b is None or b.id is None or len(b) == 0:
            return []
        xyxy = b.xyxy.cpu().numpy()
        ids = b.id.int().cpu().numpy()
        conf = b.conf.cpu().numpy()
        return [Track(int(i), (float(x[0]), float(x[1]), float(x[2]), float(x[3])), float(c))
                for i, x, c in zip(ids, xyxy, conf)]
