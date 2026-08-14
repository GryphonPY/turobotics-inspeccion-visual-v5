from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from inspection_v5.alignment import PoseAligner
from inspection_v5.features import make_model_tensor
from inspection_v5.presence import PresenceAnalyzer, PresenceConfig

from .dataset import Sample, group_split, index_session
from .model import V5PresenceNet


@dataclass(frozen=True)
class TrainingReport:
    model_path: str
    report_path: str
    epochs: int
    train_samples: int
    validation_samples: int
    validation_accuracy: list[float]
    validation_false_passes: list[int]
    seed: int


class FeatureExtractor:
    def __init__(self, root: Path, reference_path: Path) -> None:
        reference = np.load(reference_path)
        self.reference_gray = reference["gray"].astype(np.uint8)
        self.reference_mask = reference["mask"].astype(np.uint8)
        self.analyzer = PresenceAnalyzer(
            PresenceConfig(reference_area_px=19_000.0, margin_px=8, minimum_blob_area_px=12)
        )
        self.aligner = PoseAligner(self.reference_mask, self.reference_gray, alignment_min_score=0.35)
        self.root = root

    def __call__(self, relative_path: Path) -> np.ndarray:
        path = self.root / relative_path
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Could not read training image: {path}")
        gray = cv2.resize(image, (320, 560), interpolation=cv2.INTER_AREA)
        metrics = self.analyzer.measure(gray)
        aligned = self.aligner.align(metrics.mask, gray)
        if not aligned.valid:
            raise ValueError(f"Could not align training image {path}: {aligned.reason}")
        return make_model_tensor(aligned)


class V5Dataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, samples: tuple[Sample, ...], extractor: FeatureExtractor, augment: bool, seed: int) -> None:
        self.samples = samples
        self.extractor = extractor
        self.augment = augment
        self.seed = seed

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[index]
        features = torch.from_numpy(self.extractor(sample.path))
        if self.augment:
            generator = torch.Generator().manual_seed(self.seed + index * 7919)
            if torch.rand((), generator=generator).item() < 0.35:
                scale = 0.85 + 0.30 * torch.rand((), generator=generator).item()
                features[0] = torch.clamp(features[0] * scale, 0.0, 1.0)
            if torch.rand((), generator=generator).item() < 0.25:
                noise = torch.randn(features[0].shape, generator=generator) * 0.025
                features[0] = torch.clamp(features[0] + noise, 0.0, 1.0)
            if torch.rand((), generator=generator).item() < 0.15:
                kernel = torch.ones((1, 1, 3, 3), dtype=features.dtype) / 9.0
                features[0:1] = torch.nn.functional.conv2d(
                    features[0:1].unsqueeze(0), kernel, padding=1
                ).squeeze(0)
        labels = torch.tensor((*sample.labels, int(sample.state == "OK")), dtype=torch.float32)
        return features, labels


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)


def _metrics(logits: torch.Tensor, labels: torch.Tensor) -> tuple[float, int]:
    predictions = (torch.sigmoid(logits) >= 0.5).to(torch.int64)
    expected = labels.to(torch.int64)
    accuracy = float((predictions == expected).float().mean().item())
    false_passes = int(((predictions == 1) & (expected == 0)).any(dim=1).sum().item())
    return accuracy, false_passes


def train_model(config_path: Path) -> TrainingReport:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.parents[2]
    seed = int(config.get("seed", 20260813))
    _seed_everything(seed)
    session_id = str(config["session_id"])
    samples = index_session(root, session_id)
    split = group_split(
        samples,
        train_rounds=set(config.get("train_rounds", [1, 2, 3, 4, 5])),
        validation_rounds=set(config.get("validation_rounds", [6])),
        allow_unassigned=True,
    )
    reference_path = root / config["reference_path"]
    extractor = FeatureExtractor(root, reference_path)
    train_set = V5Dataset(split.train, extractor, augment=True, seed=seed)
    validation_set = V5Dataset(split.validation, extractor, augment=False, seed=seed)
    batch_size = int(config.get("batch_size", 16))
    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=0)
    validation_loader = DataLoader(validation_set, batch_size=batch_size, shuffle=False, num_workers=0)
    model = V5PresenceNet(pretrained=bool(config.get("pretrained", False)))
    freeze_epochs = int(config.get("freeze_epochs", 2))
    if freeze_epochs:
        for parameter in model.backbone.features.parameters():
            parameter.requires_grad = False
    positive = torch.zeros(11)
    negative = torch.zeros(11)
    for sample in split.train:
        labels = torch.tensor((*sample.labels, int(sample.state == "OK")), dtype=torch.float32)
        positive += labels
        negative += 1.0 - labels
    loss = nn.BCEWithLogitsLoss(pos_weight=negative / positive.clamp_min(1.0))
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=float(config.get("learning_rate", 0.0005)),
        weight_decay=float(config.get("weight_decay", 0.0001)),
    )
    epochs = int(config.get("epochs", 4))
    validation_accuracy: list[float] = []
    validation_false_passes: list[int] = []
    started = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        if epoch == freeze_epochs:
            for parameter in model.backbone.features.parameters():
                parameter.requires_grad = True
            optimizer = torch.optim.AdamW(model.parameters(), lr=float(config.get("learning_rate", 0.0005)))
        for features, labels in train_loader:
            optimizer.zero_grad(set_to_none=True)
            output = model(features)
            batch_loss = loss(output, labels)
            batch_loss.backward()
            optimizer.step()
        model.eval()
        all_logits: list[torch.Tensor] = []
        all_labels: list[torch.Tensor] = []
        with torch.no_grad():
            for features, labels in validation_loader:
                all_logits.append(model(features))
                all_labels.append(labels)
        logits = torch.cat(all_logits)
        labels = torch.cat(all_labels)
        accuracy, false_passes = _metrics(logits, labels)
        validation_accuracy.append(accuracy)
        validation_false_passes.append(false_passes)
    model_dir = root / "data" / "v5" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "presence_v1.pt"
    torch.save(model.state_dict(), model_path)
    report_path = model_dir / "presence_v1.training.json"
    report = {
        "version": "presence_v1",
        "session_id": session_id,
        "train_rounds": config.get("train_rounds", [1, 2, 3, 4, 5]),
        "validation_rounds": config.get("validation_rounds", [6]),
        "holdout_rounds": config.get("holdout_rounds", [7]),
        "train_samples": len(split.train),
        "validation_samples": len(split.validation),
        "epochs": epochs,
        "freeze_epochs": freeze_epochs,
        "seed": seed,
        "pretrained": bool(config.get("pretrained", False)),
        "validation_accuracy": validation_accuracy,
        "validation_false_passes": validation_false_passes,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "model_path": model_path.relative_to(root).as_posix(),
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return TrainingReport(
        model_path.as_posix(),
        report_path.as_posix(),
        epochs,
        len(split.train),
        len(split.validation),
        validation_accuracy,
        validation_false_passes,
        seed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Train V5 multicomponent presence model")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    report = train_model(args.config.resolve())
    print(json.dumps(report.__dict__, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
