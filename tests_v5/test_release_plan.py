from collections import Counter

from inspection_v5.contracts import Verdict
from tools.run_v5_campaign import _accepted_actual, release_schedule


def test_full_release_schedule_has_all_required_physical_cases() -> None:
    schedule = release_schedule()
    counts = Counter(row["scenario"] for row in schedule)

    assert len(schedule) == 440
    assert counts["complete"] == 100
    assert counts["single_missing"] == 200
    assert counts["double_missing"] == 20
    assert counts["rearranged"] == 20
    assert counts["outside"] == 20
    assert counts["hand"] == 20
    assert counts["marker"] == 20
    assert counts["blur"] == 20
    assert counts["bad_light"] == 20


def test_missing_schedule_identifies_each_component_twenty_times() -> None:
    schedule = release_schedule()
    missing = [row["detail"] for row in schedule if row["scenario"] == "single_missing"]
    counts = Counter(missing)

    assert set(counts) == {f"C{index:02d}" for index in range(1, 11)}
    assert all(count == 20 for count in counts.values())


def test_unsafe_capture_can_be_rejected_without_being_exactly_unreliable() -> None:
    assert _accepted_actual("hand", Verdict.UNRELIABLE.value)
    assert _accepted_actual("hand", Verdict.NO_PASS.value)
    assert not _accepted_actual("hand", Verdict.PASS.value)
    assert _accepted_actual("complete", Verdict.PASS.value)
    assert not _accepted_actual("complete", Verdict.NO_PASS.value)
