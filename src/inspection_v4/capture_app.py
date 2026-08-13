from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .board import BoardRectifier, draw_board_status
from .camera import LatestFrameCamera, enumerate_cameras, remember_camera, select_camera
from .capture import CaptureSession, CaptureWizard, build_reference_from_session
from .component_guide import draw_component_guide
from .config import load_configs


ROOT = Path(__file__).resolve().parents[2]


def run_capture(root: Path, camera_index: int | None = None, session_id: str | None = None) -> int:
    board, inspection, camera_config = load_configs(root)
    info = select_camera(enumerate_cameras(camera_config), camera_config, camera_index)
    if info is None:
        print("No se encontró una cámara compatible.")
        return 2
    try:
        remember_camera(root / "config" / "camera.json", info)
    except (OSError, ValueError) as exc:
        print(f"Aviso: no se pudo guardar la cámara seleccionada: {exc}")
    session_id = session_id or datetime.now().strftime("session_%Y%m%d_%H%M%S")
    camera = LatestFrameCamera(info.index, camera_config, info.backend).start()
    if not camera.opened:
        print("La cámara seleccionada no pudo entregar una imagen con la resolución mínima.")
        return 2
    camera.warmup()
    wizard = CaptureWizard(
        root, board, inspection, BoardRectifier(board), CaptureSession(root, session_id)
    )
    window = "Captura V4 — 11 configuraciones"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 1280, 800)
    print(f"Sesión: {session_id}")
    print("Coloca el estado indicado. ENTER inicia una captura de 10 s; ESC cancela.")
    print("Se capturarán 7 rondas: 6 para calibración y 1 como evidencia independiente.")
    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                continue
            observation = wizard.rectifier.observe(frame)
            canonical, _ = wizard.rectifier.warp(frame)
            display = draw_board_status(canonical if canonical is not None else frame, observation)
            progress = wizard.progress()
            if canonical is not None:
                display = _fit_image(display, 820, 760)
            _draw_capture_panel(display, wizard, progress)
            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key in (13, 10) and not wizard.active:
                wizard.start_state()
                print(f"Grabando {wizard.state}: {wizard.current_instruction()}")
            if wizard.active:
                try:
                    wizard.add_frame(frame)
                except RuntimeError as exc:
                    print(str(exc))
                    wizard.last_error = str(exc)
                if (
                    not wizard.active
                    and not wizard.last_error
                    and wizard.state_index == 0
                    and wizard.round_index > 1
                ):
                    print(f"Ronda {wizard.round_index - 1} completa guardada.")
                    if wizard.round_index > 7:
                        print("Se alcanzaron siete rondas. Generando referencias con rondas 1-6...")
                        try:
                            path = build_reference_from_session(root, session_id, training_rounds=(1, 2, 3, 4, 5, 6))
                        except (RuntimeError, ValueError, OSError) as exc:
                            wizard.last_error = f"Calibración pendiente: {exc}"
                            print(wizard.last_error)
                        else:
                            print(f"Referencia generada: {path}")
                            break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return 0


def _draw_capture_panel(frame, wizard: CaptureWizard, progress) -> None:
    height, width = frame.shape[:2]
    panel_x = max(0, width - 480)
    cv2.rectangle(frame, (panel_x, 0), (width, height), (24, 24, 24), thickness=-1)
    cv2.putText(frame, "ASISTENTE DE CAPTURA", (panel_x + 22, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.82, (235, 235, 235), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Estado {wizard.state_index + 1}/{wizard.total_states}: {wizard.state}", (panel_x + 22, 83), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.putText(frame, wizard.current_instruction()[:42], (panel_x + 22, 124), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (185, 185, 185), 1, cv2.LINE_AA)
    cv2.putText(frame, f"Tiempo: {progress.seconds_remaining:04.1f} s", (panel_x + 22, 176), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (60, 220, 80) if wizard.active else (185, 185, 185), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Frames validos: {progress.valid_frames}", (panel_x + 22, 214), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.putText(frame, f"Ronda: {wizard.round_index}/7", (panel_x + 22, 252), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (220, 220, 220), 1, cv2.LINE_AA)
    guide = draw_component_guide(260, 320, wizard.state[:3] if wizard.state != "OK" else None)
    guide = cv2.resize(guide, (230, 285), interpolation=cv2.INTER_AREA)
    guide_y, guide_x = 295, panel_x + 20
    if guide_y + guide.shape[0] <= height and guide_x + guide.shape[1] <= width:
        frame[guide_y : guide_y + guide.shape[0], guide_x : guide_x + guide.shape[1]] = guide
    if wizard.last_error:
        cv2.putText(frame, wizard.last_error[:55], (panel_x + 22, height - 68), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (70, 80, 240), 1, cv2.LINE_AA)
    cv2.putText(frame, "ENTER iniciar | Q salir", (panel_x + 22, height - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1, cv2.LINE_AA)


def _fit_image(image, width: int, height: int):
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(image, (max(1, int(image.shape[1] * scale)), max(1, int(image.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    canvas = np.full((height, width, 3), 18, dtype=np.uint8)
    y = (height - resized.shape[0]) // 2
    x = (width - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description="Asistente de captura V4")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument("--session", default=None)
    args = parser.parse_args()
    return run_capture(args.root, args.camera, args.session)


if __name__ == "__main__":
    raise SystemExit(main())
