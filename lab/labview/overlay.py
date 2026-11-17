"""Vẽ lên hình: khung, ID, độ tin cậy; vật thể đang khóa vẽ nổi bật."""
from __future__ import annotations

from typing import Optional, Sequence

import cv2
import numpy as np

from .lock import Track

GREEN = (80, 220, 80)
RED = (40, 40, 255)
YELLOW = (0, 230, 255)
WHITE = (255, 255, 255)


def _label(img, text, x, y, color):
    (tw, th), bl = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y = max(y, th + 4)
    cv2.rectangle(img, (x, y - th - 4), (x + tw + 4, y + bl - 2), color, -1)
    cv2.putText(img, text, (x + 2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


def draw(img: np.ndarray, tracks: Sequence[Track], locked_id: Optional[int], cx: float, cy: float) -> np.ndarray:
    """Vẽ trực tiếp lên `img` (đã là bản sao của khung) và trả lại."""
    h, w = img.shape[:2]
    c = (int(cx), int(cy))
    cv2.line(img, (c[0] - 12, c[1]), (c[0] + 12, c[1]), WHITE, 1, cv2.LINE_AA)
    cv2.line(img, (c[0], c[1] - 12), (c[0], c[1] + 12), WHITE, 1, cv2.LINE_AA)
    for t in tracks:
        x1, y1, x2, y2 = (int(round(v)) for v in t.box)
        if t.id == locked_id:
            cv2.rectangle(img, (x1, y1), (x2, y2), RED, 3, cv2.LINE_AA)
            cv2.rectangle(img, (x1 - 5, y1 - 5), (x2 + 5, y2 + 5), YELLOW, 1, cv2.LINE_AA)
            cv2.line(img, c, ((x1 + x2) // 2, (y1 + y2) // 2), YELLOW, 1, cv2.LINE_AA)
            _label(img, f"KHOA #{t.id} {t.conf:.2f}", x1, y1 - 6, YELLOW)
        else:
            cv2.rectangle(img, (x1, y1), (x2, y2), GREEN, 2, cv2.LINE_AA)
            _label(img, f"#{t.id} {t.conf:.2f}", x1, y1 - 4, GREEN)
    return img
