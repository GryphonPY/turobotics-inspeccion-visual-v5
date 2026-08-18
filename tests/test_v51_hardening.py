from __future__ import annotations

from pathlib import Path

from inspection_v5.inspector import V5Inspector
from inspection_v5.runtime import InspectionRuntime

ROOT = Path(__file__).resolve().parents[1]


def test_inspector_uses_central_runtime_configuration() -> None:
    inspector = V5Inspector(ROOT)

    assert inspector.roi_size == (320, 560)
    assert inspector.analyzer.config.reference_area_px == 19_000.0
    assert inspector.analyzer.config.margin_px == 8
    assert inspector.analyzer.config.minimum_blob_area_px == 12
    assert inspector.voter.min_frames == 5
    assert inspector.voter.max_frames == 9


def test_reset_counters_publishes_updated_public_state() -> None:
    runtime = InspectionRuntime(ROOT)
    runtime._counters = {"total": 4, "passed": 2, "failed": 1, "unreliable": 1}
    before = runtime.latest_public_state().version

    runtime.reset_counters()
    state = runtime.latest_public_state()

    assert state.version > before
    assert state.counters == {"total": 0, "passed": 0, "failed": 0, "unreliable": 0}
