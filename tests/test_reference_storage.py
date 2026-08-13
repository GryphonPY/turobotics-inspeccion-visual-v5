from __future__ import annotations

from pathlib import Path

import numpy as np

from inspection_v4.components import ReferenceSet


def test_reference_set_round_trip(tmp_path: Path) -> None:
    shape = (20, 20)
    ids = tuple(f"C{i:02d}" for i in range(1, 11))
    complete = np.zeros(shape, np.uint8)
    complete[4:16, 5:15] = 255
    reference = ReferenceSet(
        ids,
        complete,
        complete.copy(),
        {component_id: complete.copy() for component_id in ids},
        {component_id: complete.copy() for component_id in ids},
        {component_id: complete.copy() for component_id in ids},
        {component_id: 0.55 for component_id in ids},
    )
    reference.save(tmp_path)
    loaded = ReferenceSet.load(tmp_path)
    assert loaded.component_ids == ids
    assert np.array_equal(loaded.complete_mask, complete)
    assert set(loaded.missing_gray) == set(ids)
