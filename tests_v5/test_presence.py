from __future__ import annotations

import cv2
import numpy as np

from inspection_v5.presence import PresenceAnalyzer, PresenceConfig


def empty_roi() -> np.ndarray:
    return np.full((560, 320, 3), 24, dtype=np.uint8)


def complete_roi() -> np.ndarray:
    image = empty_roi()
    color = (190, 190, 190)
    cv2.rectangle(image, (110, 110), (210, 180), color, thickness=-1)
    cv2.rectangle(image, (80, 180), (240, 250), color, thickness=-1)
    cv2.rectangle(image, (110, 250), (210, 330), color, thickness=-1)
    cv2.rectangle(image, (80, 330), (240, 400), color, thickness=-1)
    return image


def analyzer() -> PresenceAnalyzer:
    return PresenceAnalyzer(PresenceConfig(reference_area_px=32_000.0))


def test_empty_area_has_low_occupancy() -> None:
    metrics = analyzer().measure(empty_roi())

    assert metrics.occupied_ratio <= 0.12
    assert metrics.bbox == (0, 0, 0, 0)
    assert metrics.reason == "piece_not_found"


def test_piece_has_high_occupancy_and_local_focus() -> None:
    metrics = analyzer().measure(complete_roi())

    assert metrics.occupied_ratio >= 0.35
    assert metrics.bbox[2:] == (161, 291)
    assert metrics.piece_focus > 0.0


def test_presence_is_independent_of_channel_order() -> None:
    source = complete_roi()
    gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    equivalent = np.repeat(gray[:, :, None], 3, axis=2)
    first = analyzer().measure(source)
    second = analyzer().measure(equivalent)

    assert abs(first.occupied_ratio - second.occupied_ratio) < 0.02


def test_motion_is_reported_between_frames() -> None:
    first = complete_roi()
    second = first.copy()
    second[:, :] = empty_roi()

    metrics = analyzer().measure(second, first)

    assert metrics.motion > 1.0


def test_blur_reduces_local_focus_without_using_marker_focus() -> None:
    source = complete_roi()
    blurred = cv2.GaussianBlur(source, (21, 21), 0)

    sharp = analyzer().measure(source)
    soft = analyzer().measure(blurred)

    assert sharp.piece_focus > soft.piece_focus
