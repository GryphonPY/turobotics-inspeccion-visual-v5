from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

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
        patch_image[quiet : quiet + marker_image.shape[0], quiet : quiet + marker_image.shape[1]] = cv2.cvtColor(marker_image, cv2.COLOR_GRAY2BGR)
        image[patch_y : patch_y + patch, patch_x : patch_x + patch] = patch_image
    return image
