"""Logic khóa mục tiêu (thuần, không phụ thuộc OpenCV/YOLO, dễ kiểm thử)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence


@dataclass(frozen=True)
class Track:
    id: int
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 (pixel khung đã xử lý)
    conf: float


@dataclass(frozen=True)
class LockStatus:
    active: bool
    track_id: Optional[int] = None
    track: Optional[Track] = None      # None khi đang mất dấu (chưa quá hạn)
    since: Optional[float] = None      # đồng hồ monotonic lúc khóa
    lost_for_s: float = 0.0


def hit_test(px: float, py: float, tracks: Sequence[Track], margin: float = 0.0) -> Optional[Track]:
    """Chọn khung theo điểm bấm: khung chứa điểm (ưu tiên khung nhỏ nhất);
    không có thì khung gần nhất trong phạm vi `margin` pixel; không có thì None."""
    inside = [t for t in tracks
              if t.box[0] <= px <= t.box[2] and t.box[1] <= py <= t.box[3]]
    if inside:
        return min(inside, key=lambda t: (t.box[2] - t.box[0]) * (t.box[3] - t.box[1]))
    best, best_d = None, None
    for t in tracks:
        dx = max(t.box[0] - px, 0.0, px - t.box[2])
        dy = max(t.box[1] - py, 0.0, py - t.box[3])
        d = (dx * dx + dy * dy) ** 0.5
        if d <= margin and (best_d is None or d < best_d):
            best, best_d = t, d
    return best


class LockManager:
    """Giữ trạng thái khóa; tự bỏ khóa khi mất mục tiêu quá `lost_timeout_s`."""

    def __init__(self, lost_timeout_s: float = 2.0,
                 clock: Callable[[], float] = time.monotonic,
                 on_event: Optional[Callable[[str], None]] = None):
        self.lost_timeout_s = lost_timeout_s
        self._clock = clock
        self._on_event = on_event or (lambda msg: None)
        self._mu = threading.Lock()
        self._id: Optional[int] = None
        self._since = 0.0
        self._last_seen = 0.0

    def _emit(self, msg: str) -> None:
        self._on_event(msg)

    def lock_id(self, track_id: int, tracks: Sequence[Track]) -> bool:
        with self._mu:
            if not any(t.id == track_id for t in tracks):
                return False
            now = self._clock()
            self._id, self._since, self._last_seen = track_id, now, now
        self._emit(f"KHOA muc tieu ID {track_id}")
        return True

    def lock_point(self, px: float, py: float, tracks: Sequence[Track], margin: float = 0.0) -> Optional[int]:
        t = hit_test(px, py, tracks, margin)
        if t is None:
            return None
        return t.id if self.lock_id(t.id, tracks) else None

    def lock_best(self, tracks: Sequence[Track]) -> Optional[int]:
        if not tracks:
            return None
        t = max(tracks, key=lambda t: t.conf)
        return t.id if self.lock_id(t.id, tracks) else None

    def release(self, reason: str = "thu cong") -> bool:
        with self._mu:
            if self._id is None:
                return False
            tid, self._id = self._id, None
        self._emit(f"HUY khoa ID {tid} ({reason})")
        return True

    def update(self, tracks: Sequence[Track]) -> LockStatus:
        """Gọi mỗi khung hình với danh sách track hiện tại."""
        lost_msg = None
        with self._mu:
            if self._id is None:
                return LockStatus(active=False)
            now = self._clock()
            found = next((t for t in tracks if t.id == self._id), None)
            if found is not None:
                self._last_seen = now
                return LockStatus(True, self._id, found, self._since, 0.0)
            lost_for = now - self._last_seen
            if lost_for > self.lost_timeout_s:
                tid, self._id = self._id, None
                lost_msg = f"TU BO KHOA ID {tid}: mat muc tieu {lost_for:.1f} s (nguong {self.lost_timeout_s:g} s)"
            else:
                return LockStatus(True, self._id, None, self._since, lost_for)
        self._emit(lost_msg)
        return LockStatus(active=False)

    def locked_id(self) -> Optional[int]:
        with self._mu:
            return self._id
