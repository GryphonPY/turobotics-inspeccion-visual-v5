from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from .board import BoardRectifier, draw_board_status
from .camera import LatestFrameCamera, enumerate_cameras, remember_camera, select_camera
from .components import ReferenceSet
from .config import load_configs
from .storage import InspectionLogger
from .types import Verdict
from .workflow import InspectionWorkflow, WorkflowState


ROOT = Path(__file__).resolve().parents[2]


def _load_reference(root: Path, component_ids: tuple[str, ...]) -> ReferenceSet:
    reference_dir = root / "data" / "references"
    metadata = reference_dir / "reference_set_v1.json"
    if not metadata.exists():
        raise FileNotFoundError(
            "No existe reference_set_v1. Ejecuta run_capture.ps1 y genera las 11 configuraciones "
            "antes de iniciar la demo."
        )
    reference = ReferenceSet.load(reference_dir)
    if reference.component_ids != component_ids:
        raise ValueError("La referencia no corresponde a los diez componentes configurados")
    return reference


def run_diagnostic(root: Path) -> int:
    board, inspection, camera_config = load_configs(root)
    cameras = enumerate_cameras(camera_config)
    print(json.dumps({
        "board": board.name,
        "roi_px": board.roi_rect_px,
        "required_markers": [0, 1, 2, 3],
        "cameras": [
            {
                **camera.__dict__,
                "eligible_for_demo": camera.width >= camera_config.minimum_width
                and camera.height >= camera_config.minimum_height,
            }
            for camera in cameras
        ],
    }, indent=2, ensure_ascii=False))
    return 0 if any(item.width >= camera_config.minimum_width and item.height >= camera_config.minimum_height for item in cameras) else 2


def run_demo(root: Path, camera_index: int | None = None) -> int:
    board, inspection, camera_config = load_configs(root)
    try:
        reference = _load_reference(root, inspection.component_ids)
    except (FileNotFoundError, ValueError) as exc:
        print(f"V4 no está calibrada: {exc}", file=sys.stderr)
        return 3
    rectifier = BoardRectifier(board)
    all_cameras = enumerate_cameras(camera_config)
    info = select_camera(all_cameras, camera_config, camera_index)
    if info is None:
        print("No se encontró una cámara compatible.", file=sys.stderr)
        return 2
    try:
        remember_camera(root / "config" / "camera.json", info)
    except (OSError, ValueError) as exc:
        print(f"Aviso: no se pudo guardar la cámara seleccionada: {exc}", file=sys.stderr)
    camera = LatestFrameCamera(info.index, camera_config, info.backend).start()
    if not camera.opened:
        print("La cámara seleccionada no pudo entregar una imagen con la resolución mínima.", file=sys.stderr)
        return 2
    camera.warmup()
    workflow = InspectionWorkflow(board, inspection, rectifier, reference)
    workflow.startup()
    logger = InspectionLogger(root)
    window = "Inspección Visual V4 — ESC salir"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 1280, 800)
    last_result = None
    last_reconnect_attempt = 0.0
    camera_message = f"Cámara {info.index} {info.width}x{info.height}"
    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                now = time.monotonic()
                workflow.state = WorkflowState.FAULT
                camera_message = "Cámara sin señal; intentando reconectar..."
                if now - last_reconnect_attempt >= 2.0:
                    last_reconnect_attempt = now
                    camera.release()
                    replacement = select_camera(
                        enumerate_cameras(camera_config),
                        camera_config,
                        camera_index,
                        prefer_saved=False,
                    )
                    if replacement is not None:
                        candidate = LatestFrameCamera(
                            replacement.index, camera_config, replacement.backend
                        ).start()
                        if candidate.opened:
                            camera = candidate
                            info = replacement
                            workflow.reset_cycle()
                            camera.warmup()
                            camera_message = f"Cámara {info.index} {info.width}x{info.height} reconectada"
                            try:
                                remember_camera(root / "config" / "camera.json", info)
                            except (OSError, ValueError):
                                pass
                        else:
                            candidate.release()
                fault = _fault_canvas(camera_message)
                cv2.imshow(window, fault)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
                time.sleep(0.02)
                continue
            if workflow.state == WorkflowState.FAULT:
                workflow.state = WorkflowState.BOARD_CHECK
            state, result = workflow.process_frame(frame)
            canonical, observation = rectifier.warp(frame)
            diagnostic = draw_board_status(
                canonical if canonical is not None else frame,
                observation,
            )
            canvas = _render_demo(
                _fit_image(diagnostic, 860, 800) if canonical is not None else diagnostic,
                state,
                workflow,
                result or last_result,
                f"{info.index} {info.width}x{info.height}",
            )
            cv2.imshow(window, canvas)
            if result is not None:
                last_result = result
                logger.log(result, {"camera_index": info.index, "camera_backend": info.backend})
                workflow.acknowledge_result()
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("r"):
                workflow.reset_cycle()
                last_result = None
            elif key == ord("z"):
                workflow.reset_counters()
                last_result = None
            elif key == ord("c"):
                workflow.reset_cycle()
                last_result = None
                candidates = [
                    item for item in enumerate_cameras(camera_config)
                    if item.width >= camera_config.minimum_width
                    and item.height >= camera_config.minimum_height
                    and item.index != info.index
                ]
                replacement = max(
                    candidates,
                    key=lambda item: item.width * item.height,
                    default=None,
                )
                if replacement is not None and replacement.index != info.index:
                    camera.release()
                    camera = LatestFrameCamera(
                        replacement.index, camera_config, replacement.backend
                    ).start()
                    if camera.opened:
                        info = replacement
                        camera.warmup()
                        camera_message = f"Cámara {info.index} {info.width}x{info.height}"
                        try:
                            remember_camera(root / "config" / "camera.json", info)
                        except (OSError, ValueError):
                            pass
            elif key == 32:
                workflow.reset_cycle()
                last_result = None
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return 0


