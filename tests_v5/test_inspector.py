from __future__ import annotations

from pathlib import Path

import cv2

from inspection_v5.contracts import TrackingSnapshot
from inspection_v5.inspector import V5Inspector

ROOT = Path(__file__).resolve().parents[1]


def _snapshot(path: Path) -> TrackingSnapshot:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    assert image is not None
    return TrackingSnapshot(1, 1.0, True, image, (0, 0, 0, 0), 1.0, 0.0, 100.0)


def test_inspector_closes_a_complete_cycle_from_legacy_frame_size() -> None:
    inspector = V5Inspector(ROOT)
    snapshot = _snapshot(ROOT / "data" / "raw_sessions" / "session_20260813_001845" / "round_01" / "OK" / "frame_0000.png")

    results = [inspector(snapshot) for _ in range(5)]

    assert results[-1] is not None
    assert results[-1].verdict.value == "PASS"


def test_inspector_rejects_a_blurred_capture_as_unreliable() -> None:
    inspector = V5Inspector(ROOT)
    snapshot = _snapshot(ROOT / "tests_v5" / "fixtures" / "blurred.png")

    results = [inspector(snapshot) for _ in range(9)]

    assert results[-1] is not None
    assert results[-1].verdict.value == "UNRELIABLE"
