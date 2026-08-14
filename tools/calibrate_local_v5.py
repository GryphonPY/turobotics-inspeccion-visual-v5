from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from inspection_v5.alignment import PoseAligner
from inspection_v5.geometry_judge import GeometryJudge
from inspection_v5.presence import PresenceAnalyzer, PresenceConfig
from training_v5.dataset import group_split, index_session


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure local geometric evidence per component")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--session", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    reference = np.load(root / args.reference)
    analyzer = PresenceAnalyzer(PresenceConfig(reference_area_px=19_000.0, margin_px=8, minimum_blob_area_px=12))
    aligner = PoseAligner(reference["mask"], reference["gray"], alignment_min_score=0.35)
    judge = GeometryJudge(reference["mask"], root / "config" / "v5" / "component_anchors.json")
    samples = index_session(root, args.session)
    validation = group_split(samples, {1, 2, 3, 4, 5}, {6}, allow_unassigned=True).validation
    rows: list[dict[str, object]] = []
    for sample in validation:
        image = cv2.imread(str(root / sample.path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            continue
        gray = cv2.resize(image, (320, 560), interpolation=cv2.INTER_AREA)
        measured = analyzer.measure(gray)
        aligned = aligner.align(measured.mask, gray)
        if aligned.valid:
            evidence = judge.evaluate(aligned)
            rows.append({"labels": [*sample.labels, int(sample.state == "OK")], "local": evidence.local_scores})
    result: dict[str, object] = {"sample_count": len(rows), "components": {}}
    for index in range(10):
        name = f"C{index + 1:02d}"
        values = np.asarray([float(row["local"][name]) for row in rows])
        labels = np.asarray([int(row["labels"][index]) for row in rows])
        negative_max = float(values[labels == 0].max())
        positive_min = float(values[labels == 1].min())
        result["components"][name] = {
            "negative_max": negative_max,
            "positive_min": positive_min,
            "separated": bool(negative_max < positive_min),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
