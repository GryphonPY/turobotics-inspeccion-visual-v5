from __future__ import annotations

from pathlib import Path

from inspection_v4.config import load_configs
from inspection_v4.types import FrameDecision, Verdict
from inspection_v4.workflow import InspectionWorkflow, WorkflowCounters, WorkflowState

ROOT = Path(__file__).resolve().parents[1]


def _usable_decision() -> FrameDecision:
    return FrameDecision(Verdict.PASS, True, "ok", [], 0.9, 1.0)


def test_collection_waits_for_required_frames_regardless_of_elapsed_time() -> None:
    _, config, _ = load_configs(ROOT)
    workflow = object.__new__(InspectionWorkflow)
    workflow.config = config
    workflow.collection_started = 0.0
    workflow.frame_decisions = [_usable_decision() for _ in range(8)]

    assert not workflow._collection_ready()

    workflow.frame_decisions.append(_usable_decision())
    assert workflow._collection_ready()


def test_persistent_alignment_failures_become_a_conservative_reject() -> None:
    _, config, _ = load_configs(ROOT)
    workflow = object.__new__(InspectionWorkflow)
    workflow.config = config
    workflow.alignment_failures = 0

    for _ in range(config.min_valid_frames - 1):
        assert not workflow._note_alignment_failure()

    assert workflow._note_alignment_failure()
    workflow._reset_alignment_failures()
    assert workflow.alignment_failures == 0


def test_motion_restarts_stabilization_without_mixing_votes() -> None:
    _, config, _ = load_configs(ROOT)
    workflow = object.__new__(InspectionWorkflow)
    workflow.config = config
    workflow.state = WorkflowState.COLLECTING
    workflow.frame_decisions = [_usable_decision() for _ in range(4)]
    workflow.alignment_failures = 3
    workflow.collection_started = 1.0
    workflow.last_collected_at = 2.0

    workflow._restart_after_motion(now=20.0)

    assert workflow.state == WorkflowState.STABILIZING
    assert workflow.frame_decisions == []
    assert workflow.alignment_failures == 0
    assert workflow.stable_since == 20.0
    assert workflow.collection_started is None
    assert workflow.last_collected_at is None


def test_incompatible_shape_is_recorded_as_no_pass() -> None:
    workflow = object.__new__(InspectionWorkflow)
    workflow.frame_decisions = []
    workflow.alignment_failures = 9
    workflow.cycle_id = 4
    workflow.inspection_started = 10.0
    workflow.counters = WorkflowCounters()

    result = workflow._finish_incompatible(now=12.5)

    assert result.verdict == Verdict.NO_PASS
    assert result.reason == "shape_incompatible"
    assert result.diagnostics["alignment_failures"] == 9
    assert result.elapsed_seconds == 2.5
    assert workflow.state == WorkflowState.DECIDED
    assert workflow.counters.total == 1
    assert workflow.counters.failed == 1
    assert workflow.counters.unreliable == 0
