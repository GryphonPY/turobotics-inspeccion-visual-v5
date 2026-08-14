from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import cv2

from inspection_v5.board_tracker import BoardTracker, V5BoardConfig
from inspection_v5.contracts import FramePacket, TrackingSnapshot, Verdict
from inspection_v5.inspector import V5Inspector


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    path: Path
    input_kind: str
    expected_verdict: str
    expected_reason_family: str
    sha256: str


@dataclass(frozen=True)
class CampaignResult:
    total: int
    passed: int
    failed: int
    false_passes: int
    false_rejects: int
    latencies: tuple[float, ...]
    artifact_hashes: dict[str, str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_fixture_manifest(root: Path, manifest_path: Path | None = None) -> list[Fixture]:
    path = (root / "tests_v5" / "fixtures" / "manifest.json") if manifest_path is None else manifest_path
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("fixtures")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Fixture manifest is empty")
    fixtures: list[Fixture] = []
    for row in rows:
        fixture = Fixture(
            fixture_id=str(row["id"]),
            path=root / str(row["path"]),
            input_kind=str(row["input_kind"]),
            expected_verdict=str(row["expected_verdict"]),
            expected_reason_family=str(row["expected_reason_family"]),
            sha256=str(row["sha256"]),
        )
        if not fixture.path.exists():
            raise FileNotFoundError(f"Missing fixture: {fixture.path}")
        actual_hash = sha256_file(fixture.path)
        if actual_hash != fixture.sha256:
            raise ValueError(f"Fixture hash mismatch: {fixture.fixture_id}")
        fixtures.append(fixture)
    return fixtures


def _git_revision(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _roi_snapshot(image, sequence: int) -> TrackingSnapshot:
    return TrackingSnapshot(
        sequence=sequence,
        captured_at=time.monotonic(),
        board_ok=True,
        roi=image,
        bbox=(0, 0, image.shape[1], image.shape[0]),
        occupied_ratio=0.0,
        motion=0.0,
        piece_focus=0.0,
    )


def _inspect_roi(inspector: V5Inspector, image) -> tuple[str, int, float, tuple[str, ...]]:
    inspector.reset()
    result = None
    started = time.perf_counter()
    for sequence in range(9):
        result = inspector(_roi_snapshot(image, sequence)) or result
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if result is None:
        return Verdict.UNRELIABLE.value, 0, elapsed_ms, ("insufficient_frames",)
    return result.verdict.value, result.frames_used, elapsed_ms, result.reasons


def run_fixture_campaign(root: Path, manifest_path: Path | None = None, output: Path | None = None) -> dict[str, object]:
    fixtures = load_fixture_manifest(root, manifest_path)
    inspector = V5Inspector(root)
    board = BoardTracker(V5BoardConfig.from_json(root / "config" / "v5" / "runtime.json"))
    rows: list[dict[str, object]] = []
    artifact_hashes: dict[str, str] = {}
    for fixture in fixtures:
        image = cv2.imread(str(fixture.path), cv2.IMREAD_COLOR)
        if image is None:
            raise OSError(f"Could not read fixture: {fixture.path}")
        artifact_hashes[fixture.fixture_id] = fixture.sha256
        started = time.perf_counter()
        if fixture.input_kind == "board":
            observation = board.observe(FramePacket(0, time.monotonic(), image))
            actual = Verdict.UNRELIABLE.value if not observation.board_ok else "UNRELIABLE"
            frames_used = 0
            reasons = (observation.reason or "board_unavailable",)
        else:
            actual, frames_used, _, reasons = _inspect_roi(inspector, image)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        rows.append(
            {
                "fixture_id": fixture.fixture_id,
                "expected_verdict": fixture.expected_verdict,
                "expected_reason_family": fixture.expected_reason_family,
                "actual_verdict": actual,
                "frames_used": frames_used,
                "latency_ms": elapsed_ms,
                "false_pass": fixture.expected_verdict != Verdict.PASS.value and actual == Verdict.PASS.value,
                "false_reject": fixture.expected_verdict == Verdict.PASS.value and actual != Verdict.PASS.value,
                "reasons": list(reasons),
            }
        )
    false_passes = sum(bool(row["false_pass"]) for row in rows)
    false_rejects = sum(bool(row["false_reject"]) for row in rows)
    result = {
        "schema_version": 1,
        "kind": "fixture_campaign",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": _git_revision(root),
        "fixture_count": len(fixtures),
        "evaluated_count": len(rows),
        "false_passes": false_passes,
        "false_rejects": false_rejects,
        "release_ready": false_passes == 0 and false_rejects == 0,
        "artifact_hashes": artifact_hashes,
        "rows": rows,
    }
    output_path = output or root / "data" / "v5" / "reports" / f"fixtures_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


_PHYSICAL_EXPECTED = {
    "complete": Verdict.PASS.value,
    "single_missing": Verdict.NO_PASS.value,
    "double_missing": Verdict.NO_PASS.value,
    "rearranged": Verdict.NO_PASS.value,
    "outside": Verdict.UNRELIABLE.value,
    "hand": Verdict.UNRELIABLE.value,
    "marker": Verdict.UNRELIABLE.value,
    "blur": Verdict.UNRELIABLE.value,
    "bad_light": Verdict.UNRELIABLE.value,
}

_UNSAFE_SCENARIOS = {"outside", "hand", "marker", "blur", "bad_light"}


def release_schedule() -> list[dict[str, str | None]]:
    """Return the complete physical release schedule without editable labels."""
    schedule: list[dict[str, str | None]] = []
    for repeat in range(1, 101):
        schedule.append({"condition_id": f"COMPLETE_{repeat:03d}", "scenario": "complete", "detail": None})
    for component in range(1, 11):
        component_id = f"C{component:02d}"
        for repeat in range(1, 21):
            schedule.append(
                {
                    "condition_id": f"{component_id}_MISSING_{repeat:02d}",
                    "scenario": "single_missing",
                    "detail": component_id,
                }
            )
    for scenario in ("double_missing", "rearranged", "outside", "hand", "marker", "blur", "bad_light"):
        for repeat in range(1, 21):
            schedule.append(
                {"condition_id": f"{scenario.upper()}_{repeat:03d}", "scenario": scenario, "detail": None}
            )
    return schedule


def _accepted_actual(scenario: str, actual: str) -> bool:
    expected = _PHYSICAL_EXPECTED[scenario]
    if scenario in _UNSAFE_SCENARIOS:
        return actual in {Verdict.UNRELIABLE.value, Verdict.NO_PASS.value}
    return actual == expected


def _campaign_metrics(rows: list[dict[str, object]], requested_count: int, max_false_rejects: int = 0) -> dict[str, object]:
    false_passes = sum(bool(row["false_pass"]) for row in rows)
    false_rejects = sum(
        row["scenario"] == "complete" and row["actual_verdict"] != Verdict.PASS.value for row in rows
    )
    incorrect_count = sum(not bool(row["correct"]) for row in rows)
    non_complete_incorrect_count = sum(
        row["scenario"] != "complete" and not bool(row["correct"]) for row in rows
    )
    return {
        "false_passes": false_passes,
        "false_rejects": false_rejects,
        "incorrect_count": incorrect_count,
        "non_complete_incorrect_count": non_complete_incorrect_count,
        "release_ready": (
            len(rows) == requested_count
            and false_passes == 0
            and non_complete_incorrect_count == 0
            and false_rejects <= max_false_rejects
        ),
    }


def _release_result(root: Path, schedule: list[dict[str, str | None]], rows: list[dict[str, object]]) -> dict[str, object]:
    complete_rows = [row for row in rows if row["scenario"] == "complete"]
    metrics = _campaign_metrics(rows, len(schedule), max_false_rejects=1)
    return {
        "schema_version": 1,
        "kind": "physical_release_full",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": _git_revision(root),
        "requested_count": len(schedule),
        "completed_count": len(rows),
        "expected_complete_count": 100,
        "complete_pass_count": sum(row["actual_verdict"] == Verdict.PASS.value for row in complete_rows),
        **metrics,
        "correct_count": sum(bool(row["correct"]) for row in rows),
        "rows": rows,
    }


def _write_release_result(result: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_path.with_suffix(output_path.suffix + ".sha256").write_text(
        f"{sha256_file(output_path)}  {output_path.name}\n", encoding="utf-8"
    )


def _load_release_resume_rows(
    path: Path, schedule: list[dict[str, str | None]], git_revision: str
) -> list[dict[str, object]]:
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    if not path.exists() or not checksum_path.exists():
        return []
    try:
        expected_hash = checksum_path.read_text(encoding="utf-8").split()[0]
        if expected_hash != sha256_file(path):
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, IndexError, json.JSONDecodeError):
        return []
    if (
        not isinstance(raw, dict)
        or raw.get("kind") != "physical_release_full"
        or raw.get("git_revision") != git_revision
        or raw.get("requested_count") != len(schedule)
    ):
        return []
    rows = raw.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) >= len(schedule):
        return []
    for expected, row in zip(schedule, rows, strict=False):
        if not isinstance(row, dict):
            return []
        if any(row.get(key) != expected[key] for key in ("condition_id", "scenario", "detail")):
            return []
    return [dict(row) for row in rows]


def _select_release_output(
    root: Path,
    schedule: list[dict[str, str | None]],
    output: Path | None,
    resume: bool,
) -> tuple[Path, list[dict[str, object]]]:
    revision = _git_revision(root)
    reports_dir = root / "data" / "v5" / "reports"
    if output is not None:
        rows = _load_release_resume_rows(output, schedule, revision) if resume else []
        return output, rows
    if resume and reports_dir.exists():
        for candidate in sorted(reports_dir.glob("physical_release_full_*.json"), reverse=True):
            rows = _load_release_resume_rows(candidate, schedule, revision)
            if rows:
                return candidate, rows
    return reports_dir / f"physical_release_full_{datetime.now(UTC):%Y%m%d_%H%M%S}.json", []


def _scenario_instruction(scenario: str, detail: str | None) -> str:
    if scenario == "complete":
        return "COLOCA EL ENSAMBLE COMPLETO; cambia posición y giro"
    if scenario == "single_missing":
        return f"RETIRA SOLAMENTE {detail}" if detail else "RETIRA EL COMPONENTE INDICADO"
    if scenario == "double_missing":
        return "RETIRA DOS COMPONENTES"
    if scenario == "rearranged":
        return "REACOMODA EL ENSAMBLE; conserva una silueta parecida pero incorrecta"
    if scenario == "outside":
        return "COLOCA LA PIEZA PARCIALMENTE FUERA DEL RECTÁNGULO"
    if scenario == "hand":
        return "DEJA UNA MANO INVADIENDO EL ÁREA DE INSPECCIÓN"
    if scenario == "marker":
        return "CUBRE PARCIALMENTE UN MARCADOR DE LA HOJA"
    if scenario == "blur":
        return "PROVOCA DESENFOQUE O MOVIMIENTO CONTROLADO"
    if scenario == "bad_light":
        return "PROVOCA REFLEJO O ILUMINACIÓN DEFICIENTE"
    return "PREPARA LA ESCENA INDICADA"


def rehearsal_schedule() -> list[tuple[str, str | None]]:
    """Return the visible 30/30 rehearsal with an explicit missing component."""
    return [("complete", None)] * 30 + [
        ("single_missing", f"C{(index % 10) + 1:02d}") for index in range(30)
    ]


def _open_camera(camera_index: int) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera {camera_index}")
    return capture


def _capture_physical_cycle(
    capture: cv2.VideoCapture,
    board: BoardTracker,
    inspector: V5Inspector,
    cycle_id: int,
    scenario: str,
    seconds: float,
    detail: str | None = None,
    condition_id: str | None = None,
) -> dict[str, object] | None:
    while True:
        ok, frame = capture.read()
        if not ok:
            continue
        cv2.putText(frame, f"CICLO {cycle_id}  {condition_id or scenario}", (30, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 210, 255), 2)
        cv2.putText(frame, _scenario_instruction(scenario, detail)[:90], (30, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 220, 180), 2)
        cv2.putText(frame, "ENTER iniciar  ESC salir", (30, 124), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 220, 180), 2)
        cv2.imshow("V5 - bateria fisica", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            return None
        if key in (10, 13):
            break
    inspector.reset()
    valid_frames = 0
    result = None
    latencies: list[float] = []
    started = time.monotonic()
    sequence = 0
    while time.monotonic() - started < seconds:
        ok, frame = capture.read()
        if not ok:
            continue
        observation = board.observe(FramePacket(sequence, time.monotonic(), frame))
        if observation.board_ok:
            valid_frames += 1
            infer_started = time.perf_counter()
            result = inspector(observation) or result
            latencies.append((time.perf_counter() - infer_started) * 1000.0)
        label = "TABLERO OK" if observation.board_ok else "REVISAR TABLERO"
        color = (0, 255, 0) if observation.board_ok else (0, 0, 255)
        cv2.putText(frame, f"GRABANDO {label}", (30, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        cv2.imshow("V5 - bateria fisica", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            return None
        sequence += 1
    actual = result.verdict.value if result is not None else Verdict.UNRELIABLE.value
    return {
        "cycle_id": cycle_id,
        "scenario": scenario,
        "detail": detail,
        "condition_id": condition_id or f"{scenario}_{cycle_id:03d}",
        "expected_verdict": _PHYSICAL_EXPECTED[scenario],
        "actual_verdict": actual,
        "valid_frames": valid_frames,
        "frames_used": result.frames_used if result is not None else 0,
        "latency_p95_ms": max(latencies) if latencies else 0.0,
        "false_pass": _PHYSICAL_EXPECTED[scenario] != Verdict.PASS.value and actual == Verdict.PASS.value,
        "correct": _accepted_actual(scenario, actual),
    }


def run_physical_campaign(root: Path, scenario: str, count: int, camera_index: int, seconds: float, output: Path | None = None) -> dict[str, object]:
    capture = _open_camera(camera_index)
    board = BoardTracker(V5BoardConfig.from_json(root / "config" / "v5" / "runtime.json"))
    inspector = V5Inspector(root)
    rows: list[dict[str, object]] = []
    try:
        for cycle_id in range(1, count + 1):
            row = _capture_physical_cycle(capture, board, inspector, cycle_id, scenario, seconds)
            if row is None:
                break
            rows.append(row)
    finally:
        capture.release()
        cv2.destroyAllWindows()
    metrics = _campaign_metrics(rows, count)
    result = {
        "schema_version": 1,
        "kind": "physical_release",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": _git_revision(root),
        "scenario": scenario,
        "requested_count": count,
        "completed_count": len(rows),
        **metrics,
        "correct_count": sum(bool(row["correct"]) for row in rows),
        "rows": rows,
    }
    output_path = output or root / "data" / "v5" / "reports" / f"physical_release_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_path.with_suffix(output_path.suffix + ".sha256").write_text(
        f"{sha256_file(output_path)}  {output_path.name}\n", encoding="utf-8"
    )
    return result


def run_rehearsal(root: Path, camera_index: int, seconds: float, output: Path | None = None) -> dict[str, object]:
    schedule = rehearsal_schedule()
    capture = _open_camera(camera_index)
    board = BoardTracker(V5BoardConfig.from_json(root / "config" / "v5" / "runtime.json"))
    inspector = V5Inspector(root)
    rows: list[dict[str, object]] = []
    try:
        for cycle_id, (scenario, detail) in enumerate(schedule, start=1):
            row = _capture_physical_cycle(
                capture,
                board,
                inspector,
                cycle_id,
                scenario,
                seconds,
                detail=detail,
                condition_id=f"REHEARSAL_{cycle_id:03d}",
            )
            if row is None:
                break
            rows.append(row)
    finally:
        capture.release()
        cv2.destroyAllWindows()
    duplicate_cycle_ids = len(rows) - len({int(row["cycle_id"]) for row in rows})
    result = {
        "schema_version": 1,
        "kind": "rehearsal",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": _git_revision(root),
        "requested_count": len(schedule),
        "completed_count": len(rows),
        "expected_passes": 30,
        "actual_correct": sum(bool(row["correct"]) for row in rows),
        "false_passes": sum(bool(row["false_pass"]) for row in rows),
        "duplicate_cycle_ids": duplicate_cycle_ids,
        "release_ready": (
            len(rows) == len(schedule)
            and all(bool(row["correct"]) for row in rows)
            and not any(bool(row["false_pass"]) for row in rows)
            and duplicate_cycle_ids == 0
        ),
        "rows": rows,
    }
    output_path = output or root / "data" / "v5" / "reports" / f"rehearsal_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_path.with_suffix(output_path.suffix + ".sha256").write_text(
        f"{sha256_file(output_path)}  {output_path.name}\n", encoding="utf-8"
    )
    return result


def run_full_release_campaign(
    root: Path,
    camera_index: int,
    seconds: float,
    output: Path | None = None,
    resume: bool = True,
) -> dict[str, object]:
    schedule = release_schedule()
    output_path, rows = _select_release_output(root, schedule, output, resume)
    capture = _open_camera(camera_index)
    board = BoardTracker(V5BoardConfig.from_json(root / "config" / "v5" / "runtime.json"))
    inspector = V5Inspector(root)
    try:
        for cycle_id, condition in enumerate(schedule[len(rows) :], start=len(rows) + 1):
            row = _capture_physical_cycle(
                capture,
                board,
                inspector,
                cycle_id,
                str(condition["scenario"]),
                seconds,
                detail=condition["detail"],
                condition_id=str(condition["condition_id"]),
            )
            if row is None:
                break
            rows.append(row)
            _write_release_result(_release_result(root, schedule, rows), output_path)
    finally:
        capture.release()
        cv2.destroyAllWindows()
    result = _release_result(root, schedule, rows)
    _write_release_result(result, output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V5 fixture or physical release campaigns")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mode", choices=("fixtures", "physical", "release", "rehearsal"), default="fixtures")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--scenario", choices=tuple(_PHYSICAL_EXPECTED))
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fresh", action="store_true", help="start a new full release campaign instead of resuming")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "fixtures":
        result = run_fixture_campaign(root, args.manifest, args.output)
    elif args.mode == "physical":
        if args.scenario is None:
            parser.error("--scenario is required with --mode physical")
        result = run_physical_campaign(root, args.scenario, args.count, args.camera, args.seconds, args.output)
    elif args.mode == "release":
        result = run_full_release_campaign(root, args.camera, args.seconds, args.output, resume=not args.fresh)
    else:
        result = run_rehearsal(root, args.camera, args.seconds, args.output)
    print(json.dumps({key: result[key] for key in ("kind", "false_passes", "release_ready")}, indent=2))
    return 0 if bool(result["release_ready"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
