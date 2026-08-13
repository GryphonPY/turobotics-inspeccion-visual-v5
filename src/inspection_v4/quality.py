from __future__ import annotations

import cv2
import numpy as np

from .config import BoardConfig, InspectionConfig
from .types import BoardObservation, QualityReport


def laplacian_variance(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _marker_focus(canonical: np.ndarray, board: BoardConfig) -> float:
    gray = cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY) if canonical.ndim == 3 else canonical
    values: list[float] = []
    scale = board.pixels_per_mm
    for marker in board.markers.values():
        x = round(marker["x_mm"] * scale)
        y = round(marker["y_mm"] * scale)
        size = round(marker["size_mm"] * scale)
        patch = gray[y : y + size, x : x + size]
        if patch.shape == (size, size):
            values.append(laplacian_variance(patch))
    return float(np.median(values)) if values else 0.0


def _piece_focus(canonical: np.ndarray, board: BoardConfig) -> float:
    gray = cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY) if canonical.ndim == 3 else canonical
    x, y, width, height = board.roi_rect_px
    roi = gray[y : y + height, x : x + width]
    background = np.concatenate([
        roi[:40, :].reshape(-1), roi[-40:, :].reshape(-1),
        roi[:, :40].reshape(-1), roi[:, -40:].reshape(-1),
    ])
    median = float(np.median(background))
    mad = float(np.median(np.abs(background.astype(np.float32) - median)))
    threshold = median + max(18.0, 4.0 * mad)
    mask = (roi > threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if cv2.contourArea(contour) >= roi.size * 0.01]
    if not contours:
        return 0.0
    contour = max(contours, key=cv2.contourArea)
    px, py, pw, ph = cv2.boundingRect(contour)
    margin = 12
    crop = roi[max(0, py - margin) : min(height, py + ph + margin),
               max(0, px - margin) : min(width, px + pw + margin)]
    return laplacian_variance(crop)


def _marker_samples(canonical: np.ndarray, board: BoardConfig) -> tuple[np.ndarray, np.ndarray]:
    """Sample printed white quiet zones and marker codes in canonical coordinates."""
    gray = cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY) if canonical.ndim == 3 else canonical
    white_samples: list[np.ndarray] = []
    black_samples: list[np.ndarray] = []
    scale = board.pixels_per_mm
    quiet = round(7.0 * scale)
    patch = round(50.0 * scale)
    for marker in board.markers.values():
        code_x = round(marker["x_mm"] * scale)
        code_y = round(marker["y_mm"] * scale)
        patch_x = code_x - quiet
        patch_y = code_y - quiet
        patch_image = gray[patch_y : patch_y + patch, patch_x : patch_x + patch]
        if patch_image.shape != (patch, patch):
            continue
        border = max(2, quiet // 2)
        white_samples.extend([
            patch_image[:border, :].reshape(-1),
            patch_image[-border:, :].reshape(-1),
            patch_image[:, :border].reshape(-1),
            patch_image[:, -border:].reshape(-1),
        ])
        code_size = round(marker["size_mm"] * scale)
        code = patch_image[quiet : quiet + code_size, quiet : quiet + code_size]
        black_samples.append(code.reshape(-1))
    if not white_samples:
        white_samples = [gray.reshape(-1)]
    if not black_samples:
        black_samples = [gray.reshape(-1)]
    return np.concatenate(white_samples), np.concatenate(black_samples)


def _background_contrast(canonical: np.ndarray, board: BoardConfig) -> float:
    white, black = _marker_samples(canonical, board)
    return float(np.percentile(white, 50) - np.percentile(black, 50))


def _background_clipping(canonical: np.ndarray, board: BoardConfig) -> float:
    """Measure overexposure in blank black-board strips, not expected white ink."""
    gray = cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY) if canonical.ndim == 3 else canonical
    x, y, width, height = board.roi_rect_px
    band = max(8, round(3.0 * board.pixels_per_mm))
    strips = [
        gray[y : y + band, x : x + width],
        gray[y + height - band : y + height, x : x + width],
        gray[y : y + height, x : x + band],
        gray[y : y + height, x + width - band : x + width],
    ]
    values = np.concatenate([strip.reshape(-1) for strip in strips if strip.size])
    if values.size == 0:
        return 0.0
    return float(np.mean(values >= 245))