def _fault_canvas(message: str) -> np.ndarray:
    canvas = np.full((800, 1280, 3), 18, dtype=np.uint8)
    cv2.putText(canvas, "INSPECCION V4", (44, 72), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (235, 235, 235), 3, cv2.LINE_AA)
    cv2.putText(canvas, "FAULT", (44, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 190, 255), 3, cv2.LINE_AA)
    cv2.putText(canvas, message[:72], (44, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (220, 220, 220), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Verifica el celular como webcam. Q/ESC = salir", (44, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (170, 170, 170), 1, cv2.LINE_AA)
    return canvas


def _render_demo(
    frame: np.ndarray,
    state: WorkflowState,
    workflow: InspectionWorkflow,
    result,
    camera_label: str = "",
) -> np.ndarray:
    if state not in {WorkflowState.DECIDED, WorkflowState.WAIT_REMOVAL}:
        result = None
    canvas = frame.copy()
    height, width = canvas.shape[:2]
    panel_x = max(0, width - 420)
    cv2.rectangle(canvas, (panel_x, 0), (width, height), (25, 25, 25), thickness=-1)
    cv2.putText(canvas, "INSPECCION V4", (panel_x + 24, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (235, 235, 235), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"ESTADO: {state.value}", (panel_x + 24, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (175, 175, 175), 1, cv2.LINE_AA)
    sheet_label = "OK" if state not in {WorkflowState.BOARD_CHECK, WorkflowState.FAULT} else "REVISAR"
    stability_label = "ESTABLE" if state != WorkflowState.STABILIZING else "ESTABILIZANDO"
    cv2.putText(canvas, f"CAM: {camera_label[:24]}", (panel_x + 24, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (190, 190, 190), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"HOJA: {sheet_label}", (panel_x + 24, 142), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (60, 220, 80) if sheet_label == "OK" else (0, 190, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"PIEZA: {stability_label}", (panel_x + 155, 142), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (60, 220, 80) if stability_label == "ESTABLE" else (0, 190, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"TOTAL: {workflow.counters.total}", (panel_x + 24, 177), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"PASA: {workflow.counters.passed}", (panel_x + 24, 203), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (60, 220, 80), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"NO PASA: {workflow.counters.failed}", (panel_x + 145, 203), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (70, 80, 240), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"INCIDENCIAS: {workflow.counters.unreliable}", (panel_x + 24, 229), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 190, 255), 1, cv2.LINE_AA)
    if result is not None:
        missing_ids = [item.component_id for item in result.evidence if not item.present and item.reason != "component_unresolved"]
        unresolved_ids = [item.component_id for item in result.evidence if item.reason == "component_unresolved"]
        if result.verdict == Verdict.PASS:
            color, label, reason_text = (60, 220, 80), "10/10 PRESENTES", "INSPECCION APROBADA"
        elif result.verdict == Verdict.UNRELIABLE:
            color, label = (0, 190, 255), "CAPTURA NO CONFIABLE"
            reason_text = (
                f"REVISAR {','.join(unresolved_ids)}" if unresolved_ids
                else _friendly_reason(result.reason)
            )
        else:
            color, label = (70, 80, 240), "NO PASA"
            if len(missing_ids) == 1:
                reason_text = f"9/10 — FALTA {missing_ids[0]}"
            else:
                reason_text = f"{10 - len(missing_ids)}/10 — FALTAN {','.join(missing_ids)}"
        cv2.putText(canvas, label, (panel_x + 22, 270), cv2.FONT_HERSHEY_SIMPLEX, 1.02, color, 3, cv2.LINE_AA)
        cv2.putText(canvas, reason_text[:33], (panel_x + 24, 304), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
        evidence_by_id = {item.component_id: item for item in result.evidence}
        y = 338
        for component_id in workflow.config.component_ids:
            item = evidence_by_id.get(component_id)
            unresolved = item is not None and item.reason == "component_unresolved"
            item_color = (135, 135, 135) if item is None else ((0, 190, 255) if unresolved else ((60, 220, 80) if item.present else (70, 80, 240)))
            item_label = "—" if item is None else ("REVISAR" if unresolved else ("OK" if item.present else "FALTA"))
            score = "" if item is None else f" {item.score:.2f}"
            cv2.putText(canvas, f"{component_id}: {item_label}{score}", (panel_x + 24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, item_color, 1, cv2.LINE_AA)
            y += 28
    cv2.putText(canvas, "R ciclo | Z contadores | C cámara | ESPACIO repetir", (panel_x + 24, height - 48), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1, cv2.LINE_AA)
    cv2.putText(canvas, "Q/ESC salir", (panel_x + 24, height - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (150, 150, 150), 1, cv2.LINE_AA)
    return canvas


def _friendly_reason(reason: str) -> str:
    return {
        "insufficient_valid_frames": "CAPTURA INSUFICIENTE",
        "alignment_unreliable": "ALINEACION NO CONFIABLE",
        "component_unresolved": "REVISAR CALIBRACION",
        "unresolved:C01": "REVISAR C01",
    }.get(reason, reason)


def _fit_image(image: np.ndarray, width: int, height: int) -> np.ndarray:
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(
        image,
        (max(1, int(image.shape[1] * scale)), max(1, int(image.shape[0] * scale))),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.full((height, width, 3), 18, dtype=np.uint8)
    y = (height - resized.shape[0]) // 2
    x = (width - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspección Visual V4")
    parser.add_argument("mode", choices=("demo", "diagnostic"), nargs="?", default="demo")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--camera", type=int, default=None)
    args = parser.parse_args()
    return run_diagnostic(args.root) if args.mode == "diagnostic" else run_demo(args.root, args.camera)


if __name__ == "__main__":
    raise SystemExit(main())
