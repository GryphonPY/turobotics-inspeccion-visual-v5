from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .alignment import AlignedCrop


@dataclass(frozen=True)
class GeometryEvidence:
    usable: bool
    global_score: float
    area_ratio: float
    aspect_score: float
    silhouette_iou: float
    local_scores: Mapping[str, float]
    reasons: tuple[str, ...]
    reference_support: Mapping[str, float] = field(default_factory=dict)


class GeometryJudge:
    def __init__(
        self,
        reference_mask: np.ndarray,
        anchors_path: Path,
        global_min_iou: float = 0.60,
    ) -> None:
        self.reference_mask = cv2.resize(
            (reference_mask > 127).astype(np.uint8) * 255,
            (224, 224),
            interpolation=cv2.INTER_NEAREST,
        )
        raw = json.loads(anchors_path.read_text(encoding="utf-8"))
        self.anchors = {key: value for key, value in raw.items()}
        self.global_min_iou = global_min_iou
        self._anchor_masks = {
            key: self._make_anchor_mask(value) for key, value in self.anchors.items()
        }

    @staticmethod
    def _make_anchor_mask(anchor: Mapping[str, float]) -> np.ndarray:
        mask = np.zeros((224, 224), dtype=np.uint8)
        x0 = round(float(anchor["x"]) * 224)
        y0 = round(float(anchor["y"]) * 224)
        x1 = round((float(anchor["x"]) + float(anchor["width"])) * 224)
        y1 = round((float(anchor["y"]) + float(anchor["height"])) * 224)
        mask[max(0, y0) : min(224, y1), max(0, x0) : min(224, x1)] = 255
        return mask

    @staticmethod
    def _iou(first: np.ndarray, second: np.ndarray) -> float:
        first_bool = first > 127
        second_bool = second > 127
        union = np.count_nonzero(first_bool | second_bool)
        return float(np.count_nonzero(first_bool & second_bool) / max(1, union))

    def evaluate(self, aligned: AlignedCrop) -> GeometryEvidence:
        current_mask = cv2.resize(
            (aligned.mask > 127).astype(np.uint8) * 255,
            (224, 224),
            interpolation=cv2.INTER_NEAREST,
        )
        current_edges = cv2.resize(
            (aligned.edges > 0).astype(np.uint8) * 255,
            (224, 224),
            interpolation=cv2.INTER_NEAREST,
        )
        current = current_mask > 127
        reference = self.reference_mask > 127
        current_area = int(np.count_nonzero(current))
        reference_area = int(np.count_nonzero(reference))
        if current_area == 0 or reference_area == 0:
            return GeometryEvidence(False, 0.0, 0.0, 0.0, 0.0, {}, ("mask_empty",))
        silhouette_iou = self._iou(current_mask, self.reference_mask)
        area_ratio = current_area / reference_area
        _, _, current_width, current_height = cv2.boundingRect(current_mask)
        _, _, ref_width, ref_height = cv2.boundingRect(self.reference_mask)
        current_aspect = current_width / max(1, current_height)
        ref_aspect = ref_width / max(1, ref_height)
        aspect_score = float(np.clip(1.0 - abs(current_aspect - ref_aspect) / max(ref_aspect, 0.01), 0.0, 1.0))
        area_score = float(np.clip(1.0 - abs(1.0 - area_ratio) / 0.40, 0.0, 1.0))
        edge_fraction = float(np.count_nonzero(current_edges)) / max(1, current_area)
        global_score = float(0.55 * silhouette_iou + 0.25 * area_score + 0.15 * aspect_score + 0.05 * np.clip(edge_fraction * 10.0, 0.0, 1.0))
        reasons: list[str] = []
        outside_area = int(np.count_nonzero(current & (~reference)))
        outside_ratio = outside_area / max(1, current_area)
        if outside_ratio > 0.15:
            reasons.append("outside_mass_detected")
        if silhouette_iou < self.global_min_iou:
            reasons.append("silhouette_incompatible")
        if not 0.70 <= area_ratio <= 1.30:
            reasons.append("area_incompatible")
        if aspect_score < 0.80:
            reasons.append("aspect_incompatible")
        local_scores = {
            component_id: float(
                np.count_nonzero(current & (anchor_mask > 0))
                / max(1, np.count_nonzero(anchor_mask))
            )
            for component_id, anchor_mask in self._anchor_masks.items()
        }
        reference_support = {
            component_id: float(
                np.count_nonzero(current & reference & (anchor_mask > 0))
                / max(1, np.count_nonzero(reference & (anchor_mask > 0)))
            )
            for component_id, anchor_mask in self._anchor_masks.items()
        }
        return GeometryEvidence(
            not reasons,
            global_score,
            float(area_ratio),
            aspect_score,
            silhouette_iou,
            local_scores,
            tuple(reasons),
            reference_support,
        )
