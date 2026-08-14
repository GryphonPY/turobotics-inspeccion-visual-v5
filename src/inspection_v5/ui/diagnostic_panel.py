from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from ..contracts import RuntimeMetrics
from .theme import TEXT


class DiagnosticPanel(QFrame):
    def __init__(self, root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.root = root
        self.setObjectName("panel")
        self.setVisible(False)
        layout = QVBoxLayout(self)
        title = QLabel("DIAGNÓSTICO · F2")
        title.setObjectName("title")
        self.form = QFormLayout()
        self.export_button = QPushButton("Exportar diagnóstico")
        self.export_button.clicked.connect(self.export_snapshot)
        layout.addWidget(title)
        layout.addLayout(self.form)
        layout.addWidget(self.export_button)
        self._values: dict[str, QLabel] = {}
        for name in ("FPS tracking", "Tiempo tracking", "Enfoque pieza", "Ocupación", "Movimiento", "Log"):
            value = QLabel("—")
            value.setStyleSheet(f"color: {TEXT}; font-size: 18px;")
            self._values[name] = value
            self.form.addRow(QLabel(name), value)

    def update_metrics(self, metrics: RuntimeMetrics) -> None:
        self._values["FPS tracking"].setText(f"{metrics.tracking_fps:.1f}")
        self._values["Tiempo tracking"].setText(f"{metrics.stage_ms.get('board_presence', 0.0):.1f} ms")
        self._values["Enfoque pieza"].setText(f"{metrics.piece_focus:.1f}")
        self._values["Ocupación"].setText(f"{metrics.occupied_ratio:.3f}")
        self._values["Movimiento"].setText(f"{metrics.motion:.2f}")
        self._values["Log"].setText(metrics.log_path)

    def export_snapshot(self) -> None:
        output_dir = self.root / "data" / "v5" / "diagnostics"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        output = output_dir / f"diagnostic_{stamp}.json"
        values = {name: label.text() for name, label in self._values.items()}
        output.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
