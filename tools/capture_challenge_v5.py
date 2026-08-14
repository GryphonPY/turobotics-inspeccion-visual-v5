from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import cv2

from inspection_v5.board_tracker import BoardTracker, V5BoardConfig
from inspection_v5.contracts import FramePacket


def _plan() -> list[dict[str, object]]:
    plan: list[dict[str, object]] = []
    for index in range(1, 21):
        plan.append({"condition_id": f"OK_{index:02d}", "expected_verdict": "PASS", "missing_ids": []})
    for component in range(1, 11):
        for repeat in range(1, 3):
            plan.append({"condition_id": f"C{component:02d}_MISSING_{repeat}", "expected_verdict": "NO_PASS", "missing_ids": [f"C{component:02d}"]})
    for index in range(1, 11):
        plan.append({"condition_id": f"REARRANGED_{index:02d}", "expected_verdict": "NO_PASS", "missing_ids": []})
    for index in range(1, 11):
        plan.append({"condition_id": f"UNSAFE_{index:02d}", "expected_verdict": "UNRELIABLE", "missing_ids": []})
    return plan


def _draw(frame, text: str, line: int, color: tuple[int, int, int] = (255, 255, 255)) -> None:
    cv2.putText(frame, text[:110], (30, 48 + line * 38), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _select_capture_target(
    scheduled_condition: dict[str, object],
    previous_condition: dict[str, object] | None,
    repeat_requested: bool,
) -> tuple[dict[str, object], bool]:
    """Return the condition to record and whether it is a repeat attempt."""
    if repeat_requested and previous_condition is not None:
        return previous_condition, True
    return scheduled_condition, False


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the independent V5 adversarial challenge")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--start", type=int, default=0, help="Resume at zero-based cycle index")
    args = parser.parse_args()
    root = args.root.resolve()
    session_id = datetime.now(UTC).strftime("challenge_%Y%m%d_%H%M%S")
    session_dir = root / "data" / "v5" / "challenge" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = session_dir / "manifest.jsonl"
    board = BoardTracker(V5BoardConfig.from_json(root / "config" / "v5" / "runtime.json"))
    capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera {args.camera}")
    plan = _plan()
    previous_condition: dict[str, object] | None = None
    previous_record: dict[str, object] | None = None
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for cycle_index, scheduled_condition in enumerate(plan[args.start :], start=args.start):
            repeat_attempt = 0
            scheduled_captured = False
            while not scheduled_captured:
                scheduled_id = str(scheduled_condition["condition_id"])
                scheduled_expected = str(scheduled_condition["expected_verdict"])
                prompt = "ENSAMBLE COMPLETO; cambia posicion y giro" if scheduled_expected == "PASS" else "RETIRA: " + ",".join(scheduled_condition["missing_ids"]) if scheduled_condition["missing_ids"] else "REACOMODA o provoca captura insegura"
                repeat_requested = False
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        continue
                    _draw(frame, f"CICLO {cycle_index + 1}/60  {scheduled_id}", 0, (0, 210, 255))
                    _draw(frame, prompt, 1)
                    _draw(frame, "ENTER iniciar   R repetir anterior   ESC salir", 2, (180, 220, 180))
                    if previous_condition is None:
                        _draw(frame, "AUN NO HAY CAPTURA ANTERIOR", 3, (150, 150, 150))
                    cv2.imshow("V5 - captura challenge", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:
                        capture.release()
                        cv2.destroyAllWindows()
                        return 0
                    if key in (ord("r"), ord("R")) and previous_condition is not None:
                        repeat_requested = True
                        repeat_attempt += 1
                        break
                    if key in (13, 10):
                        break

                condition, is_repeat = _select_capture_target(scheduled_condition, previous_condition, repeat_requested)
                condition_id = str(condition["condition_id"])
                expected = str(condition["expected_verdict"])
                cycle_prefix = f"cycle_{cycle_index + 1:03d}"
                if is_repeat:
                    cycle_prefix += f"_repeat_{repeat_attempt:02d}"
                cycle_dir = session_dir / f"{cycle_prefix}_{condition_id}"
                cycle_dir.mkdir(parents=True, exist_ok=True)
                video_path = cycle_dir / "capture.avi"
                writer = None
                started = time.monotonic()
                frame_count = 0
                board_ok_count = 0
                while time.monotonic() - started < args.seconds:
                    ok, frame = capture.read()
                    if not ok:
                        continue
                    if writer is None:
                        height, width = frame.shape[:2]
                        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (width, height))
                    writer.write(frame)
                    observation = board.observe(FramePacket(frame_count, time.monotonic(), frame))
                    board_ok_count += int(observation.board_ok)
                    _draw(frame, f"GRABANDO {condition_id}  {time.monotonic() - started:.1f}s", 0, (0, 210, 255))
                    _draw(frame, f"TABLERO {'OK' if observation.board_ok else 'REVISAR'}", 1, (0, 255, 0) if observation.board_ok else (0, 0, 255))
                    cv2.imshow("V5 - captura challenge", frame)
                    if cv2.waitKey(1) & 0xFF == 27:
                        break
                    frame_count += 1
                if writer is not None:
                    writer.release()
                record = {
                    "session_id": session_id,
                    "cycle_id": cycle_index + 1,
                    "condition_id": condition_id,
                    "scheduled_condition_id": str(scheduled_condition["condition_id"]),
                    "is_repeat": is_repeat,
                    "repeat_of_cycle_id": previous_record["cycle_id"] if is_repeat and previous_record else None,
                    "expected_verdict": expected,
                    "missing_ids": condition["missing_ids"],
                    "split": "development" if cycle_index < 30 else "holdout",
                    "path": video_path.relative_to(root).as_posix(),
                    "frame_count": frame_count,
                    "board_ok_count": board_ok_count,
                    "sha256": _sha256(video_path) if video_path.exists() else "",
                }
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                manifest.flush()
                print(f"{cycle_index + 1}/60 {condition_id}{' (repeat)' if is_repeat else ''} frames={frame_count} board_ok={board_ok_count}")
                previous_condition = condition
                previous_record = record
                if not is_repeat:
                    scheduled_captured = True
    (session_dir / "challenge_holdout_manifest.json").write_text(
        json.dumps({"session_id": session_id, "holdout_cycles": list(range(31, 61)), "source": "manifest.jsonl"}, indent=2) + "\n",
        encoding="utf-8",
    )
    capture.release()
    cv2.destroyAllWindows()
    print(session_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
