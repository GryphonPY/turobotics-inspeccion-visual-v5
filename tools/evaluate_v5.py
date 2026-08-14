from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import cv2

from inspection_v5.board_tracker import BoardTracker, V5BoardConfig
from inspection_v5.contracts import FramePacket
from inspection_v5.inspector import V5Inspector


def _load_records(root: Path, session: str, split: str) -> list[dict[str, object]]:
    session_dir = root / "data" / "v5" / "challenge" / session
    records = [json.loads(line) for line in (session_dir / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if split == "challenge-holdout":
        records = [record for record in records if record.get("split") == "holdout"]
        if not (session_dir / "challenge_holdout_manifest.json").exists():
            raise RuntimeError("Challenge holdout manifest is missing")
    return records


def _evaluate_clip(root: Path, record: dict[str, object], board: BoardTracker, inspector: V5Inspector) -> dict[str, object]:
    inspector.reset()
    video_path = root / str(record["path"])
    capture = cv2.VideoCapture(str(video_path))
    sequence = 0
    result = None
    valid_frames = 0
    latencies: list[float] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        started = time.perf_counter()
        observation = board.observe(FramePacket(sequence, time.monotonic(), frame))
        if observation.board_ok:
            valid_frames += 1
            result = inspector(observation)
            latencies.append((time.perf_counter() - started) * 1000.0)
        sequence += 1
    capture.release()
    actual = result.verdict.value if result is not None else "UNRELIABLE"
    expected = str(record["expected_verdict"])
    return {
        "cycle_id": record["cycle_id"],
        "condition_id": record["condition_id"],
        "expected_verdict": expected,
        "actual_verdict": actual,
        "valid_frames": valid_frames,
        "frames_used": result.frames_used if result is not None else 0,
        "latency_p95_ms": float(max(latencies)) if latencies else 0.0,
        "false_pass": bool(expected != "PASS" and actual == "PASS"),
        "false_reject": bool(expected == "PASS" and actual != "PASS"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a frozen V5 physical challenge")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--session", required=True)
    parser.add_argument("--split", choices=("challenge-holdout", "all"), default="challenge-holdout")
    args = parser.parse_args()
    root = args.root.resolve()
    records = _load_records(root, args.session, args.split)
    board = BoardTracker(V5BoardConfig.from_json(root / "config" / "v5" / "runtime.json"))
    inspector = V5Inspector(root)
    rows = [_evaluate_clip(root, record, board, inspector) for record in records]
    false_passes = [row for row in rows if row["false_pass"]]
    false_rejects = [row for row in rows if row["false_reject"]]
    result = {
        "session_id": args.session,
        "split": args.split,
        "sample_count": len(rows),
        "false_passes": len(false_passes),
        "false_rejects": len(false_rejects),
        "verdict_counts": dict(Counter(f"{row['expected_verdict']}->{row['actual_verdict']}" for row in rows)),
        "rows": rows,
        "release_ready": not false_passes,
    }
    output = root / "data" / "v5" / "reports" / f"challenge_{args.session}_{args.split}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("sample_count", "false_passes", "false_rejects", "verdict_counts", "release_ready")}, indent=2, ensure_ascii=False))
    return 0 if not false_passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
