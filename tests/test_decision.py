from __future__ import annotations

from pathlib import Path

from inspection_v4.config import load_configs
from inspection_v4.decision import TemporalVoter, decide_frame
from inspection_v4.types import ComponentEvidence, FrameDecision, Verdict


ROOT = Path(__file__).resolve().parents[1]


def evidence(present: bool) -> list[ComponentEvidence]:
    return [ComponentEvidence(f"C{i:02d}", present, 0.9 if present else 0.1, 0.9 if present else 0.1, 0.9 if present else 0.1, 0.9 if present else 0.1, 0.55) for i in range(1, 11)]


def test_frame_decision_requires_all_components() -> None:
    result = decide_frame(evidence(True), 0.9, 1.0)
    assert result.verdict == Verdict.PASS
    failed = evidence(True)
    failed[3] = ComponentEvidence("C04", False, 0.1, 0.1, 0.1, 0.1, 0.55, "component_missing")
    result = decide_frame(failed, 0.9, 1.0)
    assert result.verdict == Verdict.NO_PASS
    assert result.reason == "missing:C04"


def test_temporal_voter_needs_conservative_component_majority() -> None:
    _, config, _ = load_configs(ROOT)
    voter = TemporalVoter(config)
    frames = [FrameDecision(Verdict.PASS, True, "ok", evidence(True), 0.9, 1.0) for _ in range(10)]
    frames[-1] = FrameDecision(Verdict.NO_PASS, True, "missing:C04", [*evidence(True)[:3], *[ComponentEvidence("C04", False, 0.1, 0.1, 0.1, 0.1, 0.55)]] + evidence(True)[4:], 0.9, 1.0)
    result = voter.aggregate(frames)
    assert result.verdict == Verdict.PASS
    assert result.component_votes["C04"] == 9


def test_temporal_voter_rejects_insufficient_frames() -> None:
    _, config, _ = load_configs(ROOT)
    result = TemporalVoter(config).aggregate(
        [FrameDecision(Verdict.PASS, True, "ok", evidence(True), 0.9, 1.0) for _ in range(2)]
    )
    assert result.verdict == Verdict.UNRELIABLE
    assert result.reason == "insufficient_valid_frames"


def test_alignment_failure_is_not_counted_as_a_missing_component() -> None:
    failed = [
        ComponentEvidence("C01", False, 0.0, 0.0, 0.0, 0.0, 0.55, "alignment_score_low")
    ]
    result = decide_frame(failed, 0.2, 1.0)
    assert result.verdict == Verdict.UNRELIABLE
    assert result.usable is False


def test_unresolved_component_is_not_released_as_a_pass() -> None:
    failed = [
        ComponentEvidence("C01", False, 0.9, 0.9, 0.9, 0.9, 0.9, "component_unresolved")
    ]
    result = decide_frame(failed, 0.9, 1.0)
    assert result.verdict == Verdict.UNRELIABLE
    assert result.reason == "component_unresolved"
    assert result.usable is True


def test_temporal_voter_reports_unresolved_calibration() -> None:
    _, config, _ = load_configs(ROOT)
    frame_evidence = evidence(True)
    frame_evidence[0] = ComponentEvidence(
        "C01", False, 0.9, 0.9, 0.9, 0.9, 0.9, "component_unresolved"
    )
    frames = [FrameDecision(Verdict.UNRELIABLE, True, "alignment_unreliable", frame_evidence, 0.9, 1.0) for _ in range(9)]
    result = TemporalVoter(config).aggregate(frames)
    assert result.verdict == Verdict.UNRELIABLE
    assert result.reason == "unresolved:C01"
