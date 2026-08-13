from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .types import InspectionResult


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class InspectionLogger:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "data" / "inspection_v4.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, result: InspectionResult, extra: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "verdict": result.verdict.value,
            "reason": result.reason,
            "valid_frames": result.valid_frames,
            "component_votes": result.component_votes,
            "cycle_id": result.cycle_id,
            "elapsed_seconds": result.elapsed_seconds,
            "evidence": [asdict(item) for item in result.evidence],
            "diagnostics": result.diagnostics,
        }
        if extra:
            payload.update(extra)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        export_csv(self.path, self.root / "data" / "inspection_v4.csv")


class CaptureSession:
    def __init__(self, root: Path, session_id: str) -> None:
        self.root = root
        self.session_id = session_id
        self.path = root / "data" / "raw_sessions" / session_id
        self.path.mkdir(parents=True, exist_ok=True)

    def save_frame(self, state: str, index: int, image: np.ndarray, group: str | None = None) -> Path:
        state_dir = self.path / group / state if group else self.path / state
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / f"frame_{index:04d}.png"
        if not cv2.imwrite(str(path), image):
            raise OSError(f"No se pudo guardar {path}")
        return path

    def save_manifest(self, payload: dict[str, Any], suffix: str | None = None) -> Path:
        filename = f"manifest_{suffix}.json" if suffix else "manifest.json"
        path = self.path / filename
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path


def export_csv(jsonl_path: Path, csv_path: Path) -> None:
    rows: list[dict[str, Any]] = []
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    columns = ["timestamp_utc", "cycle_id", "verdict", "reason", "valid_frames", "elapsed_seconds"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
