from __future__ import annotations

import time
from pathlib import Path
from threading import Lock

import numpy as np

from inspection_v5.contracts import TrackingSnapshot
from inspection_v5.runtime import InspectionRuntime

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_processes_latest_frame_and_stops_cleanly() -> None:
    runtime = InspectionRuntime(ROOT)
    runtime.start()
    for _ in range(10):
        runtime.publish_frame(np.full((720, 1280, 3), 24, dtype=np.uint8))
    deadline = time.monotonic() + 2.0
    while runtime.latest_public_state().version == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    runtime.stop()

    assert runtime.latest_public_state().version > 0
    assert runtime._thread is None


def test_runtime_keeps_only_latest_published_frame() -> None:
    runtime = InspectionRuntime(ROOT)
    first = runtime.publish_frame(np.zeros((10, 10, 3), dtype=np.uint8))
    latest = runtime.publish_frame(np.ones((10, 10, 3), dtype=np.uint8))

    version, packet = runtime.frames.read(after_version=first)

    assert version == latest
    assert packet is not None
    assert int(packet.bgr[0, 0, 0]) == 1


def test_runtime_shows_full_camera_frame_when_board_is_not_detected() -> None:
    runtime = InspectionRuntime(ROOT)
    full_frame = np.full((12, 16, 3), 42, dtype=np.uint8)
    runtime._publish_public(
        TrackingSnapshot(1, 1.0, False, None, (0, 0, 0, 0), 0.0, 0.0, 0.0, reason="missing_markers:0"),
        full_frame,
    )

    displayed = runtime.latest_public_state().frame

    assert displayed is not None
    assert np.array_equal(displayed, full_frame)


def test_runtime_prefers_full_board_for_public_display() -> None:
    runtime = InspectionRuntime(ROOT)
    board = np.full((2235, 1728, 3), 18, dtype=np.uint8)
    roi = np.full((560, 320, 3), 220, dtype=np.uint8)
    runtime._publish_public(
        TrackingSnapshot(1, 1.0, True, roi, (0, 0, 0, 0), 0.0, 0.0, 0.0, board=board),
        np.zeros((1080, 1920, 3), dtype=np.uint8),
    )

    displayed = runtime.latest_public_state().frame

    assert displayed is not None
    assert displayed.shape[:2] == (2235, 1728)
    assert int(displayed[0, 0, 0]) == 18


def test_slow_inspector_has_one_pending_request() -> None:
    calls: list[int] = []
    calls_lock = Lock()

    def slow_inspector(snapshot) -> None:
        time.sleep(0.05)
        with calls_lock:
            calls.append(snapshot.sequence)

    runtime = InspectionRuntime(ROOT, inspector=slow_inspector)
    runtime.start()
    for sequence in range(30):
        runtime.request_inspection(
            TrackingSnapshot(
                sequence=sequence,
                captured_at=float(sequence),
                board_ok=True,
                roi=np.zeros((10, 10), dtype=np.uint8),
                bbox=(0, 0, 1, 1),
                occupied_ratio=1.0,
                motion=0.0,
                piece_focus=100.0,
            )
        )
    time.sleep(0.15)
    runtime.stop()

    assert 1 <= len(calls) <= 5
