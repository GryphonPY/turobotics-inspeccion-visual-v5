from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from inspection_v4.components import ComponentEvaluator, ReferenceBuilder
from inspection_v4.config import load_configs
from inspection_v4.types import AlignedPiece


def _piece(mask: np.ndarray) -> AlignedPiece:
    gray = mask.copy()
    return AlignedPiece(mask, gray, cv2.Canny(gray, 40, 120), np.eye(2, 3, dtype=np.float32), 0.0, 1.0, True)


def test_builder_creates_ten_distinct_regions_from_controlled_states() -> None:
    root = Path(__file__).resolve().parents[1]
    _, inspection, _ = load_configs(root)
    complete = np.zeros((300, 160), np.uint8)
    component_masks: dict[str, np.ndarray] = {}
    for index, component_id in enumerate(inspection.component_ids):
        x = 10 + (index % 2) * 75
        y = 10 + (index // 2) * 55
        complete[y : y + 42, x : x + 60] = 255
        component = np.zeros_like(complete)
        component[y : y + 42, x : x + 60] = 255
        component_masks[component_id] = component
    states: dict[str, list[AlignedPiece]] = {"OK": [_piece(complete) for _ in range(5)]}
    for component_id in inspection.component_ids:
        states[f"{component_id}_MISSING"] = [
            _piece(cv2.subtract(complete, component_masks[component_id])) for _ in range(5)
        ]
    reference = ReferenceBuilder(inspection.component_ids).build(states)
    assert set(reference.component_regions) == set(inspection.component_ids)
    assert all(cv2.countNonZero(region) > 25 for region in reference.component_regions.values())


def test_evaluator_distinguishes_complete_and_each_missing_component() -> None:
    root = Path(__file__).resolve().parents[1]
    _, inspection, _ = load_configs(root)
    complete = np.zeros((300, 160), np.uint8)
    component_masks: dict[str, np.ndarray] = {}
    for index, component_id in enumerate(inspection.component_ids):
        x = 10 + (index % 2) * 75
        y = 10 + (index // 2) * 55
        complete[y : y + 42, x : x + 60] = 255
        component = np.zeros_like(complete)
        component[y : y + 42, x : x + 60] = 255
        component_masks[component_id] = component
    states: dict[str, list[AlignedPiece]] = {"OK": [_piece(complete) for _ in range(5)]}
    for component_id, mask in component_masks.items():
        states[f"{component_id}_MISSING"] = [_piece(cv2.subtract(complete, mask)) for _ in range(5)]
    reference = ReferenceBuilder(inspection.component_ids).build(states)
    evaluator = ComponentEvaluator(reference, inspection)
    complete_evidence = evaluator.evaluate(_piece(complete))
    assert all(item.present for item in complete_evidence)
    for component_id, mask in component_masks.items():
        evidence = evaluator.evaluate(_piece(cv2.subtract(complete, mask)))
        by_id = {item.component_id: item for item in evidence}
        assert by_id[component_id].present is False
