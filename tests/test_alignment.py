from __future__ import annotations

import cv2
import numpy as np

from inspection_v4.piece import PieceAligner
from inspection_v4.types import PieceObservation


def _piece(mask: np.ndarray) -> PieceObservation:
    ys, xs = np.where(mask > 0)
    return PieceObservation(
        mask,
        mask.copy(),
        int(cv2.countNonZero(mask)),
        (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)),
        (float(xs.mean()), float(ys.mean())),
        True,
    )


def test_alignment_accepts_translation_and_arbitrary_in_plane_rotation() -> None:
    reference = np.zeros((320, 220), np.uint8)
    cv2.rectangle(reference, (70, 45), (145, 260), 255, thickness=-1)
    cv2.rectangle(reference, (35, 105), (180, 155), 255, thickness=-1)
    source = np.zeros_like(reference)
    source[45:261, 70:146] = reference[45:261, 70:146]
    matrix = cv2.getRotationMatrix2D((110, 160), 137.0, 1.0)
    matrix[:, 2] += np.array([28.0, -14.0])
    transformed = cv2.warpAffine(source, matrix, (reference.shape[1], reference.shape[0]))
    result = PieceAligner(0.45).align(_piece(transformed), reference)
    assert result.valid
    assert result.alignment_score >= 0.45


def test_alignment_rejects_empty_reference() -> None:
    mask = np.zeros((20, 20), np.uint8)
    piece = PieceObservation(mask, mask.copy(), 0, (0, 0, 0, 0), (0.0, 0.0), False, "piece_not_found")
    result = PieceAligner().align(piece, mask)
    assert not result.valid


def test_alignment_keeps_pose_valid_when_one_component_is_missing() -> None:
    reference = np.zeros((320, 220), np.uint8)
    cv2.rectangle(reference, (70, 45), (145, 260), 255, thickness=-1)
    cv2.rectangle(reference, (35, 105), (180, 155), 255, thickness=-1)
    missing = reference.copy()
    missing[45:100, 70:146] = 0
    result = PieceAligner(0.85).align(_piece(missing), reference)
    assert result.valid
    assert result.alignment_score >= 0.85
