from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import InspectionConfig
from .types import ComponentEvidence, FrameDecision, InspectionResult, Verdict


def decide_frame(
    evidence: list[ComponentEvidence], alignment_score: float, quality_score: float
) -> FrameDecision:
    if not evidence:
        return FrameDecision(Verdict.UNRELIABLE, False, "no_component_evidence", [], alignment_score, quality_score)
    hard_unreliable_reasons = {
        "alignment_failed",
        "alignment_score_low",
        "reference_empty",
    }
    if any(item.reason in hard_unreliable_reasons for item in evidence):
        return FrameDecision(
            Verdict.UNRELIABLE,
            False,
            "alignment_unreliable",
            evidence,
            alignment_score,
            quality_score,
        )
    if any(item.reason == "component_unresolved" for item in evidence):
        return FrameDecision(
            Verdict.UNRELIABLE,
            True,
            "component_unresolved",
            evidence,
            alignment_score,
            quality_score,
        )
    failed = [item.component_id for item in evidence if not item.present]
    if failed:
        return FrameDecision(
            Verdict.NO_PASS, True, f"missing:{','.join(failed)}", evidence, alignment_score, quality_score
        )
    return FrameDecision(Verdict.PASS, True, "all_components_present", evidence, alignment_score, quality_score)


@dataclass
class TemporalVoter:
    config: InspectionConfig

    def aggregate(self, frames: Iterable[FrameDecision], cycle_id: int = 0) -> InspectionResult:
        usable = [frame for frame in frames if frame.usable]
        if len(usable) < self.config.min_valid_frames:
            return InspectionResult(
                Verdict.UNRELIABLE,
                "insufficient_valid_frames",
                len(usable),
                {},
                [],
                cycle_id=cycle_id,
                diagnostics={"required_valid_frames": self.config.min_valid_frames},
            )
        usable = usable[: self.config.max_valid_frames]
        component_ids = [
            evidence.component_id for evidence in usable[0].evidence
        ]
        votes: dict[str, int] = {}
        final_evidence: list[ComponentEvidence] = []
        required = int(len(usable) * self.config.frame_vote_fraction + 0.999999)
        for component_id in component_ids:
            component_frames = [
                next(item for item in frame.evidence if item.component_id == component_id)
                for frame in usable
            ]
            count = sum(item.present for item in component_frames)
            votes[component_id] = count
            representative = max(component_frames, key=lambda item: item.score)
            final_evidence.append(
                ComponentEvidence(
                    component_id,
                    count >= required,
                    float(sum(item.score for item in component_frames) / len(component_frames)),
                    float(sum(item.occupancy_score for item in component_frames) / len(component_frames)),
                    float(sum(item.edge_score for item in component_frames) / len(component_frames)),
                    float(sum(item.advantage_score for item in component_frames) / len(component_frames)),
                    representative.threshold,
                    (
                        "component_unresolved"
                        if any(item.reason == "component_unresolved" for item in component_frames)
                        else ("" if count >= required else "temporal_vote_failed")
                    ),
                )
            )
        failed = [item.component_id for item in final_evidence if not item.present]
        unresolved = [
            item.component_id
            for frame in usable
            for item in frame.evidence
            if item.reason == "component_unresolved"
        ]
        if unresolved:
            unresolved_ids = sorted(set(unresolved))
            return InspectionResult(
                Verdict.UNRELIABLE,
                f"unresolved:{','.join(unresolved_ids)}",
                len(usable),
                votes,
                final_evidence,
                cycle_id=cycle_id,
                diagnostics={"unresolved_components": unresolved_ids},
            )
        if failed:
            verdict = Verdict.NO_PASS
            reason = f"missing:{','.join(failed)}"
        else:
            verdict = Verdict.PASS
            reason = "all_components_present_temporal_vote"
        return InspectionResult(verdict, reason, len(usable), votes, final_evidence, cycle_id=cycle_id)
