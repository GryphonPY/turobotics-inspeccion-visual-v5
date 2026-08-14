from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..contracts import ComponentPublicState
from .theme import AMBER, GRAY, GREEN, LINE, MUTED, PANEL_2, RED, TEXT


class ComponentMap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.states = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
        self.setMinimumHeight(0)
        self.setMinimumWidth(260)

    def sizeHint(self) -> QSize:
        return QSize(360, 220)

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
        scale = min(width / 360.0, height / 220.0)
        ox = (width - 360 * scale) / 2.0
        oy = (height - 220 * scale) / 2.0
        center_x = 180
        y0 = 8
        # Same silhouette as the proven V4 guide, scaled for the TV panel.
        shapes = {
            "C01": (center_x - 40, y0, 40, 30), "C02": (center_x, y0, 40, 30),
            "C03": (center_x - 90, y0 + 35, 90, 30), "C04": (center_x, y0 + 35, 90, 30),
            "C05": (center_x - 45, y0 + 70, 90, 30),
            "C06": (center_x - 90, y0 + 105, 90, 30), "C07": (center_x, y0 + 105, 90, 30),
            "C08": (center_x - 45, y0 + 140, 90, 30),
            "C09": (center_x - 90, y0 + 175, 90, 30), "C10": (center_x, y0 + 175, 90, 30),
        }
        painter.setPen(QPen(QColor(LINE), max(1.0, 1.5 * scale)))
        painter.drawLine(ox + center_x * scale, oy + 5 * scale, ox + center_x * scale, oy + 215 * scale)
        for name, (x, y, w, h) in shapes.items():
            rect = QRectF(ox + x * scale, oy + y * scale, w * scale, h * scale)
            state = self.states[name]
            pen = QPen(QColor(self._color(state)), max(1.8, 2.5 * scale))
            painter.setPen(pen)
            painter.setBrush(QColor(PANEL_2))
            painter.drawRoundedRect(rect, 6 * scale, 6 * scale)
            painter.setPen(QPen(QColor(TEXT if state is not ComponentPublicState.UNKNOWN else MUTED), 1))
            painter.setFont(QFont("Segoe UI", max(9, int(11 * scale)), QFont.Weight.DemiBold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)
            painter.setPen(QPen(QColor(GRAY), max(1.0, 1.2 * scale)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(rect.center().x() - 4 * scale, rect.top() - 3 * scale, 8 * scale, 8 * scale))
        painter.end()
