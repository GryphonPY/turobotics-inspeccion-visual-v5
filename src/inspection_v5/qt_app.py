from __future__ import annotations

import argparse
import sys
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from .camera_picker import choose_camera
from .inspector import V5Inspector
from .runtime import InspectionRuntime
from .ui.main_window import MainWindow


def _open_camera(
    index: int,
    status: Callable[[str], None] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> tuple[cv2.VideoCapture | None, str]:
    """Open a camera, tolerating the short driver handoff after the picker closes."""
    keep_trying = should_continue or (lambda: True)
    backends: tuple[tuple[str, int | None], ...] = (
        ("DSHOW", cv2.CAP_DSHOW),
        ("MSMF", cv2.CAP_MSMF),
        ("AUTO", None),
    )
    for attempt in range(16):
        if not keep_trying():
            return None, ""
        for backend_name, backend in backends:
            capture = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
            if not capture.isOpened():
                capture.release()
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            capture.set(cv2.CAP_PROP_FPS, 30)
            ok, _ = capture.read()
            if ok:
                return capture, backend_name
            capture.release()
        if status is not None:
            status(f"Esperando cámara {index} · intento {attempt + 1}/16")
        time.sleep(0.25)
    return None, ""


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
        self.status.emit(f"Conectando cámara {self.index}...")
        capture, backend = _open_camera(self.index, self.status.emit, lambda: self._running)
        if capture is None:
            self.status.emit(f"No se pudo abrir la cámara {self.index}")
            return
        self.status.emit(f"Cámara conectada · {backend}")
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
    camera.status.connect(window.set_camera_status)
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
    default_root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="V5 television demo")
    parser.add_argument("--root", type=Path, default=default_root)
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
