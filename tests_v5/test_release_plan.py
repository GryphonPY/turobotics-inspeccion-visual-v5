import json
from collections import Counter

from inspection_v5.contracts import Verdict
from tools.run_v5_campaign import (
    _accepted_actual,
    _campaign_metrics,
    _load_release_resume_rows,
    _write_release_result,
    release_schedule,
)


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


def test_component_defect_requires_no_pass_for_release() -> None:
    assert _accepted_actual("single_missing", Verdict.NO_PASS.value)
    assert not _accepted_actual("single_missing", Verdict.UNRELIABLE.value)
    assert not _accepted_actual("single_missing", Verdict.PASS.value)
    assert _accepted_actual("rearranged", Verdict.NO_PASS.value)
    assert not _accepted_actual("rearranged", Verdict.UNRELIABLE.value)


def test_release_metrics_allow_one_complete_false_reject_but_no_defect_error() -> None:
    complete_false_reject = {
        "scenario": "complete",
        "actual_verdict": Verdict.NO_PASS.value,
        "false_pass": False,
        "correct": False,
    }
    assert _campaign_metrics([complete_false_reject], 1, max_false_rejects=1)["release_ready"]

    defect_error = {
        "scenario": "single_missing",
        "actual_verdict": Verdict.UNRELIABLE.value,
        "false_pass": False,
        "correct": False,
    }
    assert not _campaign_metrics([defect_error], 1, max_false_rejects=1)["release_ready"]


def test_release_resume_accepts_only_a_signed_prefix(tmp_path) -> None:
    schedule = release_schedule()
    row = {
        "condition_id": schedule[0]["condition_id"],
        "scenario": schedule[0]["scenario"],
        "detail": schedule[0]["detail"],
        "actual_verdict": Verdict.PASS.value,
        "false_pass": False,
        "correct": True,
    }
    path = tmp_path / "physical_release_full_test.json"
    result = {
        "kind": "physical_release_full",
        "git_revision": "test-revision",
        "requested_count": len(schedule),
        "rows": [row],
    }
    _write_release_result(result, path)

    assert _load_release_resume_rows(path, schedule, "test-revision") == [row]

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["rows"][0]["actual_verdict"] = Verdict.NO_PASS.value
    path.write_text(json.dumps(tampered), encoding="utf-8")
    assert _load_release_resume_rows(path, schedule, "test-revision") == []
