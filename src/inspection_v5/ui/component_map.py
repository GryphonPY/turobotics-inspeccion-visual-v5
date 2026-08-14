from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..contracts import ComponentPublicState
from .theme import AMBER, GREEN, MUTED, PANEL_2, RED, TEXT


class ComponentMap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.states = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
        self.setMinimumHeight(230)

    def sizeHint(self) -> QSize:
        return QSize(420, 250)

    def set_states(self, states: dict[str, ComponentPublicState]) -> None:
        self.states = {f"C{index:02d}": states.get(f"C{index:02d}", ComponentPublicState.UNKNOWN) for index in range(1, 11)}
        self.update()

    @staticmethod
    def _color(state: ComponentPublicState) -> str:
        return {ComponentPublicState.PRESENT: GREEN, ComponentPublicState.MISSING: RED, ComponentPublicState.UNRELIABLE: AMBER}.get(state, MUTED)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = float(self.width())
        height = float(self.height())
        scale = min(width / 360.0, height / 250.0)
        ox = (width - 360 * scale) / 2.0
        oy = (height - 250 * scale) / 2.0
        shapes = {
            "C01": (105, 6, 64, 42), "C02": (191, 6, 64, 42),
            "C03": (62, 54, 106, 40), "C04": (192, 54, 106, 40),
            "C05": (143, 99, 74, 40),
            "C06": (62, 144, 106, 40), "C07": (192, 144, 106, 40),
            "C08": (143, 189, 74, 40),
            "C09": (62, 234, 106, 40), "C10": (192, 234, 106, 40),
        }
        for name, (x, y, w, h) in shapes.items():
            rect = QRectF(ox + x * scale, oy + y * scale, w * scale, h * scale)
            pen = QPen(QColor(self._color(self.states[name])), max(2.0, 3.0 * scale))
            painter.setPen(pen)
            painter.setBrush(PANEL_2)
            painter.drawRoundedRect(rect, 8 * scale, 8 * scale)
            painter.setPen(QPen(QColor(TEXT if self.states[name] is not ComponentPublicState.UNKNOWN else MUTED), 1))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)
        painter.end()
