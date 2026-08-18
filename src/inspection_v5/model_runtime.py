from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort


class ModelIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelEvidence:
    component_probabilities: tuple[float, ...]
    global_probability: float
    latency_ms: float
    model_hash: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PresenceModel:
    def __init__(self, model_path: Path, manifest_path: Path) -> None:
        self.model_path = model_path
        self.manifest_path = manifest_path
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actual_hash = _sha256(model_path)
        if actual_hash != manifest.get("model_sha256"):
            raise ModelIntegrityError("V5 ONNX hash does not match its manifest")
        self.model_hash = actual_hash
        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
            sess_options=self._session_options(),
        )
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or inputs[0].name != "input":
            names = [meta.name for meta in inputs]
            raise ModelIntegrityError(f"Unexpected ONNX inputs: {names}")
        if len(outputs) != 1 or outputs[0].name != "logits":
            names = [meta.name for meta in outputs]
            raise ModelIntegrityError(f"Unexpected ONNX outputs: {names}")

    @staticmethod
    def _session_options() -> ort.SessionOptions:
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return options

    def predict(self, tensor: np.ndarray) -> ModelEvidence:
        array = np.asarray(tensor, dtype=np.float32)
        if array.shape == (3, 224, 224):
            array = array[None, ...]
        if array.ndim != 4 or array.shape[1:] != (3, 224, 224):
            raise ValueError(f"Expected (3,224,224) or (N,3,224,224), got {array.shape}")
        started = time.perf_counter()
        output = self.session.run(["logits"], {"input": array})[0]
        elapsed = (time.perf_counter() - started) * 1000.0
        if output.ndim != 2 or output.shape[0] < 1 or output.shape[1] != 11:
            raise ModelIntegrityError(f"Unexpected ONNX output shape: {output.shape}")
        logits = np.clip(output[0], -60.0, 60.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        return ModelEvidence(
            tuple(float(value) for value in probabilities[:10]),
            float(probabilities[10]),
            elapsed,
            self.model_hash,
        )
