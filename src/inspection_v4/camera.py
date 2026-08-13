from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import CameraConfig


@dataclass(frozen=True)
class CameraInfo:
    index: int
    backend: str
    width: int
    height: int
    fps: float


def _backend_value(name: str) -> int:
    return {
        "DSHOW": getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY),
        "MSMF": getattr(cv2, "CAP_MSMF", cv2.CAP_ANY),
        "ANY": cv2.CAP_ANY,
    }.get(name.upper(), cv2.CAP_ANY)


def enumerate_cameras(config: CameraConfig) -> list[CameraInfo]:
    found: list[CameraInfo] = []
    for index in range(config.max_index + 1):
        candidates: list[CameraInfo] = []
        for backend_name in config.backend_order:
            capture = cv2.VideoCapture(index, _backend_value(backend_name))
            try:
                if not capture.isOpened():
                    continue
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.preferred_width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.preferred_height)
                capture.set(cv2.CAP_PROP_FPS, config.preferred_fps)
                ok, frame = capture.read()
                if ok and frame is not None:
                    height, width = frame.shape[:2]
                    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
                    candidates.append(CameraInfo(index, backend_name, width, height, fps))
            finally:
                capture.release()
        if candidates:
            # Prefer the highest real frame size, then the first configured backend.
            found.append(max(candidates, key=lambda item: (item.width * item.height, -config.backend_order.index(item.backend))))
    return found


def select_camera(
    cameras: list[CameraInfo],
    config: CameraConfig,
    requested_index: int | None = None,
    prefer_saved: bool = True,
) -> CameraInfo | None:
    """Select an eligible camera, preferring an explicit or remembered device."""
    eligible = [
        item for item in cameras
        if item.width >= config.minimum_width and item.height >= config.minimum_height
    ]
    if requested_index is not None:
        return next((item for item in eligible if item.index == requested_index), None)
    if prefer_saved and config.save_index is not None:
        remembered = [item for item in eligible if item.index == config.save_index]
        if config.save_backend:
            remembered_backend = next(
                (item for item in remembered if item.backend == config.save_backend), None
            )
            if remembered_backend is not None:
                return remembered_backend
        if remembered:
            return remembered[0]
    return max(eligible, key=lambda item: item.width * item.height, default=None)


def remember_camera(config_path: Path, camera: CameraInfo) -> None:
    """Persist the selected index/backend without storing a machine-specific device path."""
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["save_index"] = camera.index
    payload["save_backend"] = camera.backend
    payload["saved_device"] = {
        "index": camera.index,
        "backend": camera.backend,
        "width": camera.width,
        "height": camera.height,
    }
    config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class LatestFrameCamera:
    """Threaded camera that exposes only the newest frame; no stale queue is allowed."""

    def __init__(self, index: int, config: CameraConfig, backend: str = "DSHOW") -> None:
        self.index = index
        self.config = config
        self.backend = backend
        self.capture: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.actual_size: tuple[int, int] = (0, 0)
        self._last_frame_time = 0.0

    def open(self) -> bool:
        self.capture = cv2.VideoCapture(self.index, _backend_value(self.backend))
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = cv2.VideoCapture(self.index, cv2.CAP_ANY)
        if not self.capture.isOpened():
            self.capture = None
            return False
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.preferred_width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.preferred_height)
        self.capture.set(cv2.CAP_PROP_FPS, self.config.preferred_fps)
        # These properties are backend-dependent; failure is harmless and reported by quality.
        self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.capture.set(cv2.CAP_PROP_AUTO_WB, 0)
        self.actual_size = (
            int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        deadline = time.monotonic() + self.config.read_timeout_seconds
        while time.monotonic() < deadline:
            ok, frame = self.capture.read()
            if ok and frame is not None:
                with self._lock:
                    self._frame = frame
                    self._last_frame_time = time.monotonic()
                height, width = frame.shape[:2]
                self.actual_size = (width, height)
                if width < self.config.minimum_width or height < self.config.minimum_height:
                    self.release()
                    return False
                return True
        self.release()
        return False

    def start(self) -> "LatestFrameCamera":
        if self.capture is None and not self.open():
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, name="v4-camera", daemon=True)
        self._thread.start()
        return self

    def warmup(self) -> None:
        time.sleep(max(0.0, self.config.warmup_seconds))

    def _reader(self) -> None:
        assert self.capture is not None
        while not self._stop.is_set():
            ok, frame = self.capture.read()
            if ok and frame is not None:
                with self._lock:
                    self._frame = frame
                    self._last_frame_time = time.monotonic()
            else:
                time.sleep(0.02)

    def read(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if self._frame is None or time.monotonic() - self._last_frame_time > max(
                1.0, self.config.read_timeout_seconds
            ):
                return False, None
            return True, self._frame.copy()

    @property
    def opened(self) -> bool:
        return self.capture is not None and not self._stop.is_set()

    @property
    def healthy(self) -> bool:
        with self._lock:
            return self.opened and self._frame is not None and time.monotonic() - self._last_frame_time <= max(
                1.0, self.config.read_timeout_seconds
            )

    def release(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        if self.capture is not None:
            self.capture.release()
        self.capture = None

    close = release

    def __enter__(self) -> "LatestFrameCamera":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.release()
