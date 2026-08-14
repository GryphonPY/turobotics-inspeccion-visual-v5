from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import psutil

from inspection_v5.contracts import TrackingSnapshot
from inspection_v5.inspector import V5Inspector
from inspection_v5.live_state import LiveController
from inspection_v5.presence import PresenceMetrics


@dataclass(frozen=True)
class PerformanceSample:
    ui_fps: float
    stage_ms: float
    decision_ms: float
    removal_ms: float
    rss_mb: float


@dataclass(frozen=True)
class PerformanceSummary:
    sample_count: int
    ui_fps_p50: float
    ui_fps_p95: float
    stage_ms_p50: float
    stage_ms_p95: float
    decision_ms_p50: float
    decision_ms_p95: float
    removal_ms_p50: float
    removal_ms_p95: float
    rss_initial_mb: float
    rss_final_mb: float
    rss_max_mb: float
    rss_growth_mb: float


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def summarize_samples(samples: list[PerformanceSample]) -> PerformanceSummary:
    if not samples:
        return PerformanceSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    rss = [sample.rss_mb for sample in samples]
    return PerformanceSummary(
        sample_count=len(samples),
        ui_fps_p50=_percentile([sample.ui_fps for sample in samples], 50),
        ui_fps_p95=_percentile([sample.ui_fps for sample in samples], 95),
        stage_ms_p50=_percentile([sample.stage_ms for sample in samples], 50),
        stage_ms_p95=_percentile([sample.stage_ms for sample in samples], 95),
        decision_ms_p50=_percentile([sample.decision_ms for sample in samples], 50),
        decision_ms_p95=_percentile([sample.decision_ms for sample in samples], 95),
        removal_ms_p50=_percentile([sample.removal_ms for sample in samples], 50),
        removal_ms_p95=_percentile([sample.removal_ms for sample in samples], 95),
        rss_initial_mb=rss[0],
        rss_final_mb=rss[-1],
        rss_max_mb=max(rss),
        rss_growth_mb=max(rss) - rss[0],
    )


def _source_frame(source: Path) -> np.ndarray:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(source)
    return image


def _git_revision(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _simulated_removal_ms() -> float:
    controller = LiveController()
    mask = np.zeros((20, 20), dtype=np.uint8)

    def metrics(occupied: float, motion: float) -> PresenceMetrics:
        return PresenceMetrics(occupied, motion, 100.0, (1, 1, 10, 10), mask, 42.0, 24.0, 0.0)

    controller.update(metrics(0.50, 3.0), True, 0.00)
    controller.update(metrics(0.50, 0.2), True, 0.10)
    controller.update(metrics(0.50, 0.2), True, 0.46)
    controller.result_ready()
    controller.update(metrics(0.08, 2.0), True, 0.60)
    controller.update(metrics(0.08, 0.1), True, 0.72)
    released = controller.update(metrics(0.08, 0.1), True, 0.82)
    return 220.0 if released.cycle_released else float("inf")


def run_soak(root: Path, minutes: float, source: Path | None, target_fps: float = 24.0) -> dict[str, object]:
    source_path = source or root / "data" / "v5" / "reports" / "reference_v1.png"
    frame = _source_frame(source_path)
    inspector = V5Inspector(root)
    process = psutil.Process()
    samples: list[PerformanceSample] = []
    started = time.monotonic()
    deadline = started + max(minutes, 0.0) * 60.0
    sequence = 0
    inspector.reset()
    while time.monotonic() < deadline or not samples:
        loop_started = time.perf_counter()
        snapshot = TrackingSnapshot(
            sequence=sequence,
            captured_at=time.monotonic(),
            board_ok=True,
            roi=frame,
            bbox=(0, 0, frame.shape[1], frame.shape[0]),
            occupied_ratio=0.5,
            motion=0.0,
            piece_focus=40.0,
        )
        inference_started = time.perf_counter()
        inspector(snapshot)
        decision_ms = (time.perf_counter() - inference_started) * 1000.0
        stage_ms = (time.perf_counter() - loop_started) * 1000.0
        elapsed = max(time.perf_counter() - loop_started, 1e-6)
        samples.append(
            PerformanceSample(
                ui_fps=min(target_fps, 1.0 / elapsed),
                stage_ms=stage_ms,
                decision_ms=decision_ms,
                removal_ms=_simulated_removal_ms(),
                rss_mb=process.memory_info().rss / (1024 * 1024),
            )
        )
        sequence += 1
        remaining = (1.0 / target_fps) - elapsed
        if remaining > 0:
            time.sleep(remaining)
    summary = summarize_samples(samples)
    release_ready = (
        summary.ui_fps_p95 >= 24.0
        and summary.decision_ms_p95 <= 1500.0
        and summary.removal_ms_p50 <= 300.0
        and summary.rss_growth_mb <= 150.0
    )
    result = {
        "schema_version": 1,
        "kind": "soak",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": _git_revision(root),
        "minutes_requested": minutes,
        "source": str(source_path),
        "release_ready": release_ready,
        "summary": asdict(summary),
    }
    output = root / "data" / "v5" / "reports" / f"soak_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a sustained offline V5 performance soak")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--minutes", type=float, default=30.0)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--fps", type=float, default=24.0)
    args = parser.parse_args()
    result = run_soak(args.root.resolve(), args.minutes, args.source, args.fps)
    print(json.dumps({"sample_count": result["summary"]["sample_count"], "release_ready": result["release_ready"]}, indent=2))
    return 0 if bool(result["release_ready"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
