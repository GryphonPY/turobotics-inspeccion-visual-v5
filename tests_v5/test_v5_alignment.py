from __future__ import annotations

import cv2
import numpy as np

from inspection_v5.alignment import PoseAligner
from inspection_v5.features import make_model_tensor


def reference() -> tuple[np.ndarray, np.ndarray]:
    gray = np.full((560, 320), 24, dtype=np.uint8)
    mask = np.zeros_like(gray)
    cv2.rectangle(mask, (110, 80), (210, 150), 255, -1)
    cv2.rectangle(mask, (80, 150), (240, 230), 255, -1)
    cv2.rectangle(mask, (110, 230), (210, 320), 255, -1)
    cv2.rectangle(mask, (80, 320), (240, 400), 255, -1)
    gray[mask > 0] = 190
    return gray, mask


def transformed(gray: np.ndarray, mask: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
    center = (gray.shape[1] / 2.0, gray.shape[0] / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    matrix[:, 2] += np.float32([15.0, -12.0])
    return (
        cv2.warpAffine(gray, matrix, (gray.shape[1], gray.shape[0]), borderValue=24),
        cv2.warpAffine(mask, matrix, (mask.shape[1], mask.shape[0])),
    )


def test_alignment_accepts_translation_and_arbitrary_in_plane_rotation() -> None:
    gray, mask = reference()
    aligner = PoseAligner(mask, gray, alignment_min_score=0.45)
    transformed_gray, transformed_mask = transformed(gray, mask, 90.0)

    aligned = aligner.align(transformed_mask, transformed_gray)

    assert aligned.valid
    assert aligned.pose_score >= 0.45
    assert make_model_tensor(aligned).shape == (3, 224, 224)


def test_alignment_rejects_empty_mask() -> None:
    gray, mask = reference()
    aligned = PoseAligner(mask, gray).align(np.zeros_like(mask), gray)

    assert not aligned.valid
    assert aligned.reason == "mask_empty"
