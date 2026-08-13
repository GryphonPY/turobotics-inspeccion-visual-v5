from __future__ import annotations

"""Optional CPU fallback for unresolved component regions.

This module is deliberately dormant until a reference calibration proves that a
component cannot be separated with geometry alone. It has no dependency on
Ultralytics or a GPU.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import joblib
import numpy as np


def _features(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    edges = cv2.Canny(gray, 40, 120)
    hog = cv2.HOGDescriptor(
        (64, 64), (16, 16), (8, 8), (8, 8), 9, 1, -1.0, 0, 0.2, False, 64, True
    )
    hog_channels = [hog.compute(channel).reshape(-1) for channel in (gray, mask, edges)]
    return np.concatenate([
        *[channel.astype(np.float32) for channel in hog_channels],
    ])


@dataclass
class HOGSVMComponentModel:
    component_id: str
    model: object

    @classmethod
    def train(cls, component_id: str, images: list[np.ndarray], labels: list[int]) -> "HOGSVMComponentModel":
        if len(images) != len(labels) or len(set(labels)) != 2:
            raise ValueError("El modelo auxiliar requiere imágenes y dos clases")
        from sklearn.svm import SVC

        matrix = np.stack([_features(image) for image in images])
        model = SVC(kernel="linear", probability=True, class_weight="balanced", random_state=42)
        model.fit(matrix, np.asarray(labels, dtype=np.int32))
        return cls(component_id, model)

    def predict_present_score(self, image: np.ndarray) -> float:
        probabilities = self.model.predict_proba(_features(image)[None, :])[0]
        classes = list(self.model.classes_)
        return float(probabilities[classes.index(1)])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"component_id": self.component_id, "model": self.model}, path)

    @classmethod
    def load(cls, path: Path) -> "HOGSVMComponentModel":
        payload = joblib.load(path)
        return cls(payload["component_id"], payload["model"])
