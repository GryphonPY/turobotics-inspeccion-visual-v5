from __future__ import annotations

import numpy as np

import inspection_v4.components as component_module
from inspection_v4.components import ComponentEvaluator, ReferenceSet
from inspection_v4.config import InspectionConfig, load_configs
from inspection_v4.types import AlignedPiece


def _reference(config: InspectionConfig) -> ReferenceSet:
    shape = (64, 64)
    complete = np.zeros(shape, np.uint8)
    complete[8:56, 8:56] = 255
    regions: dict[str, np.ndarray] = {}
    missing_masks: dict[str, np.ndarray] = {}
    missing_gray: dict[str, np.ndarray] = {}
    for index, component_id in enumerate(config.component_ids):
        region = np.zeros(shape, np.uint8)
        x = 8 + (index % 5) * 9
        y = 8 + (index // 5) * 24
        region[y : y + 16, x : x + 8] = 255
        regions[component_id] = region
        absent = complete.copy()
        absent[region > 0] = 0
        missing_masks[component_id] = absent
        missing_gray[component_id] = absent
    return ReferenceSet(
        config.component_ids,
        complete,
        complete.copy(),
        regions,
        missing_masks,
        missing_gray,
        {component_id: 0.4 for component_id in config.component_ids},
    )


def test_current_gray_is_normalized_once_per_evaluated_frame(monkeypatch) -> None:
    source_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    _, config, _ = load_configs(source_root)
    calls = 0
    original = component_module._normalized_gray

    def counted(image: np.ndarray) -> np.ndarray:
        nonlocal calls
        calls += 1
        return original(image)

    monkeypatch.setattr(component_module, "_normalized_gray", counted)
    evaluator = ComponentEvaluator(_reference(config), config)
    calls = 0
    complete = evaluator.reference.complete_mask
    aligned = AlignedPiece(
        complete,
        complete.copy(),
        np.zeros_like(complete),
        np.eye(2, 3, dtype=np.float32),
        0.0,
        1.0,
        True,
    )

    evidence = evaluator.evaluate(aligned)

    assert len(evidence) == 10
    assert calls == 1


def test_cached_geometry_matches_reference_calculation() -> None:
    source_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    _, config, _ = load_configs(source_root)
    reference = _reference(config)
    evaluator = ComponentEvaluator(reference, config)
    mask = reference.complete_mask.copy()
    mask[14:20, 14:20] = 96
    aligned = AlignedPiece(
        mask,
        reference.complete_gray.copy(),
        np.zeros_like(mask),
        np.eye(2, 3, dtype=np.float32),
        0.0,
        1.0,
        True,
    )

    evidence = evaluator.evaluate(aligned)

    for item in evidence:
        expected = ComponentEvaluator._score_only(reference, aligned, item.component_id)
        actual = (
            item.score,
            item.occupancy_score,
            item.edge_score,
            item.advantage_score,
        )
        assert np.allclose(actual, expected, atol=1e-7)
