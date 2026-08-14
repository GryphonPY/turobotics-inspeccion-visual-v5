from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from training_v5.dataset import group_split, index_session
from training_v5.metrics import component_metrics
from training_v5.model import V5PresenceNet
from training_v5.train import FeatureExtractor


def calibrate(root: Path, session_id: str, reference_path: Path, checkpoint_path: Path) -> dict[str, object]:
    torch.set_num_threads(1)
    samples = index_session(root, session_id)
    split = group_split(samples, train_rounds={1, 2, 3, 4, 5}, validation_rounds={6}, allow_unassigned=True)
    extractor = FeatureExtractor(root, reference_path)
    model = V5PresenceNet(pretrained=False).eval()
    model.load_state_dict(torch.load(checkpoint_path, map_location="cpu", weights_only=True))
    tensors: list[torch.Tensor] = []
    labels: list[tuple[int, ...]] = []
    for sample in split.validation:
        tensors.append(torch.from_numpy(extractor(sample.path)))
        labels.append((*sample.labels, int(sample.state == "OK")))
    predictions: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(tensors), 16):
            batch = torch.stack(tensors[start : start + 16])
            predictions.append(torch.sigmoid(model(batch)).numpy())
    probabilities = np.concatenate(predictions, axis=0)
    expected = np.asarray(labels, dtype=np.int8)
    metrics = component_metrics(probabilities, expected)
    result = {
        "version": "decision_v1",
        "session_id": session_id,
        "calibration_rounds": [6],
        "holdout_rounds": [7],
        "sample_count": len(split.validation),
        "thresholds": {name: round(value.threshold, 8) for name, value in metrics.items()},
        "false_passes": {name: value.false_passes for name, value in metrics.items()},
        "false_rejects": {name: value.false_rejects for name, value in metrics.items()},
        "resolved": {name: value.resolved for name, value in metrics.items()},
        "policy": "zero calibration false passes; unresolved components require geometry or challenge evidence",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate conservative V5 thresholds")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--session", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    result = calibrate(root, args.session, root / args.reference, root / args.checkpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
