from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from .camera_picker import choose_camera
from .inspector import V5Inspector
from .runtime import InspectionRuntime
from .ui.main_window import MainWindow


def _log_launcher_error(root: Path, stage: str, exc: BaseException) -> None:
    log_path = root / "logs" / "v5_launcher.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{datetime.now(UTC).isoformat(timespec='seconds')}] {stage}: {exc!r}\n")
        traceback.print_exc(file=handle)


class CameraWorker(QThread):
    frame_ready = Signal(object)
    status = Signal(str)

    def __init__(self, index: int, parent: QThread | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self._running = True

    def run(self) -> None:
        capture = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(self.index)
        if not capture.isOpened():
            self.status.emit(f"No se pudo abrir la cámara {self.index}")
            return
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        capture.set(cv2.CAP_PROP_FPS, 30)
        self.status.emit("Cámara conectada")
        while self._running:
            ok, frame = capture.read()
            if ok and frame is not None:
                self.frame_ready.emit(frame)
            else:
                time.sleep(0.05)
        capture.release()

    def stop(self) -> None:
        self._running = False
        self.wait(1000)


def run_qt_app(root: Path, camera_index: int = 0, fullscreen: bool = False) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    runtime = InspectionRuntime(root, inspector=V5Inspector(root))
    camera = CameraWorker(camera_index)
    camera.frame_ready.connect(runtime.publish_frame)
    window = MainWindow(runtime, root)
    window.camera_worker = camera
    app.aboutToQuit.connect(camera.stop)
    runtime.start()
    camera.start()
    if fullscreen:
        window.showFullScreen()
    else:
        window.showMaximized()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="V5 television demo")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--camera", type=int, default=-1, help="Índice; -1 abre selector con vista previa")
    parser.add_argument("--fullscreen", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        camera = args.camera if args.camera >= 0 else choose_camera(root, app)
        if camera is None:
            return 0
        return run_qt_app(root, camera, args.fullscreen)
    except Exception as exc:  # noqa: BLE001  # launcher must persist unexpected startup failures
        _log_launcher_error(root, "qt_app_failed", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
