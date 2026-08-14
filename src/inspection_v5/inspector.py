from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from .alignment import PoseAligner
from .contracts import TrackingSnapshot, Verdict
from .features import make_model_tensor
from .fusion import AdaptiveVoter, CycleVerdict, FrameVerdict, HybridJudge
from .geometry_judge import GeometryJudge
from .model_runtime import PresenceModel
from .presence import PresenceAnalyzer, PresenceConfig


class V5Inspector:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        runtime_config = json.loads((self.root / "config" / "v5" / "runtime.json").read_text(encoding="utf-8"))
        self.minimum_piece_focus = float(runtime_config.get("quality", {}).get("minimum_piece_focus", 14.0))
        reference = np.load(self.root / "data" / "v5" / "references" / "reference_v1.npz")
        self.analyzer = PresenceAnalyzer(
            PresenceConfig(reference_area_px=19_000.0, margin_px=8, minimum_blob_area_px=12)
        )
        self.aligner = PoseAligner(reference["mask"], reference["gray"], alignment_min_score=0.35)
        self.geometry = GeometryJudge(reference["mask"], self.root / "config" / "v5" / "component_anchors.json")
        self.model = PresenceModel(
            self.root / "data" / "v5" / "models" / "presence_v1.onnx",
            self.root / "data" / "v5" / "models" / "presence_v1.manifest.json",
        )
        self.judge = HybridJudge(self.root / "config" / "v5" / "decision.json")
        self.voter = AdaptiveVoter(min_frames=5, max_frames=9, margin=0.08)

    def reset(self) -> None:
        self.voter.reset()

    def __call__(self, snapshot: TrackingSnapshot) -> CycleVerdict | None:
        if snapshot.roi is None or snapshot.roi.size == 0:
            return None
        gray = cv2.cvtColor(snapshot.roi, cv2.COLOR_BGR2GRAY) if snapshot.roi.ndim == 3 else snapshot.roi
        if gray.shape != (560, 320):
            gray = cv2.resize(gray, (320, 560), interpolation=cv2.INTER_AREA)
        measured = self.analyzer.measure(gray)
        aligned = self.aligner.align(measured.mask, gray)
        if not aligned.valid:
            frame = FrameVerdict(
                Verdict.UNRELIABLE,
                (),
                (),
                0.0,
                (aligned.reason or "pose_unreliable",),
            )
            return self.voter.add(frame)
        if aligned.local_focus < self.minimum_piece_focus:
            frame = FrameVerdict(
                Verdict.UNRELIABLE,
                (),
                (),
                0.0,
                ("piece_focus_low",),
            )
            return self.voter.add(frame)
        geometry = self.geometry.evaluate(aligned)
        model = self.model.predict(make_model_tensor(aligned))
        frame = self.judge.evaluate(geometry, model)
        return self.voter.add(frame)
