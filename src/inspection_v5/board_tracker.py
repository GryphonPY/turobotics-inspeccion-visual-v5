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
    homography_hold_px: float

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
            homography_hold_px=float(raw.get("homography_hold_px", 2.0)),
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
    def _refine_corners(frame: np.ndarray, found: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
        """Reduce camera-stream corner quantization before fitting the homography.

        Marker detection may run on a reduced image for speed, but the returned
        corners are mapped back to the original frame.  Refining those points on
        the original grayscale frame keeps the metric fit accurate enough for
        real phone-webcam perspective without scanning the full image twice.
        """
        if not found:
            return found
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT,
            30,
            0.01,
        )
        refined: dict[int, np.ndarray] = {}
        for marker_id, corners in found.items():
            original = corners.reshape(-1, 1, 2).astype(np.float32)
            candidate = original.copy()
            try:
                cv2.cornerSubPix(gray, candidate, (5, 5), (-1, -1), criteria)
            except cv2.error:
                candidate = original
            candidate_points = candidate.reshape(4, 2)
            original_points = original.reshape(4, 2)
            displacement = np.linalg.norm(candidate_points - original_points, axis=1)
            if np.all(np.isfinite(candidate_points)) and float(np.max(displacement)) <= 8.0:
                refined[marker_id] = candidate_points
            else:
                refined[marker_id] = original_points
        return refined

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

    def _homography_shift(self, candidate: np.ndarray, frame_shape: tuple[int, ...]) -> float:
        if self._last_homography is None:
            return float("inf")
        height, width = frame_shape[:2]
        corners = np.float32([[[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]]])
        previous_points = cv2.perspectiveTransform(corners, self._last_homography)[0]
        candidate_points = cv2.perspectiveTransform(corners, candidate)[0]
        return float(np.mean(np.linalg.norm(candidate_points - previous_points, axis=1)))

    def _roi_from_board(self, board: np.ndarray) -> np.ndarray:
        scale = self.config.pixels_per_mm
        roi = self.config.roi_mm
        x = round(roi["x"] * scale)
        y = round(roi["y"] * scale)
        width = round(roi["width"] * scale)
        height = round(roi["height"] * scale)
        crop = board[y : y + height, x : x + width]
        return cv2.resize(crop, self.config.roi_output_px, interpolation=cv2.INTER_AREA)

    def roi_bbox_to_board(self, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x, y, width, height = bbox
        scale_x = self.config.roi_mm["width"] * self.config.pixels_per_mm / self.config.roi_output_px[0]
        scale_y = self.config.roi_mm["height"] * self.config.pixels_per_mm / self.config.roi_output_px[1]
        origin_x = self.config.roi_mm["x"] * self.config.pixels_per_mm
        origin_y = self.config.roi_mm["y"] * self.config.pixels_per_mm
        return (
            round(origin_x + x * scale_x),
            round(origin_y + y * scale_y),
            round(width * scale_x),
            round(height * scale_y),
        )

    def observe(self, packet: FramePacket, now: float | None = None) -> TrackingSnapshot:
        now = time.monotonic() if now is None else now
        frame = packet.bgr
        if frame is None or frame.size == 0:
            return TrackingSnapshot(packet.sequence, packet.captured_at, False, None, (0, 0, 0, 0), 0.0, 0.0, 0.0, reason="frame_empty")

        found = self._refine_corners(frame, self._detect(frame))
        found_ids = tuple(sorted(found))
        homography: np.ndarray | None = None
        error = float("inf")
        reason = ""
        fresh = all(marker_id in found for marker_id in self.REQUIRED_IDS)
        if fresh:
            candidate, error = self._fresh_homography(found)
            if candidate is not None and error <= self.config.max_reprojection_error_px:
                if (
                    self._last_homography is None
                    or self._homography_shift(candidate, frame.shape) > self.config.homography_hold_px
                ):
                    self._last_homography = candidate
                self._last_observed_at = now
                self._last_error = error
                homography = self._last_homography
            else:
                reason = "reprojection_error" if candidate is not None else "homography_failed"
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

        board = cv2.warpPerspective(frame, homography, self.config.canonical_size_px)
        roi = self._roi_from_board(board)
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
            board=board,
        )
