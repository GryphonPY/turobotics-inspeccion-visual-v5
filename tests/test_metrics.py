from __future__ import annotations

import numpy as np

from training_v5.metrics import conservative_threshold


def test_conservative_threshold_has_zero_false_passes() -> None:
    result = conservative_threshold(np.asarray([0.99, 0.98, 0.20, 0.10]), np.asarray([1, 0, 1, 0]))

    assert result.false_passes == 0
    assert result.threshold > 0.98
    assert result.false_rejects == 1


def test_threshold_marks_unresolved_overlap() -> None:
    result = conservative_threshold(np.asarray([0.9, 0.8]), np.asarray([1, 0]))

    assert result.resolved is True
