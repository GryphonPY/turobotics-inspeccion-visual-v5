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
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for cycle_index, condition in enumerate(plan[args.start :], start=args.start):
            condition_id = str(condition["condition_id"])
            expected = str(condition["expected_verdict"])
            prompt = "ENSAMBLE COMPLETO; cambia posicion y giro" if expected == "PASS" else "RETIRA: " + ",".join(condition["missing_ids"]) if condition["missing_ids"] else "REACOMODA o provoca captura insegura"
            while True:
                ok, frame = capture.read()
                if not ok:
                    continue
                _draw(frame, f"CICLO {cycle_index + 1}/60  {condition_id}", 0, (0, 210, 255))
                _draw(frame, prompt, 1)
                _draw(frame, "ENTER iniciar   R repetir anterior   ESC salir", 2, (180, 220, 180))
                cv2.imshow("V5 - captura challenge", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    capture.release()
                    cv2.destroyAllWindows()
                    return 0
                if key in (13, 10):
                    break
            cycle_dir = session_dir / f"cycle_{cycle_index + 1:03d}_{condition_id}"
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
            print(f"{cycle_index + 1}/60 {condition_id} frames={frame_count} board_ok={board_ok_count}")
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
