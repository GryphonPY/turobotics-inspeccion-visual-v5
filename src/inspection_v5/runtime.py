from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread

import numpy as np

from .board_tracker import BoardTracker, V5BoardConfig
from .contracts import (
    ComponentPublicState,
    FramePacket,
    PublicState,
    RuntimeMetrics,
    TrackingMode,
    TrackingSnapshot,
)
from .diagnostics import RotatingJsonlLogger
from .latest_value import LatestValue
from .live_state import LiveConfig, LiveController, LiveState
from .presence import PresenceAnalyzer, PresenceConfig


class InspectionRuntime:
    def __init__(
        self,
        root: Path,
        inspector: Callable[[TrackingSnapshot], None] | None = None,
    ) -> None:
        self.root = root.resolve()
        raw = json.loads((self.root / "config" / "v5" / "runtime.json").read_text(encoding="utf-8"))
        board_config = V5BoardConfig.from_json(self.root / "config" / "v5" / "runtime.json")
        presence_raw = raw["presence"]
        self.tracker = BoardTracker(board_config)
        self.presence = PresenceAnalyzer(
            PresenceConfig(
                reference_area_px=float(presence_raw["reference_area_px"]),
                margin_px=int(presence_raw["margin_px"]),
                minimum_blob_area_px=int(presence_raw["minimum_blob_area_px"]),
                morphology_open_px=int(presence_raw["morphology_open_px"]),
                morphology_close_px=int(presence_raw["morphology_close_px"]),
            )
        )
        self.live = LiveController(
            LiveConfig(
                occupied_enter_ratio=float(presence_raw["occupied_enter_ratio"]),
                empty_exit_ratio=float(presence_raw["empty_exit_ratio"]),
                stability_seconds=float(presence_raw["stability_seconds"]),
                empty_confirm_seconds=float(presence_raw["empty_confirm_seconds"]),
                empty_confirm_observations=int(presence_raw["empty_confirm_observations"]),
            )
        )
        self.logger = RotatingJsonlLogger(self.root)
        self.frames: LatestValue[FramePacket] = LatestValue()
        self.tracking: LatestValue[TrackingSnapshot] = LatestValue()
        self.public: LatestValue[PublicState] = LatestValue()
        self.inspection_requests: LatestValue[TrackingSnapshot] = LatestValue()
        self._inspector = inspector
        self._stop = Event()
        self._thread: Thread | None = None
        self._inspection_thread: Thread | None = None
        self._sequence = 0
        self._last_frame_version = -1
        self._previous_roi: np.ndarray | None = None
        self._public_version = 0
        self._last_state = self.live.state
        self._last_metrics = RuntimeMetrics(log_path=str(self.logger.path))
        self._publish_public(
            TrackingSnapshot(0, 0.0, False, None, (0, 0, 0, 0), 0.0, 0.0, 0.0, reason="starting")
        )

    def publish_frame(self, bgr: np.ndarray, captured_at: float | None = None) -> int:
        self._sequence += 1
        packet = FramePacket(self._sequence, time.monotonic() if captured_at is None else captured_at, bgr)
        return self.frames.publish(packet)

    def start(self) -> InspectionRuntime:
        if self._thread is not None and self._thread.is_alive():
            return self
        self._stop.clear()
        self._thread = Thread(target=self._tracking_loop, name="v5-tracking", daemon=True)
        self._thread.start()
        if self._inspector is not None:
            self._inspection_thread = Thread(
                target=self._inspection_loop,
                name="v5-inspection",
                daemon=True,
            )
            self._inspection_thread.start()
        self.logger.event("INFO", "runtime_started")
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._inspection_thread is not None:
            self._inspection_thread.join(timeout=1.0)
        self._thread = None
        self._inspection_thread = None
        self.logger.event("INFO", "runtime_stopped")

    def latest_public_state(self) -> PublicState:
        _, state = self.public.read()
        if state is None:
            return PublicState()
        return state

    def latest_tracking(self) -> TrackingSnapshot | None:
        _, snapshot = self.tracking.read()
        return snapshot

    def request_inspection(self, snapshot: TrackingSnapshot) -> int:
        """Publish one inspection request; a newer request replaces an older one."""
        return self.inspection_requests.publish(snapshot)

    def _inspection_loop(self) -> None:
        last_version = -1
        while not self._stop.is_set():
            version, snapshot = self.inspection_requests.read(after_version=last_version)
            if snapshot is None:
                time.sleep(0.001)
                continue
            last_version = version
            started = time.perf_counter()
            try:
                self._inspector(snapshot)
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                self.logger.event(
                    "INFO",
                    "inspection_worker_finished",
                    sequence=snapshot.sequence,
                    stage_ms=elapsed_ms,
                )
            except Exception as exc:  # noqa: BLE001 - worker failures belong in diagnostics
                self.logger.event(
                    "ERROR",
                    "inspection_worker_exception",
                    repr(exc),
                    sequence=snapshot.sequence,
                )

    def _tracking_loop(self) -> None:
        while not self._stop.is_set():
            version, packet = self.frames.read(after_version=self._last_frame_version)
            if packet is None:
                time.sleep(0.001)
                continue
            self._last_frame_version = version
            started = time.perf_counter()
            try:
                tracked = self.tracker.observe(packet)
                presence = self.presence.measure(tracked.roi, self._previous_roi)
                self._previous_roi = tracked.roi.copy() if tracked.roi is not None else None
                tracked = replace(
                    tracked,
                    bbox=presence.bbox,
                    occupied_ratio=presence.occupied_ratio,
                    motion=presence.motion,
                    piece_focus=presence.piece_focus,
                    reason=presence.reason if tracked.board_ok and presence.reason else tracked.reason,
                )
                self.tracking.publish(tracked)
                event = self.live.update(presence, tracked.board_ok, time.monotonic())
                if event.start_inspection:
                    self.request_inspection(tracked)
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                self._last_metrics = RuntimeMetrics(
                    tracking_fps=1000.0 / max(elapsed_ms, 0.001),
                    stage_ms={"board_presence": elapsed_ms},
                    piece_focus=presence.piece_focus,
                    marker_focus=tracked.marker_focus,
                    occupied_ratio=presence.occupied_ratio,
                    motion=presence.motion,
                    log_path=str(self.logger.path),
                )
                if event.state != self._last_state:
                    self.logger.event(
                        "INFO",
                        "live_state_changed",
                        event.message,
                        state_from=self._last_state.value,
                        state_to=event.state.value,
                        sequence=packet.sequence,
                    )
                    self._last_state = event.state
                self._publish_public(tracked)
                self.logger.event(
                    "INFO",
                    "tracking_frame",
                    event.message,
                    sequence=packet.sequence,
                    state=event.state.value,
                    board_ok=tracked.board_ok,
                    occupied_ratio=presence.occupied_ratio,
                    motion=presence.motion,
                    piece_focus=presence.piece_focus,
                    stage_ms=elapsed_ms,
                )
            except Exception as exc:  # noqa: BLE001 - runtime must stay observable
                self.logger.event("ERROR", "tracking_exception", repr(exc), sequence=packet.sequence)

    def _publish_public(self, tracked: TrackingSnapshot) -> None:
        state = self.live.state
        if not tracked.board_ok:
            mode = TrackingMode.EMPTY
            headline = "REVISAR TABLERO"
            detail = "Asegura que los cuatro ArUco estén visibles"
            instruction = "TABLERO NO DISPONIBLE"
        elif state == LiveState.EMPTY:
            mode = TrackingMode.EMPTY
            headline = "ÁREA LIBRE"
            detail = "Coloca la pieza dentro del rectángulo"
            instruction = "LISTO PARA INSPECCIONAR"
        elif state in {LiveState.ENTERING, LiveState.STABILIZING}:
            mode = TrackingMode.STABILIZING
            headline = "ESTABILIZANDO"
            detail = "No muevas la pieza"
            instruction = "PREPARANDO CAPTURA"
        elif state == LiveState.INSPECTING:
            mode = TrackingMode.INSPECTING
            headline = "ANALIZANDO"
            detail = "Verificando ensamble"
            instruction = "ESPERA EL RESULTADO"
        elif state == LiveState.REMOVING:
            mode = TrackingMode.DETECTED
            headline = "RETIRANDO"
            detail = "Área vacía en confirmación"
            instruction = "COLOCA LA SIGUIENTE PIEZA"
        else:
            mode = TrackingMode.LOCKED
            headline = "RESULTADO MOSTRADO"
            detail = "Retira la pieza para continuar"
            instruction = "ESPERANDO ÁREA LIBRE"
        self._public_version += 1
        self.public.publish(
            PublicState(
                version=self._public_version,
                frame=tracked.roi,
                tracking_bbox=tracked.bbox,
                tracking_mode=mode,
                headline=headline,
                detail=detail,
                instruction=instruction,
                counters={"total": 0, "passed": 0, "failed": 0, "unreliable": 0},
                metrics=self._last_metrics,
                component_states={
                    f"C{index:02d}": ComponentPublicState.UNKNOWN
                    for index in range(1, 11)
                },
            )
        )
