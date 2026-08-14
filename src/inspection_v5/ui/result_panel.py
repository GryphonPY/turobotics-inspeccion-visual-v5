from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .component_map import ComponentMap
from .theme import AMBER, CYAN, GREEN, RED
from .view_model import PresentationViewModel


class ResultPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(8)
        eyebrow = QLabel("VERIFICACIÓN DEL ENSAMBLE")
        eyebrow.setObjectName("eyebrow")
        self.headline = QLabel("ÁREA LIBRE")
        self.headline.setObjectName("headline")
        self.headline.setWordWrap(False)
        self.headline.setMinimumHeight(58)
        self._headline_font = QFont("Segoe UI", 42, QFont.Weight.Black)
        self.detail = QLabel("Coloca la pieza dentro del tablero")
        self.detail.setObjectName("detail")
        self.detail.setWordWrap(True)
        self.instruction = QLabel("LISTO PARA INSPECCIONAR")
        self.instruction.setObjectName("instruction")
        self.map = ComponentMap()
        self.map.setFixedHeight(215)
        self.counter = QFrame()
        self.counter.setObjectName("stats")
        stats_layout = QHBoxLayout(self.counter)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(6)
        self._stat_values: dict[str, QLabel] = {}
        for key, label, color in (("passed", "APROBADAS", GREEN), ("failed", "NO PASA", RED), ("unreliable", "INCIDENCIAS", AMBER)):
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 4, 8, 4)
            card_layout.setSpacing(0)
            value = QLabel("0")
            value.setObjectName("statValue")
            value.setStyleSheet(f"color: {color};")
            caption = QLabel(label)
            caption.setObjectName("statLabel")
            card_layout.addWidget(value, 0, Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(caption, 0, Qt.AlignmentFlag.AlignCenter)
            stats_layout.addWidget(card, 1)
            self._stat_values[key] = value
        buttons = QHBoxLayout()
        self.reset_button = QPushButton("Reiniciar")
        self.exit_button = QPushButton("Salir")
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.exit_button)
        layout.addWidget(eyebrow)
        layout.addWidget(self.headline)
        layout.addWidget(self.detail)
        layout.addWidget(self.instruction)
        layout.addWidget(self.map, 1)
        layout.addWidget(self.counter)
        layout.addLayout(buttons)

    def _fit_headline(self) -> None:
        available = self.headline.width()
        if available <= 0:
            return
        for size in range(42, 19, -1):
            font = QFont(self._headline_font)
            font.setPointSize(size)
            if QFontMetrics(font).horizontalAdvance(self.headline.text()) <= available - 4:
                self.headline.setFont(font)
                return

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._fit_headline()

    def apply(self, model: PresentationViewModel) -> None:
        self.headline.setText(model.headline)
        self.headline.setStyleSheet(f"color: {model.accent};")
        self._fit_headline()
        self.detail.setText(model.detail)
        self.instruction.setText(model.instruction)
        self.instruction.setStyleSheet(f"color: {CYAN if not model.show_result else model.accent};")
        counters = model.counters
        for key, value in self._stat_values.items():
            value.setText(str(counters.get(key, 0)))
        self.map.set_states(model.component_states)
