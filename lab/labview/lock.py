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
    state: str = "tracking"            # tracking (bám) | searching (đang tìm lại) | reacquired (vừa gán lại)
    reacquired: int = 0                # số lần đã tự gán lại khóa từ lúc khóa
    predicted: Optional[tuple[float, float]] = None  # tâm dự đoán khi đang tìm lại


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


@dataclass(frozen=True)
class ReacquireParams:
    """Gán lại khóa khi bộ theo dõi đổi ID (ByteTrack hay cấp ID mới cho cùng một vật).
    Cổng khoảng cách = cạnh lớn của khung bao cuối * (gate + gate_per_s * giây_mất_dấu);
    tỉ lệ bề rộng (mới / cuối) phải trong [size_min, size_max]; ứng viên phải có conf >= min_conf.
    Không gán lại khi mục tiêu vừa ở sát mép ảnh (< 0,5 cạnh khung bao) và đang đi ra ngoài (coi là đã rời khung)."""
    enabled: bool = True
    gate: float = 1.0
    gate_per_s: float = 1.5
    size_min: float = 0.5
    size_max: float = 2.0
    min_conf: float = 0.25


_VEL_WINDOW_S = 0.5   # cửa sổ ước lượng vận tốc ảnh (từ các lần thấy gần nhất)
_PRED_MAX_S = 1.0     # không ngoại suy vị trí quá khoảng này
_FLASH_S = 2.0        # trạng thái "reacquired" hiện trong chừng này giây sau khi gán lại


