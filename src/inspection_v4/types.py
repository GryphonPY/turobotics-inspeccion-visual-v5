from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class Verdict(str, Enum):
    PASS = "PASS"
    NO_PASS = "NO_PASS"
    UNRELIABLE = "UNRELIABLE"
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"


@dataclass
class BoardObservation:
    found_ids: tuple[int, ...]
    marker_corners: dict[int, np.ndarray]
    homography: np.ndarray | None
    roi: np.ndarray | None
    reprojection_error_px: float
    image_size: tuple[int, int]
    canonical_size: tuple[int, int] = (0, 0)
    reason: str = ""
    duplicate_ids: tuple[int, ...] = ()


@dataclass
class QualityReport:
    valid: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class PieceObservation:
    mask: np.ndarray
    gray: np.ndarray
    area_px: int
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]
    valid: bool
    reason: str = ""


@dataclass
class AlignedPiece:
    mask: np.ndarray
    gray: np.ndarray
    edges: np.ndarray
    transform: np.ndarray
    angle_deg: float
    alignment_score: float
    valid: bool
    reason: str = ""


@dataclass
class ComponentEvidence:
    component_id: str
    present: bool
    score: float
    occupancy_score: float
    edge_score: float
    advantage_score: float
    threshold: float
    reason: str = ""


@dataclass
class FrameDecision:
    verdict: Verdict
    usable: bool
    reason: str
    evidence: list[ComponentEvidence] = field(default_factory=list)
    alignment_score: float = 0.0
    quality_score: float = 0.0


@dataclass
class InspectionResult:
    verdict: Verdict
    reason: str
    valid_frames: int
    component_votes: dict[str, int]
    evidence: list[ComponentEvidence] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    cycle_id: int = 0
    diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass
class WorkflowSnapshot:
    state: str
    board_ok: bool
    board_reason: str
    quality: QualityReport | None = None
    piece: PieceObservation | None = None
    frame_decision: FrameDecision | None = None
    result: InspectionResult | None = None
    counters: dict[str, int] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
