from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from inspection_v5.alignment import AlignedCrop
from inspection_v5.geometry_judge import GeometryJudge

ROOT = Path(__file__).resolve().parents[1]


def reference_mask() -> np.ndarray:
    mask = np.zeros((560, 320), dtype=np.uint8)
    cv2.rectangle(mask, (110, 80), (210, 150), 255, -1)
    cv2.rectangle(mask, (80, 150), (240, 230), 255, -1)
    cv2.rectangle(mask, (110, 230), (210, 320), 255, -1)
    cv2.rectangle(mask, (80, 320), (240, 400), 255, -1)
    return mask


def aligned(mask: np.ndarray) -> AlignedCrop:
    gray = np.where(mask > 0, 190, 24).astype(np.uint8)
    return AlignedCrop(gray, mask, cv2.Canny(gray, 40, 120), np.eye(2, 3, dtype=np.float32), 0.0, 1.0, 100.0, True)


def test_geometry_rejects_rearranged_equal_area() -> None:
    reference = reference_mask()
    judge = GeometryJudge(reference, ROOT / "config" / "v5" / "component_anchors.json", global_min_iou=0.85)
    rearranged = np.roll(reference, 180, axis=0)

    result = judge.evaluate(aligned(rearranged))

    assert abs(np.count_nonzero(reference) - np.count_nonzero(rearranged)) / np.count_nonzero(reference) < 0.01
    assert not result.usable
    assert "silhouette_incompatible" in result.reasons


def test_geometry_accepts_reference_shape() -> None:
    judge = GeometryJudge(reference_mask(), ROOT / "config" / "v5" / "component_anchors.json")

    result = judge.evaluate(aligned(reference_mask()))

    assert result.usable
    assert result.silhouette_iou >= 0.95
    assert set(result.local_scores) == {f"C{index:02d}" for index in range(1, 11)}
