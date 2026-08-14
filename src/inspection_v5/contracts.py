from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class TrackingMode(str, Enum):
    EMPTY = "EMPTY"
    DETECTED = "DETECTED"
    STABILIZING = "STABILIZING"
    INSPECTING = "INSPECTING"
    LOCKED = "LOCKED"
    PASS = "PASS"
    FAIL = "FAIL"


class ComponentPublicState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    UNRELIABLE = "UNRELIABLE"


class Verdict(str, Enum):
    PASS = "PASS"
    NO_PASS = "NO_PASS"
    UNRELIABLE = "UNRELIABLE"


@dataclass(frozen=True)
class FramePacket:
    sequence: int
    captured_at: float
    bgr: np.ndarray


@dataclass(frozen=True)
class TrackingSnapshot:
    sequence: int
    captured_at: float
    board_ok: bool
    roi: np.ndarray | None
    bbox: tuple[int, int, int, int]
    occupied_ratio: float
    motion: float
    piece_focus: float
    marker_focus: float = 0.0
    homography_age_ms: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class RuntimeMetrics:
    camera_fps: float = 0.0
    ui_fps: float = 0.0
    tracking_fps: float = 0.0
    stage_ms: Mapping[str, float] = field(default_factory=dict)
    piece_focus: float = 0.0
    marker_focus: float = 0.0
    occupied_ratio: float = 0.0
    motion: float = 0.0
    model_hash: str = ""
    log_path: str = ""


@dataclass(frozen=True)
class PublicState:
    version: int = 0
    frame: np.ndarray | None = None
    tracking_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    tracking_mode: TrackingMode = TrackingMode.EMPTY
    headline: str = "ÁREA LIBRE"
    detail: str = "Coloca la pieza dentro del rectángulo"
    instruction: str = "LISTO PARA INSPECCIONAR"
    verdict: Verdict | None = None
    component_states: Mapping[str, ComponentPublicState] = field(default_factory=dict)
    counters: Mapping[str, int] = field(default_factory=dict)
    metrics: RuntimeMetrics = field(default_factory=RuntimeMetrics)
