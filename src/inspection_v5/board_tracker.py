from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .contracts import FramePacket, TrackingSnapshot


@dataclass(frozen=True)
class V5BoardConfig:
    aruco_dictionary: str
    canonical_size_px: tuple[int, int]
    pixels_per_mm: float
    markers: dict[int, dict[str, float | str]]
    roi_mm: dict[str, float]
    roi_output_px: tuple[int, int]
    detection_width_px: int
    max_reprojection_error_px: float
    homography_cache_ms: float

    @classmethod
    def from_json(cls, path: Path) -> V5BoardConfig:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            aruco_dictionary=raw["aruco_dictionary"],
            canonical_size_px=tuple(raw["canonical_size_px"]),
            pixels_per_mm=float(raw["pixels_per_mm"]),
            markers={int(key): value for key, value in raw["markers"].items()},
            roi_mm={key: float(value) for key, value in raw["roi_mm"].items()},
            roi_output_px=tuple(raw["roi_output_px"]),
            detection_width_px=int(raw["detection_width_px"]),
            max_reprojection_error_px=float(raw["max_reprojection_error_px"]),
            homography_cache_ms=float(raw["homography_cache_ms"]),
        )


def _dictionary(name: str) -> cv2.aruco_Dictionary:
    try:
        dictionary_id = getattr(cv2.aruco, name)
    except AttributeError as exc:
        raise ValueError(f"Unsupported ArUco dictionary: {name}") from exc
    return cv2.aruco.getPredefinedDictionary(dictionary_id)


class BoardTracker:
    REQUIRED_IDS = (0, 1, 2, 3)

    def __init__(self, config: V5BoardConfig) -> None:
        self.config = config
        self.detector = cv2.aruco.ArucoDetector(
            _dictionary(config.aruco_dictionary), cv2.aruco.DetectorParameters()
        )
        self.expected = self._expected_marker_points()
        self._last_homography: np.ndarray | None = None
        self._last_observed_at: float | None = None
        self._last_error = float("inf")

    def _expected_marker_points(self) -> dict[int, np.ndarray]:
        points: dict[int, np.ndarray] = {}
        scale = self.config.pixels_per_mm
        for marker_id, marker in self.config.markers.items():
            x = float(marker["x_mm"]) * scale
            y = float(marker["y_mm"]) * scale
            size = float(marker["size_mm"]) * scale
            points[marker_id] = np.float32(
                [[x, y], [x + size, y], [x + size, y + size], [x, y + size]]
            )
        return points

    def _detect(self, frame: np.ndarray) -> dict[int, np.ndarray]:
        height, width = frame.shape[:2]
        target_width = min(width, self.config.detection_width_px)
        scale = target_width / width
        reduced = (
            frame
            if scale >= 0.999
            else cv2.resize(frame, (target_width, round(height * scale)), interpolation=cv2.INTER_AREA)
        )
        gray = cv2.cvtColor(reduced, cv2.COLOR_BGR2GRAY) if reduced.ndim == 3 else reduced
        corners, ids, _ = self.detector.detectMarkers(gray)
        found: dict[int, np.ndarray] = {}
        if ids is None:
            return found
        for corner, marker_id in zip(corners, ids.flatten().tolist()):
            marker_id = int(marker_id)
            if marker_id in self.expected and marker_id not in found:
                found[marker_id] = corner.reshape(4, 2).astype(np.float32) / scale
        return found

    @staticmethod
    def _reprojection_error(
        source: np.ndarray, destination: np.ndarray, homography: np.ndarray
    ) -> float:
        projected = cv2.perspectiveTransform(source.reshape(-1, 1, 2), homography).reshape(-1, 2)
        return float(np.mean(np.linalg.norm(projected - destination, axis=1)))

    def _fresh_homography(self, found: dict[int, np.ndarray]) -> tuple[np.ndarray | None, float]:
        source = np.concatenate([found[marker_id] for marker_id in self.REQUIRED_IDS], axis=0)
        destination = np.concatenate([self.expected[marker_id] for marker_id in self.REQUIRED_IDS], axis=0)
        homography, _ = cv2.findHomography(source, destination, cv2.RANSAC, 3.0)
        if homography is None:
            return None, float("inf")
        return homography, self._reprojection_error(source, destination, homography)

    def _roi_homography(self, board_homography: np.ndarray) -> np.ndarray:
        scale = self.config.pixels_per_mm
        roi = self.config.roi_mm
        translate = np.array(
            [[1.0, 0.0, -roi["x"] * scale], [0.0, 1.0, -roi["y"] * scale], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        output_scale = self.config.roi_output_px[0] / (roi["width"] * scale)
        resize = np.array(
            [[output_scale, 0.0, 0.0], [0.0, output_scale, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        return resize @ translate @ board_homography

    def observe(self, packet: FramePacket, now: float | None = None) -> TrackingSnapshot:
        now = time.monotonic() if now is None else now
        frame = packet.bgr
        if frame is None or frame.size == 0:
            return TrackingSnapshot(packet.sequence, packet.captured_at, False, None, (0, 0, 0, 0), 0.0, 0.0, 0.0, reason="frame_empty")

        found = self._detect(frame)
        found_ids = tuple(sorted(found))
        homography: np.ndarray | None = None
        error = float("inf")
        reason = ""
        fresh = all(marker_id in found for marker_id in self.REQUIRED_IDS)
        if fresh:
            homography, error = self._fresh_homography(found)
            if homography is not None and error <= self.config.max_reprojection_error_px:
                self._last_homography = homography
                self._last_observed_at = now
                self._last_error = error
            else:
                reason = "reprojection_error" if homography is not None else "homography_failed"
        elif self._last_homography is not None and self._last_observed_at is not None:
            age_ms = (now - self._last_observed_at) * 1000.0
            if age_ms <= self.config.homography_cache_ms:
                homography = self._last_homography
                error = self._last_error
                reason = "cached_homography"
        if homography is None:
            missing = ",".join(str(marker_id) for marker_id in self.REQUIRED_IDS if marker_id not in found)
            return TrackingSnapshot(
                packet.sequence, packet.captured_at, False, None, (0, 0, 0, 0), 0.0, 0.0, 0.0,
                found_ids=found_ids, reprojection_error_px=error,
                reason=reason or f"missing_markers:{missing}",
            )

        roi_homography = self._roi_homography(homography)
        roi = cv2.warpPerspective(
            frame,
            roi_homography,
            self.config.roi_output_px,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        age_ms = 0.0 if fresh else (now - (self._last_observed_at or now)) * 1000.0
        return TrackingSnapshot(
            packet.sequence,
            packet.captured_at,
            True,
            roi,
            (0, 0, 0, 0),
            0.0,
            0.0,
            0.0,
            homography_age_ms=age_ms,
            found_ids=found_ids,
            reprojection_error_px=error,
            reason=reason,
        )
