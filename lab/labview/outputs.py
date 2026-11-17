"""Giao diện "đầu ra khóa" (LockSink).

Pipeline gọi `on_lock(report)` mỗi khung hình: report là LockReport khi đang khóa và
thấy mục tiêu, None khi không khóa hoặc đang mất dấu. Mốc L0 chỉ có LogSink (ghi log).
Sau này thêm ServoSink (góc cho servo gật một trục) hoặc sink đọc/ghi bộ điều khiển bay
bằng cách viết lớp con LockSink rồi đưa vào danh sách `sinks`, không sửa lõi.
Lưu ý: chương trình hiện KHÔNG gửi lệnh tới thiết bị nào.
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("labview.lock")


@dataclass(frozen=True)
class LockReport:
    track_id: int
    yaw_deg: float          # + = lệch phải
    pitch_deg: float        # + = lệch lên
    distance_m: Optional[float]
    assumed_width_m: float
    conf: float
    ts: float               # đồng hồ monotonic của khung hình


class LockSink(abc.ABC):
    @abc.abstractmethod
    def on_lock(self, report: Optional[LockReport]) -> None: ...

    def close(self) -> None:  # pragma: no cover - mặc định không làm gì
        pass


class LogSink(LockSink):
    """Ghi log khi trạng thái thấy/không thấy mục tiêu đổi, và định kỳ mỗi `every_s` giây."""

    def __init__(self, every_s: float = 1.0):
        self.every_s = every_s
        self._last = None
        self._was_visible = False

    def on_lock(self, report: Optional[LockReport]) -> None:
        visible = report is not None
        if visible != self._was_visible:
            log.info("muc tieu %s", "xuat hien" if visible else "khong thay")
            self._was_visible = visible
        if report and (self._last is None or report.ts - self._last >= self.every_s):
            self._last = report.ts
            d = f"{report.distance_m:.1f} m" if report.distance_m is not None else "n/a"
            log.info("ID %d yaw %+.1f pitch %+.1f dist %s (gia dinh rong %.2f m)",
                     report.track_id, report.yaw_deg, report.pitch_deg, d, report.assumed_width_m)
