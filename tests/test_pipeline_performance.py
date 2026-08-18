from __future__ import annotations

from pathlib import Path

import cv2

from inspection_v5.board_tracker import BoardTracker, V5BoardConfig
from inspection_v5.contracts import FramePacket
from tools.benchmark_v5 import benchmark_board

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_board_benchmark_stays_within_gate() -> None:
    median_ms, p95_ms = benchmark_board(ROOT, 30)

    assert median_ms >= 0.0
    assert p95_ms <= 35.0


def test_permanent_board_fixture_detects_four_markers() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    image = cv2.imread(str(ROOT / "tests_v5" / "fixtures" / "board_complete.png"))
    assert image is not None
    observation = BoardTracker(config).observe(FramePacket(1, 1.0, image), now=1.0)

    assert observation.board_ok
    assert observation.found_ids == (0, 1, 2, 3)
