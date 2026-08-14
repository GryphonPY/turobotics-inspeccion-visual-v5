from __future__ import annotations

from tools.capture_challenge_v5 import _plan


def test_challenge_plan_has_sixty_cycles_and_holdout_boundary() -> None:
    plan = _plan()

    assert len(plan) == 60
    assert plan[0]["expected_verdict"] == "PASS"
    assert plan[20]["missing_ids"] == ["C01"]
    assert plan[30]["condition_id"] == "C06_MISSING_1"
    assert plan[40]["condition_id"] == "REARRANGED_01"
    assert plan[50]["expected_verdict"] == "UNRELIABLE"
