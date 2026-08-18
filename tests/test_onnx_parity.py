from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("onnx")
pytest.importorskip("torchvision")

from inspection_v5.model_runtime import PresenceModel
from training_v5.export import export_model
from training_v5.model import V5PresenceNet, load_checkpoint


def test_exported_onnx_matches_pytorch(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    model_path = tmp_path / "model.onnx"
    manifest = tmp_path / "model.json"
    source = V5PresenceNet(pretrained=False).eval()
    torch.save(source.state_dict(), checkpoint)
    export_model(checkpoint, model_path, manifest)

    tensor = np.random.default_rng(8).random((2, 3, 224, 224), dtype=np.float32)
    pytorch = load_checkpoint(str(checkpoint))(torch.from_numpy(tensor)).detach().numpy()
    runtime = PresenceModel(model_path, manifest)
    onnx_output = runtime.session.run(["logits"], {"input": tensor})[0]

    assert np.max(np.abs(pytorch - onnx_output)) <= 1e-4
    assert json.loads(manifest.read_text(encoding="utf-8"))["model_sha256"] == runtime.model_hash


def test_manifest_mismatch_is_rejected(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    model_path = tmp_path / "model.onnx"
    manifest = tmp_path / "model.json"
    torch.save(V5PresenceNet(pretrained=False).state_dict(), checkpoint)
    export_model(checkpoint, model_path, manifest)
    model_path.write_bytes(model_path.read_bytes() + b"tampered")

    from inspection_v5.model_runtime import ModelIntegrityError

    with pytest.raises(ModelIntegrityError):
        PresenceModel(model_path, manifest)
