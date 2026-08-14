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
