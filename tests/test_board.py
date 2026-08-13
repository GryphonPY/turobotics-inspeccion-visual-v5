from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from inspection_v4.board import BoardRectifier, expected_marker_points
from inspection_v4.config import load_configs


ROOT = Path(__file__).resolve().parents[1]


def synthetic_board() -> np.ndarray:
    board, _, _ = load_configs(ROOT)
    image = np.full((board.height_px, board.width_px, 3), 24, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    patch = round(50 * board.pixels_per_mm)
    quiet = round(7 * board.pixels_per_mm)
    for marker_id, marker in board.markers.items():
        patch_x = round(marker["x_mm"] * board.pixels_per_mm) - quiet
        patch_y = round(marker["y_mm"] * board.pixels_per_mm) - quiet
        patch_image = np.full((patch, patch, 3), 255, dtype=np.uint8)
        marker_image = cv2.aruco.generateImageMarker(dictionary, marker_id, round(36 * board.pixels_per_mm), 1)
        code_x = quiet
        code_y = quiet
        patch_image[code_y : code_y + marker_image.shape[0], code_x : code_x + marker_image.shape[1]] = cv2.cvtColor(marker_image, cv2.COLOR_GRAY2BGR)
        image[patch_y : patch_y + patch, patch_x : patch_x + patch] = patch_image
    return image


def test_template_coordinates_are_metric_and_corner_identity_is_explicit() -> None:
    board, _, _ = load_configs(ROOT)
    points = expected_marker_points(board)
    assert board.roi_rect_px == (544, 558, 640, 1120)
    assert np.allclose(points[0][0], [176.0, 176.0], atol=0.01)
    assert np.allclose(points[2][0], [176.0, 1771.2], atol=0.01)
    assert board.markers[0]["corner"] == "top_left"
    assert board.markers[2]["corner"] == "bottom_left"


def test_rectifier_detects_all_four_markers_in_canonical_board() -> None:
    board, _, _ = load_configs(ROOT)
    observation = BoardRectifier(board).observe(synthetic_board())
    assert observation.found_ids == (0, 1, 2, 3)
    assert observation.homography is not None
    assert observation.reprojection_error_px < 1.0
    assert observation.reason == ""


def test_rectifier_handles_perspective_warp() -> None:
    board, _, _ = load_configs(ROOT)
    source = synthetic_board()
    height, width = source.shape[:2]
    matrix = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]),
        np.float32([[80, 90], [width - 140, 25], [width - 90, height - 80], [35, height - 20]]),
    )
    warped = cv2.warpPerspective(source, matrix, (width, height), borderValue=(15, 15, 15))
    observation = BoardRectifier(board).observe(warped)
    assert observation.found_ids == (0, 1, 2, 3)
    assert observation.homography is not None
    assert observation.reprojection_error_px < 3.0


def test_rectifier_rejects_duplicate_required_marker_ids() -> None:
    board, _, _ = load_configs(ROOT)
    rectifier = BoardRectifier(board)
    rectifier._detect = lambda frame: (
        {0: np.float32([[176, 176], [464, 176], [464, 464], [176, 464]]),
         1: np.float32([[1263, 176], [1551, 176], [1551, 464], [1263, 464]]),
         2: np.float32([[176, 1771], [464, 1771], [464, 2059], [176, 2059]]),
         3: np.float32([[1263, 1771], [1551, 1771], [1551, 2059], [1263, 2059]])},
        (0, 1, 2, 3),
        (1,),
    )
    observation = rectifier.observe(synthetic_board())
    assert observation.reason == "duplicate_markers:1"
    assert observation.duplicate_ids == (1,)
