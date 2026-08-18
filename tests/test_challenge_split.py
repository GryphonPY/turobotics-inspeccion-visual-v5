from __future__ import annotations

from tools.capture_challenge_v5 import _plan, _select_capture_target


def test_challenge_plan_has_sixty_cycles_and_holdout_boundary() -> None:
    plan = _plan()

    assert len(plan) == 60
    assert plan[0]["expected_verdict"] == "PASS"
    assert plan[20]["missing_ids"] == ["C01"]
    assert plan[30]["condition_id"] == "C06_MISSING_1"
    assert plan[40]["condition_id"] == "REARRANGED_01"
    assert plan[50]["expected_verdict"] == "UNRELIABLE"


def test_repeat_uses_previous_condition_without_replacing_scheduled_condition() -> None:
    plan = _plan()
    previous = plan[0]
    scheduled = plan[1]

    target, is_repeat = _select_capture_target(scheduled, previous, repeat_requested=True)

    assert target is previous
    assert is_repeat is True
    assert scheduled["condition_id"] == "OK_02"


def test_repeat_without_previous_capture_keeps_scheduled_condition() -> None:
    scheduled = _plan()[0]

    target, is_repeat = _select_capture_target(scheduled, None, repeat_requested=True)

    assert target is scheduled
    assert is_repeat is False
