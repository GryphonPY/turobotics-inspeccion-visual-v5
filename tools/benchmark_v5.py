from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

from inspection_v5.board_tracker import BoardTracker, V5BoardConfig
from inspection_v5.contracts import FramePacket
from inspection_v5.model_runtime import PresenceModel


def synthetic_board(config: V5BoardConfig) -> np.ndarray:
    width, height = config.canonical_size_px
    image = np.full((height, width, 3), 24, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    scale = config.pixels_per_mm
    patch = round(50 * scale)
    quiet = round(7 * scale)
    for marker_id, marker in config.markers.items():
        x = round(float(marker["x_mm"]) * scale)
        y = round(float(marker["y_mm"]) * scale)
        size = round(float(marker["size_mm"]) * scale)
        canvas = np.full((patch, patch, 3), 255, dtype=np.uint8)
        marker_image = cv2.aruco.generateImageMarker(dictionary, marker_id, size)
        canvas[quiet : quiet + size, quiet : quiet + size] = cv2.cvtColor(marker_image, cv2.COLOR_GRAY2BGR)
        image[y - quiet : y - quiet + patch, x - quiet : x - quiet + patch] = canvas
    return image


def benchmark_board(root: Path, frames: int) -> tuple[float, float]:
    config = V5BoardConfig.from_json(root / "config" / "v5" / "runtime.json")
    tracker = BoardTracker(config)
    frame = synthetic_board(config)
    for sequence in range(5):
        tracker.observe(FramePacket(sequence, float(sequence), frame), now=float(sequence))
    samples: list[float] = []
    for sequence in range(frames):
        started = time.perf_counter()
        tracker.observe(FramePacket(sequence, float(sequence), frame), now=float(sequence))
        samples.append((time.perf_counter() - started) * 1000.0)
    return statistics.median(samples), float(np.percentile(samples, 95))


def benchmark_onnx(root: Path, frames: int) -> tuple[float, float]:
    model = PresenceModel(
        root / "data" / "v5" / "models" / "presence_v1.onnx",
        root / "data" / "v5" / "models" / "presence_v1.manifest.json",
    )
    tensor = np.zeros((3, 224, 224), dtype=np.float32)
    for _ in range(10):
        model.predict(tensor)
    samples: list[float] = []
    for _ in range(frames):
        samples.append(model.predict(tensor).latency_ms)
    return statistics.median(samples), float(np.percentile(samples, 95))


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark V5 stages")
    parser.add_argument("--stage", choices=("board", "onnx"), required=True)
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    median, p95 = (
        benchmark_board(args.root, args.frames)
        if args.stage == "board"
        else benchmark_onnx(args.root, args.frames)
    )
    print(f"stage={args.stage} frames={args.frames} median_ms={median:.2f} p95_ms={p95:.2f}")
    return 0 if p95 <= 35.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
