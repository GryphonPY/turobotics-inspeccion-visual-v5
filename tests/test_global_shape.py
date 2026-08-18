from __future__ import annotations

import numpy as np

from inspection_v4.piece import PieceAligner


def test_shape_iou_is_symmetric_and_penalizes_rearrangement() -> None:
    reference = np.zeros((80, 80), dtype=np.uint8)
    reference[10:25, 20:60] = 255
    reference[25:70, 32:48] = 255
    rearranged = np.zeros_like(reference)
    rearranged[10:25, 20:60] = 255
    rearranged[45:60, 20:60] = 255

    forward = PieceAligner.shape_iou(rearranged, reference)
    reverse = PieceAligner.shape_iou(reference, rearranged)

    assert forward == reverse
    assert forward < 0.85
    assert PieceAligner.shape_iou(reference, reference) == 1.0
