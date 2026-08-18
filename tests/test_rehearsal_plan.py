from __future__ import annotations

from tools.run_v5_campaign import _PHYSICAL_EXPECTED


def test_rehearsal_scenarios_have_safe_expected_verdicts() -> None:
    assert _PHYSICAL_EXPECTED["complete"] == "PASS"
    assert _PHYSICAL_EXPECTED["single_missing"] == "NO_PASS"
    assert all(value != "PASS" for key, value in _PHYSICAL_EXPECTED.items() if key != "complete")