def _center(b):
    return (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0


class LockManager:
    """Giữ trạng thái khóa; tự bỏ khóa khi mất mục tiêu quá `lost_timeout_s`; trong thời gian chờ
    tự gán lại khóa cho track MỚI xuất hiện gần vị trí dự đoán với kích thước tương tự."""

    def __init__(self, lost_timeout_s: float = 2.0,
                 clock: Callable[[], float] = time.monotonic,
                 on_event: Optional[Callable[[str], None]] = None,
                 reacquire: Optional[ReacquireParams] = None):
        self.lost_timeout_s = lost_timeout_s
        self.reacquire = reacquire or ReacquireParams()
        self._clock = clock
        self._on_event = on_event or (lambda msg: None)
        self._mu = threading.Lock()
        self._id: Optional[int] = None
        self._since = 0.0
        self._last_seen = 0.0
        self._last_box: Optional[tuple] = None
        self._last_ids: frozenset = frozenset()   # ID có mặt ở khung cuối còn thấy mục tiêu (không phải "track mới")
        self._hist: list = []                     # (t, cx, cy) các lần thấy gần nhất
        self._reacq = 0
        self._reacq_at = -1e9
        self._size = 0.0
        self.reacq_info: list = []  # mỗi lần gán lại: dist (theo cạnh khung bao), size_ratio, lost_s (cho bench)

    def _emit(self, msg: str) -> None:
        self._on_event(msg)

    def _observe(self, now: float, t: Track, tracks: Sequence[Track]) -> None:
        self._last_seen, self._last_box = now, t.box
        self._last_ids = frozenset(x.id for x in tracks)
        cx, cy = _center(t.box)
        self._hist = [h for h in self._hist if now - h[0] <= _VEL_WINDOW_S] + [(now, cx, cy)]

    def _velocity(self) -> tuple[float, float]:
        cx, cy = _center(self._last_box)
        t0, x0, y0 = self._hist[0]
        dt = self._last_seen - t0
        if dt < 0.08:  # quá ít lịch sử: vận tốc nhiễu, coi như đứng yên
            return 0.0, 0.0
        return (cx - x0) / dt, (cy - y0) / dt

    def _predict(self, now: float, frame_wh=None) -> tuple[float, float]:
        cx, cy = _center(self._last_box)
        vx, vy = self._velocity()
        s = min(now - self._last_seen, _PRED_MAX_S)
        px, py = cx + vx * s, cy + vy * s
        if frame_wh:  # vị trí dự đoán không ra ngoài khung hình
            px, py = min(max(px, 0.0), frame_wh[0]), min(max(py, 0.0), frame_wh[1])
        return px, py

    def _left_frame(self, frame_wh) -> bool:
        """Khung bao cuối sát mép ảnh và vận tốc hướng ra ngoài: coi mục tiêu đã rời khung."""
        if not frame_wh:
            return False
        b = self._last_box
        m = 0.5 * max(b[2] - b[0], b[3] - b[1])
        vx, vy = self._velocity()
        return ((b[0] < m and vx < 0) or (frame_wh[0] - b[2] < m and vx > 0)
                or (b[1] < m and vy < 0) or (frame_wh[1] - b[3] < m and vy > 0))

    def _pick(self, tracks: Sequence[Track], pred: tuple[float, float], lost_for: float):
        """Trả (track, khoảng cách tới vị trí dự đoán, tỉ lệ bề rộng) hoặc None."""
        p = self.reacquire
        lw = self._last_box[2] - self._last_box[0]
        size = max(lw, self._last_box[3] - self._last_box[1])
        if lw <= 0 or size <= 0:
            return None
        self._size = size
        gate = size * (p.gate + p.gate_per_s * lost_for)
        best, best_d, best_r = None, None, 0.0
        for t in tracks:
            if t.id == self._id or t.id in self._last_ids:
                continue
            ratio = (t.box[2] - t.box[0]) / lw
            if t.conf < p.min_conf or not (p.size_min <= ratio <= p.size_max):
                continue
            cx, cy = _center(t.box)
            d = ((cx - pred[0]) ** 2 + (cy - pred[1]) ** 2) ** 0.5
            if d <= gate and (best_d is None or d < best_d):
                best, best_d, best_r = t, d, ratio
        return None if best is None else (best, best_d, best_r)

    def lock_id(self, track_id: int, tracks: Sequence[Track]) -> bool:
        with self._mu:
            t = next((t for t in tracks if t.id == track_id), None)
            if t is None:
                return False
            now = self._clock()
            self._id, self._since = track_id, now
            self._hist, self._reacq, self._reacq_at, self.reacq_info = [], 0, -1e9, []
            self._observe(now, t, tracks)
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

    def update(self, tracks: Sequence[Track], frame_wh: Optional[tuple[float, float]] = None) -> LockStatus:
        """Gọi mỗi khung hình với danh sách track hiện tại (và kích thước khung đã xử lý nếu biết)."""
        lost_msg = None
        with self._mu:
            if self._id is None:
                return LockStatus(active=False)
            now = self._clock()
            found = next((t for t in tracks if t.id == self._id), None)
            if found is not None:
                self._observe(now, found, tracks)
                st = "reacquired" if now - self._reacq_at <= _FLASH_S else "tracking"
                return LockStatus(True, self._id, found, self._since, 0.0, st, self._reacq)
            lost_for = now - self._last_seen
            if lost_for > self.lost_timeout_s:
                tid, self._id = self._id, None
                lost_msg = f"TU BO KHOA ID {tid}: mat muc tieu {lost_for:.1f} s (nguong {self.lost_timeout_s:g} s)"
            else:
                pred = self._predict(now, frame_wh)
                hit = None
                if self.reacquire.enabled and not self._left_frame(frame_wh):
                    hit = self._pick(tracks, pred, lost_for)
                if hit is None:
                    return LockStatus(True, self._id, None, self._since, lost_for, "searching", self._reacq, pred)
                cand, dist, ratio = hit
                old, self._id = self._id, cand.id
                self._reacq += 1
                self._reacq_at = now
                self.reacq_info = (self.reacq_info + [dict(dist=dist / self._size, size_ratio=ratio, lost_s=lost_for)])[-200:]
                self._hist = []  # vận tốc bắt đầu lại từ track mới, không trộn vị trí của track cũ
                self._observe(now, cand, tracks)
                msg = f"GAN LAI khoa ID {old} -> {cand.id} (mat {lost_for:.2f} s, lan {self._reacq})"
                st = LockStatus(True, self._id, cand, self._since, 0.0, "reacquired", self._reacq)
        if lost_msg is None:
            self._emit(msg)
            return st
        self._emit(lost_msg)
        return LockStatus(active=False)

    def locked_id(self) -> Optional[int]:
        with self._mu:
            return self._id
