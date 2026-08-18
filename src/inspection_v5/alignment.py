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
        alignment_min_score: float = 0.35,
    ) -> None:
        self.reference_mask = (reference_mask > 127).astype(np.uint8) * 255
        self.reference_gray = reference_gray.copy()
        self.alignment_min_score = alignment_min_score
        self._pad = 80
        self._padded_ref = cv2.copyMakeBorder(
            self.reference_mask,
            self._pad,
            self._pad,
            self._pad,
            self._pad,
            cv2.BORDER_CONSTANT,
            value=0,
        )
        self._scale = 0.50
        self._ref_small = cv2.resize(
            self.reference_mask, (0, 0), fx=self._scale, fy=self._scale, interpolation=cv2.INTER_AREA
        )
        self._padded_ref_s = cv2.copyMakeBorder(
            self._ref_small,
            round(self._pad * self._scale),
            round(self._pad * self._scale),
            round(self._pad * self._scale),
            round(self._pad * self._scale),
            cv2.BORDER_CONSTANT,
            value=0,
        )

    def align(self, mask: np.ndarray, gray: np.ndarray) -> AlignedCrop:
        input_mask = (mask > 127).astype(np.uint8) * 255
        if cv2.countNonZero(input_mask) == 0:
            empty = np.zeros_like(input_mask)
            return AlignedCrop(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, 0.0, False, "mask_empty")

        center = _centroid(input_mask)
        mask_small = cv2.resize(input_mask, (0, 0), fx=self._scale, fy=self._scale, interpolation=cv2.INTER_AREA)
        center_s = center * self._scale

        coarse_candidates: list[tuple[float, float]] = []
        for deg in range(0, 360, 10):
            rot = float(deg)
            rad = np.deg2rad(rot)
            cos, sin = np.cos(rad), np.sin(rad)
            cx, cy = center_s
            base_matrix = np.array([[cos, -sin, 0.0], [sin, cos, 0.0]], dtype=np.float32)
            base_matrix[:, 2] = center_s - base_matrix[:, :2] @ np.float32([cx, cy])
            rotated = cv2.warpAffine(mask_small, base_matrix, self._ref_small.shape[::-1], flags=cv2.INTER_NEAREST)
            ys, xs = np.where(rotated > 127)
            if len(xs) == 0:
                continue
            x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
            piece_crop = rotated[y0:y1, x0:x1]

            res = cv2.matchTemplate(self._padded_ref_s, piece_crop, cv2.TM_CCORR_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            coarse_candidates.append((max_val, rot))

        if not coarse_candidates:
            empty = np.zeros_like(input_mask)
            return AlignedCrop(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, 0.0, False, "alignment_failed")

        coarse_candidates.sort(key=lambda x: x[0], reverse=True)
        best_rot = coarse_candidates[0][1]

        best = None
        for fine in (-8.0, -6.0, -4.0, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0, 6.0, 8.0):
            rot = (best_rot + fine) % 360.0
            rad = np.deg2rad(rot)
            cos, sin = np.cos(rad), np.sin(rad)
            cx, cy = center
            base_matrix = np.array([[cos, -sin, 0.0], [sin, cos, 0.0]], dtype=np.float32)
            base_matrix[:, 2] = center - base_matrix[:, :2] @ np.float32([cx, cy])
            rotated = cv2.warpAffine(input_mask, base_matrix, (320, 560), flags=cv2.INTER_NEAREST)
            ys, xs = np.where(rotated > 127)
            if len(xs) == 0:
                continue
            x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
            piece_crop = rotated[y0:y1, x0:x1]

            res = cv2.matchTemplate(self._padded_ref, piece_crop, cv2.TM_CCORR_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            tx = max_loc[0] - self._pad - x0
            ty = max_loc[1] - self._pad - y0

            matrix = base_matrix.copy()
            matrix[0, 2] += tx
            matrix[1, 2] += ty

            candidate = _warp(input_mask, matrix)
            cand_area = int(np.count_nonzero(candidate > 127))
            if cand_area == 0:
                continue
            inter = int(np.count_nonzero((candidate > 127) & (self.reference_mask > 127)))
            union = int(np.count_nonzero((candidate > 127) | (self.reference_mask > 127)))
            precision = inter / cand_area
            iou = inter / max(1, union)
            score = precision * 0.70 + iou * 0.30
            if best is None or score > best[0]:
                best = (score, matrix, rot, iou)

        if best is None:
            empty = np.zeros_like(input_mask)
            return AlignedCrop(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, 0.0, False, "alignment_failed")

        score, matrix, rotation, iou = best
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
