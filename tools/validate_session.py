from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspection_v4.capture import CAPTURE_STATES, load_capture_frames_by_round


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida una sesión V4 antes de generar referencias")
    parser.add_argument("session_id")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    rounds = load_capture_frames_by_round(args.root, args.session_id)
    report = {
        "session_id": args.session_id,
        "rounds": {},
        "calibration_rounds_ready": True,
        "holdout_round_ready": False,
    }
    for round_number, states in sorted(rounds.items()):
        counts = {state: len(states.get(state, [])) for state in CAPTURE_STATES}
        ready = all(counts[state] >= 5 for state in CAPTURE_STATES)
        report["rounds"][str(round_number)] = {
            "ready": ready,
            "states": counts,
            "total_frames": sum(counts.values()),
        }
    for required_round in range(1, 7):
        if not report["rounds"].get(str(required_round), {}).get("ready", False):
            report["calibration_rounds_ready"] = False
    report["holdout_round_ready"] = report["rounds"].get("7", {}).get("ready", False)
    report["ready_for_reference"] = report["calibration_rounds_ready"] and report["holdout_round_ready"]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ready_for_reference"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
