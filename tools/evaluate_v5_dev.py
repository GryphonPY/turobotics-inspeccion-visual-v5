from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch

from inspection_v5.alignment import PoseAligner
from inspection_v5.features import make_model_tensor
from inspection_v5.fusion import HybridJudge
from inspection_v5.geometry_judge import GeometryJudge
from inspection_v5.model_runtime import ModelEvidence
from inspection_v5.presence import PresenceAnalyzer, PresenceConfig
from training_v5.dataset import group_split, index_session
from training_v5.model import V5PresenceNet


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the V5 hybrid judge on development validation")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--session", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    reference = np.load(root / args.reference)
    analyzer = PresenceAnalyzer(PresenceConfig(reference_area_px=19_000.0, margin_px=8, minimum_blob_area_px=12))
    aligner = PoseAligner(reference["mask"], reference["gray"], alignment_min_score=0.35)
    geometry = GeometryJudge(reference["mask"], root / "config" / "v5" / "component_anchors.json")
    judge = HybridJudge(root / args.decision)
    model = V5PresenceNet(pretrained=False).eval()
    model.load_state_dict(torch.load(root / args.checkpoint, map_location="cpu", weights_only=True))
    samples = index_session(root, args.session)
    validation = group_split(samples, {1, 2, 3, 4, 5}, {6}, allow_unassigned=True).validation
    counts = Counter()
    rows: list[dict[str, object]] = []
    with torch.no_grad():
        for sample in validation:
            image = cv2.imread(str(root / sample.path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            gray = cv2.resize(image, (320, 560), interpolation=cv2.INTER_AREA)
            measured = analyzer.measure(gray)
            aligned = aligner.align(measured.mask, gray)
            if not aligned.valid:
                counts[(sample.state, "UNRELIABLE")] += 1
                continue
            evidence = geometry.evaluate(aligned)
            probabilities = torch.sigmoid(model(torch.from_numpy(make_model_tensor(aligned))[None, ...]))[0].numpy()
            verdict = judge.evaluate(evidence, ModelEvidence(tuple(probabilities[:10]), float(probabilities[10]), 0.0, "dev"))
            counts[(sample.state, verdict.verdict.value)] += 1
            rows.append({"state": sample.state, "verdict": verdict.verdict.value, "reasons": list(verdict.reasons)})
    result = {"sample_count": len(rows), "counts": {f"{state}:{verdict}": count for (state, verdict), count in sorted(counts.items())}, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
