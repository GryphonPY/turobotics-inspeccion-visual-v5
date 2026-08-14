from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    false_passes: int
    false_rejects: int
    resolved: bool


def conservative_threshold(probabilities: np.ndarray, labels: np.ndarray) -> ThresholdResult:
    probabilities = np.asarray(probabilities, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int8)
    negative = probabilities[labels == 0]
    positive = probabilities[labels == 1]
    if not len(negative) or not len(positive):
        raise ValueError("Threshold calibration requires both classes")
    threshold = float(np.nextafter(np.max(negative), 1.0))
    predictions = probabilities >= threshold
    false_passes = int(np.count_nonzero((predictions == 1) & (labels == 0)))
    false_rejects = int(np.count_nonzero((predictions == 0) & (labels == 1)))
    return ThresholdResult(
        threshold,
        false_passes,
        false_rejects,
        bool(false_passes == 0 and threshold <= 1.0 and np.any(positive >= threshold)),
    )


def component_metrics(probabilities: np.ndarray, labels: np.ndarray) -> dict[str, ThresholdResult]:
    probabilities = np.asarray(probabilities)
    labels = np.asarray(labels)
    if probabilities.ndim != 2 or probabilities.shape[1] != 11:
        raise ValueError(f"Expected (N,11), got {probabilities.shape}")
    return {
        f"C{index + 1:02d}" if index < 10 else "GLOBAL": conservative_threshold(
            probabilities[:, index], labels[:, index]
        )
        for index in range(11)
    }
