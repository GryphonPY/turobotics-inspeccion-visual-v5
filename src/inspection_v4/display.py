from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import cv2
import numpy as np

from .types import BoardObservation

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
VIDEO_WIDTH = 820
PANEL_X = VIDEO_WIDTH
PANEL_WIDTH = SCREEN_WIDTH - PANEL_X
VIDEO_X = 12
VIDEO_Y = 66
VIDEO_INNER_WIDTH = VIDEO_WIDTH - 24
VIDEO_INNER_HEIGHT = 650


@dataclass
class BoardStatusLatch:
    """Keep the user-facing board status from flickering on isolated bad frames."""

    good_frames_required: int = 3
    bad_frames_required: int = 3
    displayed: BoardObservation | None = None
    _good_streak: int = 0
    _bad_streak: int = 0

    def update(self, observation: BoardObservation) -> BoardObservation:
        reliable = observation.found_ids == (0, 1, 2, 3) and not observation.reason
        if reliable:
            self._good_streak += 1
            self._bad_streak = 0
            if self.displayed is None or self._good_streak >= self.good_frames_required:
                self.displayed = observation
        else:
            self._bad_streak += 1
            self._good_streak = 0
            if self.displayed is None or self._bad_streak >= self.bad_frames_required:
                self.displayed = observation
        return self.displayed


def fit_into(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Fit an image into a fixed rectangle without changing the dashboard size."""
    if image is None or image.size == 0:
        return np.full((height, width, 3), 18, dtype=np.uint8)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(
        image,
        (max(1, int(image.shape[1] * scale)), max(1, int(image.shape[0] * scale))),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.full((height, width, 3), 18, dtype=np.uint8)
    y = (height - resized.shape[0]) // 2
    x = (width - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return canvas


def put_text(
    image: np.ndarray,
    text: str,
    origin: tuple[int, int],
    scale: float = 0.6,
    color: tuple[int, int, int] = (220, 220, 220),
    thickness: int = 1,
) -> None:
    cv2.putText(
        image,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def put_lines(
    image: np.ndarray,
    lines: Iterable[str],
    origin: tuple[int, int],
    line_height: int = 28,
    scale: float = 0.6,
    color: tuple[int, int, int] = (220, 220, 220),
    thickness: int = 1,
) -> int:
    """Draw readable multi-line text and return the next y coordinate."""
    x, y = origin
    for line in lines:
        put_text(image, line, (x, y), scale, color, thickness)
        y += line_height
    return y


def wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def board_status(observation: BoardObservation) -> tuple[str, str, tuple[int, int, int]]:
    """Return a human-readable marker status for the fixed UI and logs."""
    required = (0, 1, 2, 3)
    found = observation.found_ids
    missing = tuple(marker_id for marker_id in required if marker_id not in found)
    if not missing and not observation.reason:
        return (
            "ARUCO: 0 1 2 3",
            "TABLERO OK | 4 ARUCO ESTABLES",
            (60, 220, 80),
        )
    if not missing:
        return (
            "ARUCO: 0 1 2 3",
            f"TABLERO NO CONFIABLE | {observation.reason.upper()}",
            (0, 190, 255),
        )
    found_text = " ".join(str(marker_id) for marker_id in found) or "NINGUNO"
    missing_text = " ".join(str(marker_id) for marker_id in missing) or "NINGUNO"
    return (
        f"DETECTADOS: {found_text}",
        f"FALTAN: {missing_text} | NO GRABA",
        (0, 190, 255),
    )


def place_video(
    screen: np.ndarray,
    source: np.ndarray,
    view_label: str,
    observation: BoardObservation,
) -> None:
    """Place a stable camera/rectified view in the left dashboard region."""
    video = fit_into(source, VIDEO_INNER_WIDTH, VIDEO_INNER_HEIGHT)
    screen[VIDEO_Y : VIDEO_Y + VIDEO_INNER_HEIGHT, VIDEO_X : VIDEO_X + VIDEO_INNER_WIDTH] = video
    cv2.rectangle(
        screen,
        (VIDEO_X, VIDEO_Y),
        (VIDEO_X + VIDEO_INNER_WIDTH - 1, VIDEO_Y + VIDEO_INNER_HEIGHT - 1),
        (90, 90, 90),
        1,
    )
    put_text(screen, view_label, (18, 42), 0.72, (235, 235, 235), 2)
    first, second, color = board_status(observation)
    put_text(screen, first, (26, SCREEN_HEIGHT - 52), 0.62, color, 2)
    put_text(screen, second, (26, SCREEN_HEIGHT - 22), 0.58, color, 1)


def window_closed(window: str) -> bool:
    """Return true when the user clicked the native window close button."""
    try:
        return cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1
    except cv2.error:
        return True
