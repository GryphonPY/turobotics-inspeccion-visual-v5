from __future__ import annotations

from pathlib import Path

from inspection_v5.contracts import ComponentPublicState, Verdict
from inspection_v5.fusion import AdaptiveVoter, HybridJudge
from inspection_v5.geometry_judge import GeometryEvidence
from inspection_v5.model_runtime import ModelEvidence

ROOT = Path(__file__).resolve().parents[1]


def geometry(usable: bool = True) -> GeometryEvidence:
    return GeometryEvidence(
        usable,
        0.98 if usable else 0.4,
        1.0,
        1.0,
        0.95 if usable else 0.4,
        {f"C{i:02d}": 0.8 for i in range(1, 11)},
        () if usable else ("silhouette_incompatible",),
    )


def model(values: tuple[float, ...], global_value: float = 0.9) -> ModelEvidence:
    return ModelEvidence(values, global_value, 1.0, "hash")


def test_disagreement_never_produces_pass() -> None:
    judge = HybridJudge(ROOT / "config" / "v5" / "decision.json")
    verdict = judge.evaluate(geometry(), model((0.99,) * 9 + (0.1,)))

    assert verdict.verdict is not Verdict.PASS
    assert any("judge_disagreement" in reason for reason in verdict.reasons)


def test_complete_components_can_pass_when_global_head_is_unreliable() -> None:
    judge = HybridJudge(ROOT / "config" / "v5" / "decision.json")
    evidence = GeometryEvidence(
        usable=False,
        global_score=0.74,
        area_ratio=1.18,
        aspect_score=0.95,
        silhouette_iou=0.73,
        local_scores={f"C{i:02d}": 0.80 for i in range(1, 11)},
        reasons=("silhouette_incompatible",),
    )

    verdict = judge.evaluate(evidence, model((0.99,) * 10, global_value=0.0))

    assert verdict.verdict is Verdict.PASS


def test_complete_components_can_pass_at_rotated_shape_score() -> None:
    judge = HybridJudge(ROOT / "config" / "v5" / "decision.json")
    verdict = judge.evaluate(
        GeometryEvidence(
            usable=False,
            global_score=0.64,
            area_ratio=1.07,
            aspect_score=0.82,
            silhouette_iou=0.62,
            local_scores={f"C{i:02d}": 0.80 for i in range(1, 11)},
            reasons=("silhouette_incompatible", "aspect_incompatible"),
        ),
        model((0.99,) * 10, global_value=0.0),
    )

    assert verdict.verdict is Verdict.PASS


def test_missing_component_still_blocks_component_only_pass() -> None:
    judge = HybridJudge(ROOT / "config" / "v5" / "decision.json")
    local_scores = {f"C{i:02d}": 0.80 for i in range(1, 11)}
    local_scores["C01"] = 0.20
    probabilities = (0.0,) + (0.99,) * 9
    evidence = GeometryEvidence(
        usable=False,
        global_score=0.74,
        area_ratio=1.0,
        aspect_score=0.95,
        silhouette_iou=0.73,
        local_scores=local_scores,
        reasons=("silhouette_incompatible",),
    )

    verdict = judge.evaluate(evidence, model(probabilities, global_value=0.0))

    assert verdict.verdict is Verdict.NO_PASS


def test_voter_closes_after_five_unanimous_passes() -> None:
    voter = AdaptiveVoter()
    frame = type("Frame", (), {"verdict": Verdict.PASS, "global_score": 0.95, "components": (ComponentPublicState.PRESENT,) * 10})()

    results = [voter.add(frame) for _ in range(5)]

    assert results[-1] is not None
    assert results[-1].verdict is Verdict.PASS


def test_voter_passes_complete_components_when_frame_quality_is_uncertain() -> None:
    voter = AdaptiveVoter(min_frames=5, max_frames=9)
    frame = type(
        "Frame",
        (),
        {
            "verdict": Verdict.UNRELIABLE,
            "global_score": 0.40,
            "components": (ComponentPublicState.PRESENT,) * 10,
        },
    )()

    results = [voter.add(frame) for _ in range(5)]

    assert results[-1] is not None
    assert results[-1].verdict is Verdict.PASS
    assert results[-1].components == (ComponentPublicState.PRESENT,) * 10


def test_voter_waits_for_more_when_one_frame_is_uncertain() -> None:
    voter = AdaptiveVoter()
    pass_frame = type("Frame", (), {"verdict": Verdict.PASS, "global_score": 0.95, "components": (ComponentPublicState.PRESENT,) * 10})()
    uncertain = type("Frame", (), {"verdict": Verdict.UNRELIABLE, "global_score": 0.5, "components": (ComponentPublicState.UNKNOWN,) * 10})()

    assert voter.add(pass_frame) is None
    assert voter.add(uncertain) is None


def test_voter_emits_only_one_result_per_cycle() -> None:
    voter = AdaptiveVoter(min_frames=5, max_frames=9)
    frame = type("Frame", (), {"verdict": Verdict.PASS, "global_score": 0.95, "components": (ComponentPublicState.PRESENT,) * 10})()

    results = [voter.add(frame) for _ in range(6)]

    assert results[4] is not None
    assert results[5] is None
