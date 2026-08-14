from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class AlignedCrop:
    gray: np.ndarray
    mask: np.ndarray
    edges: np.ndarray
    matrix: np.ndarray
    rotation_deg: float
    pose_score: float
    local_focus: float
    valid: bool
    reason: str = ""


def _principal_angle(mask: np.ndarray) -> float:
    ys, xs = np.where(mask > 127)
    if len(xs) < 3:
        return 0.0
    points = np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])
    points -= points.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(points, full_matrices=False)
    vector = vt[0]
    return float(np.degrees(np.arctan2(vector[1], vector[0])))


def _centroid(mask: np.ndarray) -> np.ndarray:
    moments = cv2.moments(mask)
    if moments["m00"] == 0:
        return np.zeros(2, dtype=np.float32)
    return np.float32([moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]])


def _warp(image: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    first_bool = first > 127
    second_bool = second > 127
    union = np.count_nonzero(first_bool | second_bool)
    if union == 0:
        return 0.0
    return float(np.count_nonzero(first_bool & second_bool) / union)


def _square_crop(image: np.ndarray, mask: np.ndarray, size: int) -> np.ndarray:
    ys, xs = np.where(mask > 127)
    if len(xs) == 0:
        return np.zeros((size, size), dtype=np.uint8)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    width = x1 - x0
    height = y1 - y0
    side = int(np.ceil(max(width, height) * 1.28))
    side = max(side, 8)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    sx0 = round(cx - side / 2.0)
    sy0 = round(cy - side / 2.0)
    sx1 = sx0 + side
    sy1 = sy0 + side
    canvas = np.zeros((side, side), dtype=image.dtype)
    ix0, ix1 = max(0, sx0), min(image.shape[1], sx1)
    iy0, iy1 = max(0, sy0), min(image.shape[0], sy1)
    canvas[iy0 - sy0 : iy1 - sy0, ix0 - sx0 : ix1 - sx0] = image[iy0:iy1, ix0:ix1]
    return cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA)


def crop_aligned(aligned: AlignedCrop, size: int = 224) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        _square_crop(aligned.gray, aligned.mask, size),
        _square_crop(aligned.mask, aligned.mask, size),
        _square_crop(aligned.edges, aligned.mask, size),
    )


class PoseAligner:
    def __init__(
        self,
        reference_mask: np.ndarray,
        reference_gray: np.ndarray,
        alignment_min_score: float = 0.45,
    ) -> None:
        self.reference_mask = (reference_mask > 127).astype(np.uint8) * 255
        self.reference_gray = reference_gray.copy()
        self.alignment_min_score = alignment_min_score

    def align(self, mask: np.ndarray, gray: np.ndarray) -> AlignedCrop:
        input_mask = (mask > 127).astype(np.uint8) * 255
        if cv2.countNonZero(input_mask) == 0:
            empty = np.zeros_like(input_mask)
            return AlignedCrop(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, 0.0, False, "mask_empty")
        reference_center = _centroid(self.reference_mask)
        input_center = _centroid(input_mask)
        reference_angle = _principal_angle(self.reference_mask)
        input_angle = _principal_angle(input_mask)
        best: tuple[float, np.ndarray, float] | None = None
        for flip in (0.0, 180.0):
            rotation = reference_angle - input_angle + flip
            radians = np.deg2rad(rotation)
            cos, sin = np.cos(radians), np.sin(radians)
            cx, cy = input_center
            matrix = np.array([[cos, -sin, 0.0], [sin, cos, 0.0]], dtype=np.float32)
            matrix[:, 2] = input_center - matrix[:, :2] @ np.float32([cx, cy])
            rotated = _warp(input_mask, matrix)
            translated_center = _centroid(rotated)
            matrix[:, 2] += reference_center - translated_center
            candidate = _warp(input_mask, matrix)
            score = _iou(candidate, self.reference_mask)
            if best is None or score > best[0]:
                best = (score, matrix, rotation)
        if best is None:
            empty = np.zeros_like(input_mask)
            return AlignedCrop(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, 0.0, False, "alignment_failed")
        score, matrix, rotation = best
        aligned_mask = _warp(input_mask, matrix)
        aligned_gray = _warp(gray, matrix)
        edges = cv2.Canny(aligned_gray, 40, 120)
        bbox = cv2.boundingRect(aligned_mask)
        x, y, width, height = bbox
        crop = aligned_gray[y : y + height, x : x + width]
        local_mask = aligned_mask[y : y + height, x : x + width]
        laplacian = cv2.Laplacian(crop, cv2.CV_64F)[local_mask > 0] if crop.size else np.array([])
        focus = float(np.var(laplacian)) if laplacian.size else 0.0
        valid = score >= self.alignment_min_score
        return AlignedCrop(
            aligned_gray,
            aligned_mask,
            edges,
            matrix,
            float(rotation % 360.0),
            float(score),
            focus,
            valid,
            "" if valid else "pose_score_low",
        )