def assess_frame(
    canonical: np.ndarray,
    observation: BoardObservation,
    board: BoardConfig,
    config: InspectionConfig,
    baseline_laplacian: float | None = None,
    previous_canonical: np.ndarray | None = None,
) -> QualityReport:
    reasons: list[str] = []
    metrics: dict[str, float] = {}
    if canonical is None or canonical.size == 0:
        return QualityReport(False, 0.0, ["canonical_empty"], metrics)

    metrics["reprojection_error_px"] = observation.reprojection_error_px
    metrics["contrast"] = _background_contrast(canonical, board)
    roi_x, roi_y, roi_width, roi_height = board.roi_rect_px
    metrics["marker_focus"] = _marker_focus(canonical, board)
    metrics["piece_focus"] = _piece_focus(canonical, board)
    # The board and the piece are coplanar. Use the stronger signal for the release
    # gate, while keeping both measurements available for diagnosis.
    metrics["laplacian"] = max(metrics["piece_focus"], metrics["marker_focus"])
    gray = cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY)
    metrics["black_fraction"] = float(np.mean(gray <= 3))
    metrics["white_fraction"] = float(np.mean(gray >= 252))
    metrics["clipped_fraction"] = _background_clipping(canonical, board)

    if observation.homography is None or observation.reason.startswith(
        ("missing_", "duplicate_")
    ):
        reasons.append("markers_incomplete")
    if observation.reprojection_error_px > min(
        board.max_reprojection_error_px, config.quality_max_reprojection_px
    ):
        reasons.append("reprojection_error")
    if metrics["contrast"] < config.quality_min_contrast:
        reasons.append("low_contrast")
    if metrics["clipped_fraction"] > config.quality_max_marker_clipped_fraction:
        reasons.append("clipping")
    if metrics["black_fraction"] > config.quality_max_black_fraction:
        reasons.append("black_clipping")
    if metrics["white_fraction"] > config.quality_max_white_fraction:
        reasons.append("white_clipping")

    baseline = baseline_laplacian or config.quality_min_laplacian
    minimum_laplacian = max(config.quality_min_laplacian, baseline * config.quality_relative_blur_floor)
    if metrics["laplacian"] < minimum_laplacian:
        reasons.append("blur")

    if previous_canonical is not None and previous_canonical.shape == canonical.shape:
        previous_gray = cv2.cvtColor(previous_canonical, cv2.COLOR_BGR2GRAY)
        current_motion = cv2.GaussianBlur(
            gray[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width], (5, 5), 0
        )
        previous_motion = cv2.GaussianBlur(
            previous_gray[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width], (5, 5), 0
        )
        metrics["motion_mean"] = float(np.mean(cv2.absdiff(current_motion, previous_motion)))
    else:
        metrics["motion_mean"] = 0.0
    if metrics["motion_mean"] > config.quality_max_motion_mean:
        reasons.append("motion")

    # Score is intentionally interpretable: each satisfied quality gate contributes equally.
    checks = [
        observation.homography is not None,
        observation.reprojection_error_px <= config.quality_max_reprojection_px,
        metrics["contrast"] >= config.quality_min_contrast,
        metrics["clipped_fraction"] <= config.quality_max_marker_clipped_fraction,
        metrics["black_fraction"] <= config.quality_max_black_fraction,
        metrics["white_fraction"] <= config.quality_max_white_fraction,
        metrics["laplacian"] >= minimum_laplacian,
    ]
    score = float(sum(checks) / len(checks))
    return QualityReport(not reasons, score, reasons, metrics)
