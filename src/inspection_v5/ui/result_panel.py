from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .component_map import ComponentMap
from .theme import CYAN
from .view_model import PresentationViewModel


class ResultPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(14)
        eyebrow = QLabel("VERIFICACIÓN DEL ENSAMBLE")
        eyebrow.setObjectName("eyebrow")
        self.headline = QLabel("ÁREA LIBRE")
        self.headline.setObjectName("headline")
        self.headline.setWordWrap(True)
        self.detail = QLabel("Coloca la pieza dentro del tablero")
        self.detail.setObjectName("detail")
        self.detail.setWordWrap(True)
        self.instruction = QLabel("LISTO PARA INSPECCIONAR")
        self.instruction.setObjectName("instruction")
        self.map = ComponentMap()
        self.counter = QLabel("APROBADAS 0   ·   DEFECTUOSAS 0   ·   INCIDENCIAS 0")
        self.counter.setObjectName("counter")
        self.counter.setWordWrap(True)
        buttons = QHBoxLayout()
        self.reset_button = QPushButton("Reiniciar")
        self.exit_button = QPushButton("Salir")
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.exit_button)
        layout.addWidget(eyebrow)
        layout.addWidget(self.headline)
        layout.addWidget(self.detail)
        layout.addWidget(self.instruction)
        layout.addSpacing(8)
        layout.addWidget(self.map, 1)
        layout.addWidget(self.counter)
        layout.addLayout(buttons)

    def apply(self, model: PresentationViewModel) -> None:
        self.headline.setText(model.headline)
        self.headline.setStyleSheet(f"color: {model.accent};")
        self.detail.setText(model.detail)
        self.instruction.setText(model.instruction)
        self.instruction.setStyleSheet(f"color: {CYAN if not model.show_result else model.accent};")
        counters = model.counters
        self.counter.setText(
            f"APROBADAS {counters.get('passed', 0)}   ·   "
            f"DEFECTUOSAS {counters.get('failed', 0)}   ·   "
            f"INCIDENCIAS {counters.get('unreliable', 0)}"
        )
        self.map.set_states(model.component_states)
