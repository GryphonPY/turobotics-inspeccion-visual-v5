from __future__ import annotations

import cv2
import numpy as np

from .config import BoardConfig, InspectionConfig
from .types import AlignedPiece, PieceObservation


def _mad(values: np.ndarray) -> float:
    median = float(np.median(values))
    return float(np.median(np.abs(values.astype(np.float32) - median)))


class PieceSegmenter:
    def __init__(self, board: BoardConfig, config: InspectionConfig) -> None:
        self.board = board
        self.config = config

    def segment(self, roi: np.ndarray) -> PieceObservation:
        if roi is None or roi.size == 0:
            return PieceObservation(np.zeros((1, 1), np.uint8), np.zeros((1, 1), np.uint8), 0,
                                    (0, 0, 0, 0), (0.0, 0.0), False, "roi_empty")
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi.copy()
        h, w = gray.shape[:2]
        margin = max(1, int(self.config.piece_margin_mm * self.board.pixels_per_mm))
        background_samples = np.concatenate(
            [gray[:margin, :].reshape(-1), gray[-margin:, :].reshape(-1),
             gray[:, :margin].reshape(-1), gray[:, -margin:].reshape(-1)]
        )
        median = float(np.median(background_samples))
        threshold = median + max(18.0, 4.0 * _mad(background_samples))
        mask = (gray > threshold).astype(np.uint8) * 255
        # The printed guide is near the boundary; enforcing the physical placement margin removes it.
        interior = np.zeros_like(mask)
        interior[margin : h - margin, margin : w - margin] = 255
        mask = cv2.bitwise_and(mask, interior)
        open_size = max(1, int(self.config.morphology_open_px))
        close_size = max(1, int(self.config.morphology_close_px))
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_size, open_size)),
        )
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size)),
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(self.config.min_component_area_px, int(roi.size * 0.00001))
        contours = [c for c in contours if cv2.contourArea(c) >= min_area]
        if not contours:
            return PieceObservation(mask, gray, 0, (0, 0, 0, 0), (0.0, 0.0), False, "piece_not_found")

        contours.sort(key=cv2.contourArea, reverse=True)
        main = contours[0]
        x, y, bw, bh = cv2.boundingRect(main)
        expanded = (x - 0.25 * bw, y - 0.25 * bh, x + 1.25 * bw, y + 1.25 * bh)
        selected = [main]
        for contour in contours[1:]:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            center = (cx + cw / 2, cy + ch / 2)
            if expanded[0] <= center[0] <= expanded[2] and expanded[1] <= center[1] <= expanded[3]:
                selected.append(contour)
        selected_mask = np.zeros_like(mask)
        cv2.drawContours(selected_mask, selected, -1, 255, thickness=cv2.FILLED)
        area = int(cv2.countNonZero(selected_mask))
        roi_area = h * w
        fraction = area / max(1, roi_area)
        if fraction < self.config.min_piece_area_fraction:
            reason = "piece_too_small"
            valid = False
        elif fraction > self.config.max_piece_area_fraction:
            reason = "piece_too_large"
            valid = False
        else:
            reason = ""
            valid = True
        ys, xs = np.where(selected_mask > 0)
        bbox = (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
        moments = cv2.moments(selected_mask)
        centroid = (
            float(moments["m10"] / moments["m00"]) if moments["m00"] else 0.0,
            float(moments["m01"] / moments["m00"]) if moments["m00"] else 0.0,
        )
        border_touch = bbox[0] < margin or bbox[1] < margin or bbox[0] + bbox[2] > w - margin or bbox[1] + bbox[3] > h - margin
        if border_touch:
            valid = False
            reason = "piece_too_close_to_boundary"
        return PieceObservation(selected_mask, gray, area, bbox, centroid, valid, reason)


def _principal_angle(mask: np.ndarray) -> float:
    ys, xs = np.where(mask > 0)
    if len(xs) < 3:
        return 0.0
    points = np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])
    points -= points.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(points, full_matrices=False)
    vector = vt[0]
    return float(np.degrees(np.arctan2(vector[1], vector[0])))


def _warp(image: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR)


class PieceAligner:
    """Align a detected piece to a complete reference while accepting arbitrary in-plane rotation."""

    def __init__(self, alignment_min_score: float = 0.45) -> None:
        self.alignment_min_score = alignment_min_score

    @staticmethod
    def _overlap(candidate: np.ndarray, reference: np.ndarray) -> float:
        candidate_bool = candidate > 0
        reference_bool = reference > 0
        candidate_area = np.count_nonzero(candidate_bool)
        if candidate_area == 0 or not np.any(reference_bool):
            return 0.0
        # Alignment is a pose gate, not a completeness gate. Precision deliberately
        # tolerates a legitimate missing component; component evidence evaluates the
        # missing area after pose normalization. Extra/noisy pixels still reduce score.
        intersection = np.count_nonzero(candidate_bool & reference_bool)
        return float(intersection / candidate_area)

    def align(
        self, piece: PieceObservation, reference_mask: np.ndarray, reference_gray: np.ndarray | None = None
    ) -> AlignedPiece:
        if not piece.valid or cv2.countNonZero(piece.mask) == 0:
            empty = np.zeros_like(piece.mask)
            return AlignedPiece(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, False, piece.reason)
        ref_moments = cv2.moments(reference_mask)
        if ref_moments["m00"] == 0:
            empty = np.zeros_like(piece.mask)
            return AlignedPiece(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, False, "reference_empty")
        ref_center = np.array([
            ref_moments["m10"] / ref_moments["m00"], ref_moments["m01"] / ref_moments["m00"]
        ])
        angle = _principal_angle(piece.mask)
        ref_angle = _principal_angle(reference_mask)
        best: tuple[float, np.ndarray, float] | None = None
        for flip in (0.0, 180.0):
            rotation = ref_angle - angle + flip
            radians = np.deg2rad(rotation)
            cos, sin = np.cos(radians), np.sin(radians)
            cx, cy = piece.centroid
            matrix = np.array([[cos, -sin, 0.0], [sin, cos, 0.0]], dtype=np.float32)
            matrix[:, 2] = np.array([cx, cy], dtype=np.float32) - matrix[:, :2] @ np.array([cx, cy], dtype=np.float32)
            rotated_mask = _warp(piece.mask, matrix)
            moments = cv2.moments(rotated_mask)
            if moments["m00"] == 0:
                continue
            rotated_center = np.array([
                moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
            ])
            matrix[:, 2] += (ref_center - rotated_center).astype(np.float32)
            aligned_mask = _warp(piece.mask, matrix)
            score = self._overlap(aligned_mask, reference_mask)
            if best is None or score > best[0]:
                best = (score, matrix, rotation)
        if best is None:
            empty = np.zeros_like(piece.mask)
            return AlignedPiece(empty, empty, empty, np.eye(2, 3, dtype=np.float32), 0.0, 0.0, False, "alignment_failed")
        score, matrix, rotation = best
        aligned_mask = _warp(piece.mask, matrix)
        aligned_gray = _warp(piece.gray, matrix)
        edges = cv2.Canny(aligned_gray, 40, 120)
        valid = score >= self.alignment_min_score
        return AlignedPiece(
            aligned_mask, aligned_gray, edges, matrix, float(rotation % 360.0), score, valid,
            "" if valid else "alignment_score_low",
        )
