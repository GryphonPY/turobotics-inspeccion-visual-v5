from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from inspection_v5.alignment import PoseAligner
from inspection_v5.presence import PresenceAnalyzer, PresenceConfig


def _read_index(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resize_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return cv2.resize(image, (320, 560), interpolation=cv2.INTER_AREA)


def _select_samples(index: list[dict[str, object]], rounds: set[int], per_clip: int) -> list[Path]:
    grouped: dict[str, list[Path]] = {}
    for item in index:
        if item["state"] != "OK" or int(item["round_id"]) not in rounds:
            continue
        grouped.setdefault(str(item["clip_id"]), []).append(Path(str(item["path"])))
    selected: list[Path] = []
    for clip_id in sorted(grouped):
        paths = grouped[clip_id]
        if len(paths) <= per_clip:
            selected.extend(paths)
            continue
        indices = np.linspace(0, len(paths) - 1, per_clip, dtype=int)
        selected.extend(paths[index] for index in sorted(set(indices)))
    return selected


def build_reference(root: Path, session_id: str, rounds: set[int], per_clip: int) -> dict[str, object]:
    index_path = root / "data" / "v5" / "dataset" / "index.jsonl"
    index = _read_index(index_path)
    paths = _select_samples(index, rounds, per_clip)
    analyzer = PresenceAnalyzer(
        PresenceConfig(reference_area_px=19_000.0, margin_px=8, minimum_blob_area_px=12)
    )
    candidates: list[tuple[Path, np.ndarray, np.ndarray]] = []
    for relative_path in paths:
        path = root / relative_path
        gray = _resize_gray(path)
        metrics = analyzer.measure(gray)
        if 0.25 <= metrics.occupied_ratio <= 1.0 and cv2.countNonZero(metrics.mask) > 2500:
            candidates.append((relative_path, gray, metrics.mask))
    if len(candidates) < 3:
        raise RuntimeError(f"Only {len(candidates)} usable OK frames found")
    seed_index = next(
        (
            index
            for index, (path, _, _) in enumerate(candidates)
            if path.as_posix().endswith("round_01/OK/frame_0000.png")
        ),
        0,
    )
    seed_path, seed_gray, seed_mask = candidates[seed_index]
    aligner = PoseAligner(seed_mask, seed_gray, alignment_min_score=0.35)
    aligned_gray: list[np.ndarray] = []
    aligned_mask: list[np.ndarray] = []
    accepted_paths: list[str] = []
    for relative_path, gray, mask in candidates:
        aligned = aligner.align(mask, gray)
        if not aligned.valid:
            continue
        aligned_gray.append(aligned.gray)
        aligned_mask.append(aligned.mask)
        accepted_paths.append(relative_path.as_posix())
    if len(aligned_gray) < 3:
        raise RuntimeError(f"Only {len(aligned_gray)} aligned OK frames found")
    mask_stack = np.stack(aligned_mask, axis=0)
    gray_stack = np.stack(aligned_gray, axis=0)
    reference_mask = (np.mean(mask_stack > 127, axis=0) >= 0.50).astype(np.uint8) * 255
    reference_gray = np.median(gray_stack, axis=0).astype(np.uint8)
    reference_mask = cv2.morphologyEx(
        reference_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    output_dir = root / "data" / "v5" / "references"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "reference_v1.npz"
    np.savez_compressed(output_path, gray=reference_gray, mask=reference_mask)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    metadata = {
        "version": "reference_v1",
        "session_id": session_id,
        "rounds": sorted(rounds),
        "candidate_count": len(candidates),
        "accepted_count": len(aligned_gray),
        "seed": seed_path.as_posix(),
        "shape": [560, 320],
        "mask_threshold": 0.50,
        "sha256": digest,
        "source_paths": accepted_paths,
        "warning": "Development reference only; round_7 remains independent holdout.",
    }
    (output_dir / "reference_v1.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a leakage-safe V5 reference from complete assemblies")
    parser.add_argument("--session", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--per-clip", type=int, default=60)
    args = parser.parse_args()
    metadata = build_reference(args.root.resolve(), args.session, {1, 2, 3, 4, 5}, args.per_clip)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
