from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout


def _scan_indices(max_index: int = 6) -> list[int]:
    available: list[int] = []
    for index in range(max_index):
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            continue
        ok, _ = capture.read()
        capture.release()
        if ok:
            available.append(index)
    return available


class CameraPicker(QDialog):
    def __init__(self, root: Path, indices: list[int], selected: int) -> None:
        super().__init__()
        self.root = root
        self.setWindowTitle("Seleccionar cámara · V5")
        self.setMinimumSize(720, 560)
        self.combo = QComboBox()
        self.combo.addItems([f"Cámara {index}" for index in indices])
        if selected in indices:
            self.combo.setCurrentIndex(indices.index(selected))
        self.preview = QLabel("Vista previa")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(420)
        self.preview.setStyleSheet("background: #060B14; color: #9FB0C7; font-size: 24px;")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Elige la cámara del celular o webcam"))
        layout.addWidget(self.combo)
        layout.addWidget(self.preview, 1)
        layout.addWidget(buttons)
        self.capture: cv2.VideoCapture | None = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_preview)
        self.combo.currentIndexChanged.connect(self._open_selected)
        if indices:
            self._open_selected()
        self.timer.start(80)

    def _open_selected(self) -> None:
        if self.capture is not None:
            self.capture.release()
        if self.combo.count() == 0:
            self.capture = None
            return
        index = int(self.combo.currentText().split()[-1])
        self.capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)

    def _refresh_preview(self) -> None:
        if self.capture is None:
            self.preview.setText("No se detectaron cámaras")
            return
        ok, frame = self.capture.read()
        if not ok:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], int(rgb.strides[0]), QImage.Format.Format_RGB888).copy()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def selected_index(self) -> int | None:
        if self.combo.count() == 0:
            return None
        return int(self.combo.currentText().split()[-1])

    def closeEvent(self, event: object) -> None:
        self.timer.stop()
        if self.capture is not None:
            self.capture.release()
        super().closeEvent(event)


def choose_camera(root: Path, app: object) -> int | None:
    del app
    indices = _scan_indices()
    config_path = root / "config" / "v5" / "camera.json"
    selected = 0
    if config_path.exists():
        selected = int(json.loads(config_path.read_text(encoding="utf-8")).get("index", 0))
    dialog = CameraPicker(root, indices, selected)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    index = dialog.selected_index()
    if index is not None:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"index": index, "updated_at": time.time()}, indent=2) + "\n", encoding="utf-8")
    return index
