from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from inspection_v4.board import BoardRectifier
from inspection_v4.config import load_configs
from inspection_v4.quality import assess_frame
from testsupport import synthetic_board


ROOT = Path(__file__).resolve().parents[1]


def test_intentional_black_background_is_not_counted_as_clipping() -> None:
    board, config, _ = load_configs(ROOT)
    image = synthetic_board()
    rectifier = BoardRectifier(board)
    observation = rectifier.observe(image)
    report = assess_frame(image, observation, board, config)
    assert report.metrics["black_fraction"] < 0.1
    assert report.metrics["clipped_fraction"] < config.quality_max_marker_clipped_fraction


def test_blurred_board_is_rejected() -> None:
    board, config, _ = load_configs(ROOT)
    image = cv2.GaussianBlur(synthetic_board(), (31, 31), 0)
    rectifier = BoardRectifier(board)
    observation = rectifier.observe(image)
    # Severe blur may prevent ArUco detection; either path must be unsafe.
    report = assess_frame(image, observation, board, config)
    assert not report.valid


def test_motion_metric_is_available_after_the_first_frame() -> None:
    board, config, _ = load_configs(ROOT)
    image = synthetic_board()
    rectifier = BoardRectifier(board)
    observation = rectifier.observe(image)
    report = assess_frame(image, observation, board, config, previous_canonical=image.copy())
    assert "motion_mean" in report.metrics
    assert report.metrics["motion_mean"] == 0.0


def test_release_quality_uses_the_eighty_level_sharpness_floor() -> None:
    _, config, _ = load_configs(ROOT)
    assert config.quality_min_laplacian == 80.0
    assert config.quality_max_motion_mean == 1.0
    assert config.quality_max_black_fraction == 0.03
    assert config.quality_max_white_fraction == 0.03
