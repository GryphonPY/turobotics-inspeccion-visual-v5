from __future__ import annotations

from pathlib import Path

import pytest

from training_v5.dataset import Sample, group_split, labels_for_state


def sample(round_id: int, state: str) -> Sample:
    return Sample(Path(f"frame_{round_id}_{state}.png"), "s", round_id, f"s:{round_id}:{state}", state, labels_for_state(state), "sha", "dhash")


def test_group_split_never_leaks_round_or_clip() -> None:
    samples = [sample(1, "OK"), sample(2, "OK"), sample(3, "C01_MISSING")]

    split = group_split(samples, train_rounds={1, 2}, validation_rounds={3})

    train_groups = {item.clip_id for item in split.train}
    validation_groups = {item.clip_id for item in split.validation}
    assert train_groups.isdisjoint(validation_groups)


def test_labels_for_missing_component_are_multilabel() -> None:
    labels = labels_for_state("C04_MISSING")

    assert len(labels) == 10
    assert labels[3] == 0
    assert sum(labels) == 9


def test_group_split_rejects_unassigned_round() -> None:
    with pytest.raises(ValueError, match="not assigned"):
        group_split([sample(7, "OK")], train_rounds={1}, validation_rounds={6})


def test_group_split_can_leave_holdout_round_unassigned() -> None:
    split = group_split(
        [sample(1, "OK"), sample(7, "OK")],
        train_rounds={1},
        validation_rounds={6},
        allow_unassigned=True,
    )

    assert len(split.train) == 1
    assert len(split.validation) == 0
