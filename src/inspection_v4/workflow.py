from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

from .board import BoardRectifier
from .components import ComponentEvaluator, ReferenceSet
from .config import BoardConfig, InspectionConfig
from .decision import TemporalVoter, decide_frame
from .piece import PieceAligner, PieceSegmenter
from .quality import assess_frame
from .types import FrameDecision, InspectionResult, Verdict


class WorkflowState(str, Enum):
    BOOT = "BOOT"
    CAMERA_SETUP = "CAMERA_SETUP"
    BOARD_CHECK = "BOARD_CHECK"
    WAIT_PIECE = "WAIT_PIECE"
    STABILIZING = "STABILIZING"
    COLLECTING = "COLLECTING"
    DECIDED = "DECIDED"
    WAIT_REMOVAL = "WAIT_REMOVAL"
    FAULT = "FAULT"


@dataclass
class WorkflowCounters:
    passed: int = 0
    failed: int = 0
    unreliable: int = 0
    total: int = 0


@dataclass
class InspectionWorkflow:
    board: BoardConfig
    config: InspectionConfig
    rectifier: BoardRectifier
    reference: ReferenceSet
    state: WorkflowState = WorkflowState.BOOT
    counters: WorkflowCounters = field(default_factory=WorkflowCounters)
    cycle_id: int = 0
    previous_canonical: np.ndarray | None = None
    previous_mask: np.ndarray | None = None
    baseline_laplacian: float | None = None
    stable_since: float | None = None
    collection_started: float | None = None
    last_collected_at: float | None = None
    removal_since: float | None = None
    inspection_started: float | None = None
    frame_decisions: list[FrameDecision] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.segmenter = PieceSegmenter(self.board, self.config)
        self.aligner = PieceAligner(self.config.alignment_min_score)
        self.evaluator = ComponentEvaluator(self.reference, self.config)
        self.voter = TemporalVoter(self.config)

    def startup(self) -> None:
        self.state = WorkflowState.CAMERA_SETUP
        self.baseline_laplacian = None

    def process_frame(self, frame: np.ndarray, now: float | None = None) -> tuple[WorkflowState, InspectionResult | None]:
        now = now if now is not None else time.monotonic()
        canonical, observation = self.rectifier.warp(frame)
        if canonical is None or observation.reason:
            if self.state == WorkflowState.WAIT_REMOVAL:
                return self.state, None
            self.state = WorkflowState.BOARD_CHECK
            return self.state, None
        quality = assess_frame(
            canonical, observation, self.board, self.config,
            self.baseline_laplacian, self.previous_canonical,
        )
        if self.baseline_laplacian is None and quality.valid:
            self.baseline_laplacian = quality.metrics.get(
                "laplacian", self.config.quality_min_laplacian
            )
        self.previous_canonical = canonical
        if not quality.valid:
            if self.state == WorkflowState.WAIT_REMOVAL:
                return self.state, None
            if "markers_incomplete" in quality.reasons or observation.homography is None:
                self.state = WorkflowState.BOARD_CHECK
                self.stable_since = None
                return self.state, None
            if self.state == WorkflowState.STABILIZING:
                self.stable_since = None
                return self.state, None
            if self.state == WorkflowState.COLLECTING:
                if self._collection_expired(now):
                    result = self._finish_collection(now)
                    return self.state, result
                return self.state, None
            if "motion" in quality.reasons and self.state in {
                WorkflowState.STABILIZING,
                WorkflowState.COLLECTING,
            }:
                if self.state == WorkflowState.STABILIZING:
                    self.stable_since = now
                elif self._collection_expired(now):
                    result = self._finish_collection(now)
                    return self.state, result
                return self.state, None
            self.state = WorkflowState.WAIT_PIECE
            return self.state, None
        piece = self.segmenter.segment(observation.roi)
        if not piece.valid:
            if self.state == WorkflowState.WAIT_REMOVAL:
                if self.removal_since is None:
                    self.removal_since = now
                elif now - self.removal_since >= self.config.removal_seconds:
                    self.confirm_removal(piece_present=False)
                return self.state, None
            if self.state == WorkflowState.COLLECTING and self._collection_expired(now):
                result = self._finish_collection(now)
                return self.state, result
            self.state = WorkflowState.WAIT_PIECE
            return self.state, None
        if self.state in {WorkflowState.BOOT, WorkflowState.CAMERA_SETUP, WorkflowState.BOARD_CHECK, WorkflowState.WAIT_PIECE}:
            self.state = WorkflowState.STABILIZING
            self.stable_since = now
            return self.state, None
        if self.state == WorkflowState.STABILIZING:
            if self.stable_since is None:
                self.stable_since = now
            if now - self.stable_since < self.config.stability_seconds:
                return self.state, None
            self.state = WorkflowState.COLLECTING
            self.collection_started = now
            self.inspection_started = now
            self.last_collected_at = None
            self.frame_decisions.clear()
        if self.state == WorkflowState.COLLECTING:
            if (
                self.last_collected_at is not None
                and now - self.last_collected_at < self.config.frame_spacing_seconds
            ):
                return self.state, None
            aligned = self.aligner.align(piece, self.reference.complete_mask, self.reference.complete_gray)
            evidence = self.evaluator.evaluate(aligned)
            decision = decide_frame(evidence, aligned.alignment_score, quality.score)
            if decision.usable:
                self.frame_decisions.append(decision)
                self.frame_decisions.sort(
                    key=lambda item: 0.5 * item.quality_score + 0.5 * item.alignment_score,
                    reverse=True,
                )
                del self.frame_decisions[self.config.max_valid_frames :]
                self.last_collected_at = now
                if self._collection_expired(now):
                    result = self._finish_collection(now)
                    return self.state, result
            elif self.collection_started is not None and now - self.collection_started >= self.config.collection_seconds:
                result = self._finish_collection(now)
                return self.state, result
        return self.state, None

    def _collection_expired(self, now: float) -> bool:
        return self.collection_started is not None and now - self.collection_started >= self.config.collection_seconds

    def _finish_collection(self, now: float) -> InspectionResult:
        result = self.voter.aggregate(self.frame_decisions, self.cycle_id)
        self._record_result(result, now)
        self.state = WorkflowState.DECIDED
        return result

    def _record_result(self, result: InspectionResult, now: float) -> None:
        if self.inspection_started is not None:
            result.elapsed_seconds = max(0.0, now - self.inspection_started)
        self.counters.total += 1
        if result.verdict == Verdict.PASS:
            self.counters.passed += 1
        elif result.verdict == Verdict.NO_PASS:
            self.counters.failed += 1
        else:
            self.counters.unreliable += 1
        self.cycle_id += 1

    def acknowledge_result(self) -> None:
        if self.state == WorkflowState.DECIDED:
            self.state = WorkflowState.WAIT_REMOVAL
            self.removal_since = None

    def confirm_removal(self, piece_present: bool) -> None:
        if self.state == WorkflowState.WAIT_REMOVAL and not piece_present:
            self.state = WorkflowState.WAIT_PIECE
            self.frame_decisions.clear()
            self.stable_since = None
            self.removal_since = None
            self.inspection_started = None

    def reset_cycle(self) -> None:
        self.state = WorkflowState.WAIT_PIECE
        self.frame_decisions.clear()
        self.stable_since = None
        self.collection_started = None
        self.last_collected_at = None
        self.removal_since = None
        self.inspection_started = None
        self.previous_canonical = None

    def reset_counters(self) -> None:
        self.counters = WorkflowCounters()
