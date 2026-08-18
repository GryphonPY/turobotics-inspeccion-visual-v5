from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


def _mad(values: np.ndarray) -> float:
    median = float(np.median(values))
    return float(np.median(np.abs(values.astype(np.float32) - median)))


@dataclass(frozen=True)
class PresenceConfig:
    reference_area_px: float = 18_000.0
    margin_px: int = 20
    minimum_blob_area_px: int = 20
    morphology_open_px: int = 3
    morphology_close_px: int = 5


@dataclass(frozen=True)
class PresenceMetrics:
    occupied_ratio: float
    motion: float
    piece_focus: float
    bbox: tuple[int, int, int, int]
    mask: np.ndarray
    threshold: float
    background_median: float
    background_mad: float
    reason: str = ""


class PresenceAnalyzer:
    def __init__(self, config: PresenceConfig | None = None) -> None:
        self.config = config or PresenceConfig()

    @staticmethod
    def _gray(roi: np.ndarray) -> np.ndarray:
        if roi.ndim == 2:
            return roi.copy()
        return cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    def _threshold(self, gray: np.ndarray) -> tuple[float, float, float]:
        margin = max(1, min(self.config.margin_px, min(gray.shape[:2]) // 4))
        samples = np.concatenate(
            [
                gray[:margin, :].reshape(-1),
                gray[-margin:, :].reshape(-1),
                gray[:, :margin].reshape(-1),
                gray[:, -margin:].reshape(-1),
            ]
        )
        median = float(np.median(samples))
        background_mad = _mad(samples)
        inner = gray[margin:-margin, margin:-margin]
        otsu = float(cv2.threshold(inner, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])
        mad_offset = max(18.0, 3.5 * background_mad)
        if otsu < median + 20.0:
            threshold = median + max(32.0, mad_offset)
        else:
            threshold = max(median + mad_offset, min(otsu * 0.75, median + 36.0))
        return threshold, median, background_mad

    def _select_piece(self, mask: np.ndarray, gray: np.ndarray | None = None) -> np.ndarray:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [
            contour
            for contour in contours
            if cv2.contourArea(contour) >= self.config.minimum_blob_area_px
        ]
        if not contours:
            return np.zeros_like(mask)
        if gray is not None:
            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            gmag = np.sqrt(gx * gx + gy * gy)
            valid = []
            for contour in contours:
                c_mask = np.zeros_like(gray)
                cv2.drawContours(c_mask, [contour], -1, 255, thickness=3)
                mean_g = float(np.mean(gmag[c_mask > 0])) if np.count_nonzero(c_mask > 0) else 0.0
                if mean_g >= 18.0:
                    valid.append(contour)
            if valid:
                contours = valid
        contours.sort(key=cv2.contourArea, reverse=True)
        main = contours[0]
        x, y, width, height = cv2.boundingRect(main)
        expanded = (x - 14, y - 14, x + width + 14, y + height + 14)
        selected = [main]
        for contour in contours[1:]:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            center = (cx + cw / 2.0, cy + ch / 2.0)
            if expanded[0] <= center[0] <= expanded[2] and expanded[1] <= center[1] <= expanded[3]:
                selected.append(contour)
        result = np.zeros_like(mask)
        cv2.drawContours(result, selected, -1, 255, thickness=cv2.FILLED)
        return result

    @staticmethod
    def _focus(gray: np.ndarray, mask: np.ndarray, bbox: tuple[int, int, int, int]) -> float:
        x, y, width, height = bbox
        if width <= 4 or height <= 4:
            return 0.0
        crop = gray[y : y + height, x : x + width]
        crop_mask = mask[y : y + height, x : x + width]
        if cv2.countNonZero(crop_mask) < 10:
            return 0.0
        values = cv2.Laplacian(crop, cv2.CV_64F)[crop_mask > 0]
        return float(np.var(values)) if values.size else 0.0

    def measure(self, roi: np.ndarray, previous_roi: np.ndarray | None = None) -> PresenceMetrics:
        if roi is None or roi.size == 0:
            return PresenceMetrics(0.0, 0.0, 0.0, (0, 0, 0, 0), np.zeros((1, 1), np.uint8), 0.0, 0.0, 0.0, "roi_empty")
        gray = self._gray(roi)
        threshold, median, background_mad = self._threshold(gray)
        mask = (gray > threshold).astype(np.uint8) * 255
        margin = max(1, min(self.config.margin_px, min(gray.shape[:2]) // 4))
        interior = np.zeros_like(mask)
        interior[margin:-margin, margin:-margin] = 255
        mask = cv2.bitwise_and(mask, interior)
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (self.config.morphology_open_px, self.config.morphology_open_px),
            ),
        )
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (self.config.morphology_close_px, self.config.morphology_close_px),
            ),
        )
        selected = self._select_piece(mask, gray)
        if np.count_nonzero(selected > 0):
            mean_intensity = float(np.mean(gray[selected > 0]))
            if mean_intensity < median + 25.0:
                selected = np.zeros_like(mask)
        area = int(cv2.countNonZero(selected))
        occupied_ratio = min(1.0, area / max(1.0, self.config.reference_area_px))
        ys, xs = np.where(selected > 0)
        if not len(xs) or occupied_ratio < 0.08:
            bbox = (0, 0, 0, 0)
            reason = "piece_not_found"
        else:
            bbox = (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
            reason = ""
        if previous_roi is None or previous_roi.size == 0:
            motion = 0.0
        else:
            previous_gray = self._gray(previous_roi)
            if previous_gray.shape != gray.shape:
                motion = 0.0
            else:
                motion_gray = cv2.GaussianBlur(gray, (3, 3), 0)
                previous_motion_gray = cv2.GaussianBlur(previous_gray, (3, 3), 0)
                margin = max(1, min(self.config.margin_px, min(gray.shape[:2]) // 4))
                difference = cv2.absdiff(motion_gray, previous_motion_gray)[margin:-margin, margin:-margin]
                motion = float(np.mean(difference))
        return PresenceMetrics(
            occupied_ratio,
            motion,
            self._focus(gray, selected, bbox),
            bbox,
            selected,
            threshold,
            median,
            background_mad,
            reason,
        )
