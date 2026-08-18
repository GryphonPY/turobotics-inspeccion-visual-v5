from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..contracts import PublicState
from ..runtime import InspectionRuntime
from .diagnostic_panel import DiagnosticPanel
from .result_panel import ResultPanel
from .theme import GREEN, MUTED, RED, install_fonts, stylesheet
from .video_view import TrackingVideoView
from .view_model import PresentationViewModel


class MainWindow(QMainWindow):
    def __init__(self, runtime: InspectionRuntime, root: Path) -> None:
        super().__init__()
        self.runtime = runtime
        self.root = root
        install_fonts()
        self.setWindowTitle("TUROBOTICS · INSPECCIÓN VISUAL")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet(stylesheet())
        root_widget = QWidget()
        root_widget.setObjectName("root")
        self.setCentralWidget(root_widget)
        outer = QVBoxLayout(root_widget)
        outer.setContentsMargins(22, 18, 22, 16)
        outer.setSpacing(14)
        outer.addWidget(self._header())
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        self.video = TrackingVideoView()
        self.panel = ResultPanel()
        self.panel.setMinimumWidth(320)
        self.panel.setMaximumWidth(460)
        body.addWidget(self.video)
        body.addWidget(self.panel)
        body.setSizes([840, 396])
        body.setStretchFactor(0, 68)
        body.setStretchFactor(1, 32)
        outer.addWidget(body, 1)
        outer.addWidget(self._footer())
        self.diagnostic = DiagnosticPanel(root, root_widget)
        self.diagnostic.setGeometry(30, 100, 420, 350)
        self.panel.exit_button.clicked.connect(self.close)
        self.panel.reset_button.clicked.connect(self.runtime.reset_counters)
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(16)
        self._last_state_version = -1

    def _header(self) -> QFrame:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 4, 14, 4)
        logo = QLabel()
        logo.setFixedSize(58, 52)
        logo_path = self.root / "assets" / "Logo_TuRobotics_Colorizado.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            logo.setPixmap(pixmap.scaled(52, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand = QLabel("TUROBOTICS")
        brand.setObjectName("brand")
        divider = QLabel("/")
        divider.setObjectName("headerDivider")
        title = QLabel("INSPECCIÓN VISUAL")
        title.setObjectName("title")
        layout.addWidget(logo)
        layout.addWidget(brand)
        layout.addWidget(divider)
        layout.addWidget(title)
        layout.addStretch(1)
        return frame

    def _footer(self) -> QFrame:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 0, 14, 0)
        self.footer = QLabel("F2 diagnóstico  ·  F11 ventana/pantalla completa  ·  ESC salir")
        self.footer.setStyleSheet(f"color: {MUTED}; font-size: 18px;")
        layout.addWidget(self.footer)
        layout.addStretch(1)
        self.camera_status = QLabel("CÁMARA: INICIANDO")
        self.camera_status.setStyleSheet(f"color: {MUTED}; font-size: 16px; font-weight: 700;")
        layout.addWidget(self.camera_status)
        return frame

    def set_camera_status(self, message: str) -> None:
        normalized = message.upper()
        color = RED if "NO SE PUDO" in normalized else GREEN if "CONECTADA" in normalized else MUTED
        self.camera_status.setText(f"CÁMARA · {message.upper()}")
        self.camera_status.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: 700;")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def refresh(self) -> None:
        state: PublicState = self.runtime.latest_public_state()
        model = PresentationViewModel.from_public_state(state)
        self.video.set_frame(state.frame)
        self.video.set_tracking(state.tracking_bbox, state.tracking_mode, model.headline)
        if state.version != self._last_state_version:
            self.panel.apply(model)
            self.diagnostic.update_metrics(state.metrics)
            self._last_state_version = state.version

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F2:
            self.diagnostic.setVisible(not self.diagnostic.isVisible())
            self.diagnostic.raise_()
            return
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.runtime.stop()
        event.accept()
