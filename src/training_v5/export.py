from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import onnx
import torch

from .model import load_checkpoint


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_model(checkpoint_path: Path, output_path: Path, manifest_path: Path) -> dict[str, object]:
    model = load_checkpoint(str(checkpoint_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros((1, 3, 224, 224), dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )
    onnx.checker.check_model(onnx.load(str(output_path)))
    manifest = {
        "version": "presence_v1",
        "model_sha256": _sha256(output_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "input": {"name": "input", "shape": [None, 3, 224, 224], "dtype": "float32"},
        "output": {"name": "logits", "shape": [None, 11], "labels": [f"C{i:02d}" for i in range(1, 11)] + ["GLOBAL"]},
        "data_version": "reference_v1",
        "onnx_opset": 17,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the V5 model to verified ONNX")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_model(args.checkpoint, args.output, args.manifest), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
