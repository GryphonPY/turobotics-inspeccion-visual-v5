from __future__ import annotations

from pathlib import Path

import numpy as np

from inspection_v4.display import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    BoardStatusLatch,
    board_status,
    fit_into,
)
from inspection_v4.storage import DiagnosticLogger
from inspection_v4.types import BoardObservation


def _observation(found_ids: tuple[int, ...], reason: str = "") -> BoardObservation:
    return BoardObservation(
        found_ids=found_ids,
        marker_corners={},
        homography=None,
        roi=None,
        reprojection_error_px=0.5 if not reason else float("inf"),
        image_size=(1920, 1080),
        canonical_size=(1728, 2235),
        reason=reason,
    )


def test_fixed_dashboard_dimensions_and_no_marker_zoom_state() -> None:
    source = np.zeros((1080, 1920, 3), dtype=np.uint8)
    fitted = fit_into(source, SCREEN_WIDTH, SCREEN_HEIGHT)
    assert fitted.shape == (SCREEN_HEIGHT, SCREEN_WIDTH, 3)
    first, second, _ = board_status(_observation((0, 1)))
    assert first == "DETECTADOS: 0 1"
    assert "FALTAN: 2 3" in second
    assert "NO GRABA" in second


def test_board_status_requires_all_four_markers() -> None:
    first, second, color = board_status(_observation((0, 1, 2, 3)))
    assert first == "ARUCO: 0 1 2 3"
    assert second == "TABLERO OK | 4 ARUCO ESTABLES"
    assert color == (60, 220, 80)


def test_board_status_latch_ignores_two_isolated_bad_frames() -> None:
    good = _observation((0, 1, 2, 3))
    bad = _observation((0, 1, 2, 3), "reprojection_error")
    latch = BoardStatusLatch()

    assert latch.update(good) is good
    assert latch.update(bad) is good
    assert latch.update(bad) is good
    assert latch.update(good) is good


def test_board_status_latch_shows_sustained_bad_status() -> None:
    good = _observation((0, 1, 2, 3))
    bad = _observation((0, 1), "missing_markers:2,3")
    latch = BoardStatusLatch()

    latch.update(good)
    latch.update(good)
    latch.update(good)
    latch.update(bad)
    latch.update(bad)
    shown = latch.update(bad)

    assert shown is bad


def test_diagnostic_logger_records_and_throttles(tmp_path: Path) -> None:
    logger = DiagnosticLogger(tmp_path)
    logger.event("WARN", "marker_missing", "faltan 2 y 3", found_ids=[0, 1])
    logger.throttled("same", 3600.0, "WARN", "repeated")
    logger.throttled("same", 3600.0, "WARN", "repeated")
    lines = (tmp_path / "logs" / "inspection_v4.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"event": "marker_missing"' in lines[0]
    assert '"found_ids": [0, 1]' in lines[0]
