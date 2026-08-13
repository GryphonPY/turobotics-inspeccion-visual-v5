from __future__ import annotations

import cv2
import numpy as np

from .config import BoardConfig
from .types import BoardObservation


def _dictionary(name: str) -> cv2.aruco_Dictionary:
    try:
        dictionary_id = getattr(cv2.aruco, name)
    except AttributeError as exc:
        raise ValueError(f"Diccionario ArUco no soportado: {name}") from exc
    return cv2.aruco.getPredefinedDictionary(dictionary_id)


def _marker_corners(config: BoardConfig, marker_id: int) -> np.ndarray:
    marker = config.markers[marker_id]
    x = marker["x_mm"] * config.pixels_per_mm
    y = marker["y_mm"] * config.pixels_per_mm
    size = marker["size_mm"] * config.pixels_per_mm
    return np.array(
        [[x, y], [x + size, y], [x + size, y + size], [x, y + size]],
        dtype=np.float32,
    )


def expected_marker_points(config: BoardConfig) -> dict[int, np.ndarray]:
    """Return marker data-square corners in canonical top-left-origin pixels."""
    return {marker_id: _marker_corners(config, marker_id) for marker_id in config.markers}


class BoardRectifier:
    """Detect the physical Carta board and warp it to a metric canonical image."""

    REQUIRED_IDS = (0, 1, 2, 3)

    def __init__(self, config: BoardConfig) -> None:
        self.config = config
        self.dictionary = _dictionary(config.aruco_dictionary)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.dictionary, self.parameters)
        self.expected = expected_marker_points(config)

    def _detect(
        self, frame: np.ndarray
    ) -> tuple[dict[int, np.ndarray], tuple[int, ...], tuple[int, ...]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        corners, ids, _ = self.detector.detectMarkers(gray)
        if ids is None:
            return {}, (), ()
        found: dict[int, np.ndarray] = {}
        duplicates: set[int] = set()
        for corner, marker_id in zip(corners, ids.flatten().tolist()):
            marker_id = int(marker_id)
            if marker_id not in self.expected:
                continue
            if marker_id in found:
                duplicates.add(marker_id)
                continue
            found[marker_id] = corner.reshape(4, 2).astype(np.float32)
        return found, tuple(sorted(found)), tuple(sorted(duplicates))

    @staticmethod
    def _reprojection_error(
        source: np.ndarray, destination: np.ndarray, homography: np.ndarray
    ) -> float:
        projected = cv2.perspectiveTransform(source.reshape(-1, 1, 2), homography).reshape(-1, 2)
        return float(np.mean(np.linalg.norm(projected - destination, axis=1)))

    def observe(self, frame: np.ndarray, warp: bool = True) -> BoardObservation:
        if frame is None or frame.size == 0:
            return BoardObservation((), {}, None, None, float("inf"), (0, 0), (0, 0), "frame_empty")

        found, found_ids, duplicate_ids = self._detect(frame)
        height, width = frame.shape[:2]
        if any(marker_id not in found for marker_id in self.REQUIRED_IDS):
            missing = [str(marker_id) for marker_id in self.REQUIRED_IDS if marker_id not in found]
            return BoardObservation(
                found_ids, found, None, None, float("inf"), (width, height),
                (self.config.width_px, self.config.height_px),
                f"missing_markers:{','.join(missing)}", duplicate_ids,
            )
        if duplicate_ids:
            return BoardObservation(
                found_ids, found, None, None, float("inf"), (width, height),
                (self.config.width_px, self.config.height_px),
                f"duplicate_markers:{','.join(map(str, duplicate_ids))}", duplicate_ids,
            )

        source = np.concatenate([found[marker_id] for marker_id in self.REQUIRED_IDS], axis=0)
        destination = np.concatenate(
            [self.expected[marker_id] for marker_id in self.REQUIRED_IDS], axis=0
        )
        homography, _ = cv2.findHomography(source, destination, cv2.RANSAC, 3.0)
        if homography is None:
            return BoardObservation(
                found_ids, found, None, None, float("inf"), (width, height),
                (self.config.width_px, self.config.height_px), "homography_failed", duplicate_ids
            )

        error = self._reprojection_error(source, destination, homography)
        canonical = None
        roi = None
        if warp:
            canonical = cv2.warpPerspective(
                frame,
                homography,
                (self.config.width_px, self.config.height_px),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0),
            )
            x, y, w, h = self.config.roi_rect_px
            roi = canonical[y : y + h, x : x + w].copy()

        reason = "" if error <= self.config.max_reprojection_error_px else "reprojection_error"
        return BoardObservation(
            found_ids, found, homography, roi, error, (width, height),
            (self.config.width_px, self.config.height_px), reason, duplicate_ids
        )

    def warp(self, frame: np.ndarray) -> tuple[np.ndarray | None, BoardObservation]:
        observation = self.observe(frame, warp=True)
        if observation.homography is None:
            return None, observation
        canonical = cv2.warpPerspective(
            frame,
            observation.homography,
            (self.config.width_px, self.config.height_px),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        return canonical, observation


def draw_board_status(frame: np.ndarray, observation: BoardObservation) -> np.ndarray:
    """Draw a lightweight diagnostic overlay without changing the source frame."""
    output = frame.copy()
    color = (0, 190, 0) if not observation.reason else (0, 80, 220)
    text = (
        f"ArUco {','.join(map(str, observation.found_ids))} "
        f"err={observation.reprojection_error_px:.1f}px"
    )
    cv2.putText(output, text, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return output
