from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import ComponentPublicState, Verdict
from .geometry_judge import GeometryEvidence
from .model_runtime import ModelEvidence


@dataclass(frozen=True)
class FrameVerdict:
    verdict: Verdict
    components: tuple[ComponentPublicState, ...]
    scores: tuple[float, ...]
    global_score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CycleVerdict:
    verdict: Verdict
    components: tuple[ComponentPublicState, ...]
    frames_used: int
    reasons: tuple[str, ...]


def _as_float_map(raw: object, names: tuple[str, ...], default: float) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {name: default for name in names}
    return {name: float(raw.get(name, default)) for name in names}


class HybridJudge:
    def __init__(self, decision_path: Path) -> None:
        config = json.loads(decision_path.read_text(encoding="utf-8"))
        names = tuple(f"C{index:02d}" for index in range(1, 11))
        self.names = names
        self.high = _as_float_map(config.get("component_high"), names, 0.90)
        self.low = _as_float_map(config.get("component_low"), names, 0.20)
        self.global_high = float(config.get("global_high", 0.80))
        self.global_low = float(config.get("global_low", 0.25))
        self.local_high = _as_float_map(config.get("local_high"), names, 0.45)
        self.local_low = _as_float_map(config.get("local_low"), names, 0.20)
        self.geometry_min = float(config.get("geometry_min", 0.85))
        self.component_model_floor = float(config.get("component_model_floor", 0.50))
        self.component_model_missing_max = float(
            config.get("component_model_missing_max", 0.05)
        )
        self.component_pass_geometry_min = float(
            config.get("component_pass_geometry_min", self.geometry_min)
        )

    def evaluate(self, geometry: GeometryEvidence, model: ModelEvidence) -> FrameVerdict:
        if len(model.component_probabilities) != 10:
            raise ValueError("V5 model must return exactly ten component probabilities")
        scores = tuple(float(value) for value in model.component_probabilities)
        components: list[ComponentPublicState] = []
        reasons: list[str] = []
        high_count = 0
        low_count = 0
        for index, name in enumerate(self.names):
            local = float(geometry.local_scores.get(name, 0.0))
            score = scores[index]
            if score >= max(self.high[name], self.component_model_floor) and local >= self.local_high[name]:
                components.append(ComponentPublicState.PRESENT)
                high_count += 1
            elif score <= self.component_model_missing_max and (
                local <= self.local_low[name]
                or not geometry.usable
                or geometry.global_score < self.geometry_min
            ):
                components.append(ComponentPublicState.MISSING)
                low_count += 1
            else:
                components.append(ComponentPublicState.UNKNOWN)
                reasons.append(f"{name}:judge_disagreement")
        if not geometry.usable or geometry.global_score < self.geometry_min:
            reasons.extend(geometry.reasons or ("geometry_incompatible",))
        all_components_present = high_count == 10
        if all_components_present and geometry.global_score >= self.component_pass_geometry_min:
            return FrameVerdict(Verdict.PASS, tuple(components), scores, model.global_probability, tuple(reasons))
        if low_count or (model.global_probability <= self.global_low and not all_components_present):
            return FrameVerdict(Verdict.NO_PASS, tuple(components), scores, model.global_probability, tuple(reasons))
        if model.global_probability >= self.global_high and all_components_present and geometry.usable:
            return FrameVerdict(Verdict.PASS, tuple(components), scores, model.global_probability, tuple(reasons))
        if not geometry.usable or geometry.global_score < self.geometry_min:
            return FrameVerdict(Verdict.UNRELIABLE, tuple(components), scores, model.global_probability, tuple(reasons))
        return FrameVerdict(Verdict.UNRELIABLE, tuple(components), scores, model.global_probability, tuple(reasons))


class AdaptiveVoter:
    def __init__(
        self,
        *,
        min_frames: int = 5,
        max_frames: int = 9,
        margin: float = 0.08,
        component_presence_min: float = 0.80,
        component_missing_min: float = 0.40,
    ) -> None:
        self.min_frames = min_frames
        self.max_frames = max_frames
        self.margin = margin
        self.component_presence_min = component_presence_min
        self.component_missing_min = component_missing_min
        self.frames: list[FrameVerdict] = []
        self._finished = False

    @property
    def finished(self) -> bool:
        return self._finished

    def reset(self) -> None:
        self.frames.clear()
        self._finished = False

    def _finish(
        self,
        verdict: Verdict,
        components: tuple[ComponentPublicState, ...],
        reasons: tuple[str, ...],
    ) -> CycleVerdict:
        self._finished = True
        return CycleVerdict(verdict, components, len(self.frames), reasons)

    def _component_vote(self, frames: list[FrameVerdict]) -> tuple[ComponentPublicState, ...]:
        total = max(1, len(frames))
        states: list[ComponentPublicState] = []
        for index in range(10):
            present = sum(
                index < len(frame.components)
                and frame.components[index] is ComponentPublicState.PRESENT
                for frame in frames
            )
            missing = sum(
                index < len(frame.components)
                and frame.components[index] is ComponentPublicState.MISSING
                for frame in frames
            )
            if present / total >= self.component_presence_min:
                states.append(ComponentPublicState.PRESENT)
            elif missing / total >= self.component_missing_min:
                states.append(ComponentPublicState.MISSING)
            else:
                states.append(ComponentPublicState.UNKNOWN)
        return tuple(states)

    def add(self, frame: FrameVerdict) -> CycleVerdict | None:
        if self._finished:
            return None
        self.frames.append(frame)
        if len(self.frames) < self.min_frames:
            return None
        recent = self.frames[-self.min_frames :]
        component_vote = self._component_vote(recent)
        if all(state is ComponentPublicState.PRESENT for state in component_vote):
            return self._finish(Verdict.PASS, component_vote, ())
        if any(state is ComponentPublicState.MISSING for state in component_vote):
            return self._finish(Verdict.NO_PASS, component_vote, ("component_missing",))
        if all(item.verdict is Verdict.PASS for item in recent) and all(
            item.global_score >= 0.5 + self.margin for item in recent
        ):
            return self._finish(Verdict.PASS, recent[-1].components, ())
        if all(item.verdict is Verdict.NO_PASS for item in recent):
            components = tuple(
                ComponentPublicState.MISSING
                if any(item.components[index] is ComponentPublicState.MISSING for item in recent)
                else ComponentPublicState.UNKNOWN
                for index in range(10)
            )
            return self._finish(Verdict.NO_PASS, components, ("consistent_defect",))
        if len(self.frames) < self.max_frames:
            return None
        pass_count = sum(item.verdict is Verdict.PASS for item in self.frames)
        fail_count = sum(item.verdict is Verdict.NO_PASS for item in self.frames)
        if pass_count == self.max_frames:
            return self._finish(Verdict.PASS, self.frames[-1].components, ())
        if fail_count >= self.min_frames and pass_count == 0:
            return self._finish(
                Verdict.NO_PASS,
                self.frames[-1].components,
                ("consistent_defect",),
            )
        return self._finish(
            Verdict.UNRELIABLE,
            self.frames[-1].components,
            ("temporal_disagreement",),
        )
