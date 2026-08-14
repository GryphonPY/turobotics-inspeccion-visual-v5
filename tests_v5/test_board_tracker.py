from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from inspection_v5.board_tracker import BoardTracker, V5BoardConfig
from inspection_v5.contracts import FramePacket

ROOT = Path(__file__).resolve().parents[1]


def synthetic_board() -> np.ndarray:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    width, height = config.canonical_size_px
    image = np.full((height, width, 3), 24, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    scale = config.pixels_per_mm
    patch = round(50 * scale)
    quiet = round(7 * scale)
    for marker_id, marker in config.markers.items():
        x = round(float(marker["x_mm"]) * scale)
        y = round(float(marker["y_mm"]) * scale)
        size = round(float(marker["size_mm"]) * scale)
        canvas = np.full((patch, patch, 3), 255, dtype=np.uint8)
        marker_image = cv2.aruco.generateImageMarker(dictionary, marker_id, size)
        canvas[quiet : quiet + size, quiet : quiet + size] = cv2.cvtColor(marker_image, cv2.COLOR_GRAY2BGR)
        image[y - quiet : y - quiet + patch, x - quiet : x - quiet + patch] = canvas
    return image


def packet(image: np.ndarray, sequence: int = 1) -> FramePacket:
    return FramePacket(sequence, float(sequence), image)


def test_tracker_detects_all_markers_and_returns_metric_roi() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    observation = BoardTracker(config).observe(packet(synthetic_board()), now=1.0)

    assert observation.board_ok
    assert observation.found_ids == (0, 1, 2, 3)
    assert observation.roi is not None
    assert observation.roi.shape[:2] == (560, 320)
    assert observation.reprojection_error_px < 1.1


def test_tracker_refines_fast_detection_corners_before_reprojection_check(monkeypatch) -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    source = synthetic_board()
    tracker = BoardTracker(config)
    detected = tracker._detect(source)
    offsets = {0: (4, 0), 1: (0, 4), 2: (-4, 0), 3: (0, -4)}
    jittered = {
        marker_id: corners + np.float32(offsets[marker_id])
        for marker_id, corners in detected.items()
    }
    _, raw_error = tracker._fresh_homography(jittered)
    monkeypatch.setattr(tracker, "_detect", lambda _frame: jittered)

    observation = tracker.observe(packet(source), now=1.0)

    assert raw_error > config.max_reprojection_error_px
    assert observation.board_ok
    assert observation.reprojection_error_px <= config.max_reprojection_error_px


def test_tracker_returns_full_canonical_board_and_roi() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    observation = BoardTracker(config).observe(packet(synthetic_board()), now=1.0)

    assert observation.board is not None
    assert observation.board.shape[:2] == (2235, 1728)
    assert observation.roi is not None
    assert observation.roi.shape[:2] == (560, 320)


def test_tracker_holds_small_homography_jitter() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    tracker = BoardTracker(config)
    source = synthetic_board()
    first = tracker.observe(packet(source, 1), now=1.0)
    shifted = cv2.warpAffine(source, np.float32([[1, 0, 0.6], [0, 1, 0.4]]), source.shape[1::-1])
    second = tracker.observe(packet(shifted, 2), now=1.1)

    assert first.board is not None and second.board is not None
    assert float(np.mean(cv2.absdiff(first.board, second.board))) < 2.0


def test_tracker_converts_roi_bbox_to_board_coordinates() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    board_bbox = BoardTracker(config).roi_bbox_to_board((10, 20, 100, 200))

    assert board_bbox == (564, 598, 200, 400)


def test_tracker_warps_roi_once(monkeypatch) -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    tracker = BoardTracker(config)
    source = synthetic_board()
    calls = 0
    original = cv2.warpPerspective

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(cv2, "warpPerspective", counted)
    result = tracker.observe(packet(source), now=1.0)

    assert result.board_ok
    assert calls == 1


def test_tracker_uses_short_homography_cache_for_temporary_marker_loss() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    tracker = BoardTracker(config)
    source = synthetic_board()
    first = tracker.observe(packet(source, 1), now=1.0)
    covered = source.copy()
    covered[:500, :500] = 24
    second = tracker.observe(packet(covered, 2), now=1.1)

    assert first.board_ok
    assert second.board_ok
    assert second.reason == "cached_homography"
    assert abs(second.homography_age_ms - 100.0) < 0.01


def test_tracker_uses_cache_for_one_bad_reprojection_frame(monkeypatch) -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    tracker = BoardTracker(config)
    source = synthetic_board()
    first = tracker.observe(packet(source, 1), now=1.0)
    assert first.board_ok
    cached_homography = tracker._last_homography
    assert cached_homography is not None

    monkeypatch.setattr(
        tracker,
        "_fresh_homography",
        lambda _found: (cached_homography, config.max_reprojection_error_px + 4.0),
    )
    second = tracker.observe(packet(source, 2), now=1.1)

    assert second.board_ok
    assert second.reason == "cached_homography"
    assert second.reprojection_error_px == first.reprojection_error_px
