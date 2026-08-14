from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class RotatingJsonlLogger:
    def __init__(self, root: Path, filename: str = "v5_runtime.jsonl", max_bytes: int = 10_000_000, backups: int = 5) -> None:
        self.path = root / "logs" / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.backups = backups
        self._lock = Lock()

    def _rotate_if_needed(self, extra_bytes: int) -> None:
        if not self.path.exists() or self.path.stat().st_size + extra_bytes <= self.max_bytes:
            return
        oldest = self.path.with_suffix(self.path.suffix + f".{self.backups}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backups - 1, 0, -1):
            source = self.path.with_suffix(self.path.suffix + f".{index}")
            target = self.path.with_suffix(self.path.suffix + f".{index + 1}")
            if source.exists():
                source.replace(target)
        self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))

    def event(self, level: str, name: str, message: str = "", **fields: Any) -> None:
        payload = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "timestamp_monotonic": time.monotonic(),
            "level": level,
            "event": name,
            "message": message,
            **fields,
        }
        line = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            self._rotate_if_needed(len(line))
            with self.path.open("ab") as handle:
                handle.write(line)
                handle.flush()

