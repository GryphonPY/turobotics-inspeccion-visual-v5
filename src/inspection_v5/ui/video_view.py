from __future__ import annotations

from collections import deque

import cv2
import numpy as np
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..contracts import TrackingMode
from .theme import AMBER, CYAN, GRAY, GREEN, RED


class TrackingVideoView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._bbox = (0, 0, 0, 0)
        self._mode = TrackingMode.EMPTY
        self._label = "ÁREA LIBRE"
        self._history: deque[tuple[int, int, int, int]] = deque(maxlen=5)
        self.setMinimumSize(640, 420)

    def set_frame(self, bgr: np.ndarray | None) -> None:
        if bgr is None or bgr.size == 0:
            return
        if bgr.ndim == 2:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        self._pixmap = QPixmap.fromImage(QImage(rgb.data, width, height, int(rgb.strides[0]), QImage.Format.Format_RGB888).copy())
        self.update()

    def set_tracking(self, bbox: tuple[int, int, int, int], mode: TrackingMode, label: str) -> None:
        if mode == TrackingMode.EMPTY or bbox[2] <= 0 or bbox[3] <= 0:
            self._history.clear()
            self._bbox = (0, 0, 0, 0)
        else:
            self._history.append(bbox)
            self._bbox = tuple(int(np.median([item[index] for item in self._history])) for index in range(4))
        self._mode, self._label = mode, label
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(1200, 800)

    @staticmethod
    def _color(mode: TrackingMode) -> QColor:
        return QColor({TrackingMode.EMPTY: GRAY, TrackingMode.STABILIZING: AMBER, TrackingMode.INSPECTING: AMBER, TrackingMode.PASS: GREEN, TrackingMode.FAIL: RED}.get(mode, CYAN))

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0A0A0A"))
        if self._pixmap is None:
            painter.setPen(QColor(GRAY))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ESPERANDO CÁMARA")
            painter.end()
            return
        source = self._pixmap.size()
        target = self.rect()
        scaled = self._pixmap.scaled(target.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        x = (target.width() - scaled.width()) / 2.0
        y = (target.height() - scaled.height()) / 2.0
        painter.drawPixmap(int(x), int(y), scaled)
        if self._mode != TrackingMode.EMPTY and self._bbox[2] > 0 and self._bbox[3] > 0 and source.width() > 0 and source.height() > 0:
            sx, sy = scaled.width() / source.width(), scaled.height() / source.height()
            bx, by, bw, bh = self._bbox
            rect = QRectF(x + bx * sx, y + by * sy, bw * sx, bh * sy)
            color = self._color(self._mode)
            painter.setPen(QPen(color, 4.0))
            corner = min(34.0, rect.width() * 0.22, rect.height() * 0.22)
            for dx, dy, sxn, syn in ((0, 0, 1, 1), (1, 0, -1, 1), (0, 1, 1, -1), (1, 1, -1, -1)):
                px = rect.left() if dx == 0 else rect.right()
                py = rect.top() if dy == 0 else rect.bottom()
                painter.drawLine(px, py, px + sxn * corner, py)
                painter.drawLine(px, py, px, py + syn * corner)
            painter.setPen(QPen(color, 1.5))
            label_top = max(6.0, rect.top() - 30.0)
            label_width = max(40.0, min(360.0, target.right() - rect.left() - 6.0))
            painter.drawText(QRectF(rect.left(), label_top, label_width, 26), self._label)
        painter.end()
