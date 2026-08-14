from __future__ import annotations

import cv2
import numpy as np

from .alignment import AlignedCrop, crop_aligned


def _normalize_gray(gray: np.ndarray) -> np.ndarray:
    low, high = np.percentile(gray, (2, 98))
    if high <= low:
        return np.zeros_like(gray, dtype=np.float32)
    return np.clip((gray.astype(np.float32) - low) / (high - low), 0.0, 1.0)


def make_model_tensor(aligned: AlignedCrop, size: int = 224) -> np.ndarray:
    gray, mask, edges = crop_aligned(aligned, size)
    return np.stack(
        [
            _normalize_gray(gray),
            (mask > 127).astype(np.float32),
            (edges > 0).astype(np.float32),
        ],
        axis=0,
    ).astype(np.float32)


def make_reference_from_roi(gray: np.ndarray, threshold_floor: float = 18.0) -> tuple[np.ndarray, np.ndarray]:
    if gray.ndim != 2:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    border = np.concatenate([gray[:20].reshape(-1), gray[-20:].reshape(-1), gray[:, :20].reshape(-1), gray[:, -20:].reshape(-1)])
    threshold = max(float(np.median(border)) + threshold_floor, float(cv2.threshold(gray[20:-20, 20:-20], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]))
    mask = (gray > threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return gray, mask
