from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from inspection_v4.board import BoardRectifier
from inspection_v4.components import ReferenceSet
from inspection_v4.config import load_configs
from inspection_v4.piece import PieceAligner, PieceSegmenter

ROOT = Path(__file__).resolve().parents[1]
LIVE_COMPLETE = Path(
    r"C:\Users\axel2\AppData\Local\Temp\codex-clipboard-f82ac532-db8f-4d46-a62a-827bb077b4dc.png"
)
LIVE_COMPLETE_WITH_LIGHT_BAND = Path(
    r"C:\Users\axel2\AppData\Local\Temp\codex-clipboard-46deac7b-b363-4964-a65d-d69a17e63c75.png"
)


def test_live_complete_piece_survives_background_gradient() -> None:
    if not LIVE_COMPLETE.exists():
        return
    board, config, _ = load_configs(ROOT)
    reference = ReferenceSet.load(ROOT / "data" / "references")
    image = cv2.imread(str(LIVE_COMPLETE))
    assert image is not None
    _, observation = BoardRectifier(board).warp(image)
    assert observation.roi is not None

    piece = PieceSegmenter(board, config).segment(observation.roi)
    aligned = PieceAligner(config.alignment_min_score).align(
        piece, reference.complete_mask, reference.complete_gray
    )

    assert piece.valid
    assert piece.area_px >= 90_000
    assert PieceAligner.shape_iou(aligned.mask, reference.complete_mask) >= 0.85


def test_live_complete_piece_ignores_bright_band_on_black_board() -> None:
    if not LIVE_COMPLETE_WITH_LIGHT_BAND.exists():
        return
    board, config, _ = load_configs(ROOT)
    reference = ReferenceSet.load(ROOT / "data" / "references")
    image = cv2.imread(str(LIVE_COMPLETE_WITH_LIGHT_BAND))
    assert image is not None
    _, observation = BoardRectifier(board).warp(image)
    assert observation.roi is not None

    segmenter = PieceSegmenter(board, config)
    piece = segmenter.segment(observation.roi)
    aligned = PieceAligner(config.alignment_min_score).align(
        piece, reference.complete_mask, reference.complete_gray
    )

    assert segmenter.last_threshold_mode == "adaptive_otsu"
    assert segmenter.last_threshold >= 110
    assert 90_000 <= piece.area_px <= 100_000
    assert aligned.valid
    assert aligned.alignment_score >= 0.90
    assert PieceAligner.shape_iou(aligned.mask, reference.complete_mask) >= 0.90


def test_adaptive_threshold_excludes_connected_light_band() -> None:
    board, config, _ = load_configs(ROOT)
    reference = ReferenceSet.load(ROOT / "data" / "references")
    gray = np.full(reference.complete_mask.shape, 65, dtype=np.uint8)
    gray[180:850, 40:540] = 92
    gray[reference.complete_mask > 0] = 180
    roi = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    adaptive_segmenter = PieceSegmenter(board, config)
    adaptive = adaptive_segmenter.segment(roi)
    fixed = PieceSegmenter(board, config, background_mad_multiplier=2.0).segment(roi)
    aligned = PieceAligner(config.alignment_min_score).align(
        adaptive, reference.complete_mask, reference.complete_gray
    )

    assert adaptive.area_px < fixed.area_px * 0.5
    assert abs(adaptive.area_px - cv2.countNonZero(reference.complete_mask)) < 2_000
    assert aligned.valid
    assert PieceAligner.shape_iou(aligned.mask, reference.complete_mask) >= 0.95
