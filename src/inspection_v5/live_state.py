from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from statistics import median

from .presence import PresenceMetrics


class LiveState(str, Enum):
    EMPTY = "EMPTY"
    ENTERING = "ENTERING"
    STABILIZING = "STABILIZING"
    READY = "READY"
    INSPECTING = "INSPECTING"
    RESULT = "RESULT"
    REMOVING = "REMOVING"


@dataclass(frozen=True)
class LiveConfig:
    occupied_enter_ratio: float = 0.35
    empty_exit_ratio: float = 0.12
    motion_stable_max: float = 1.0
    stability_seconds: float = 0.35
    empty_confirm_seconds: float = 0.20
    empty_confirm_observations: int = 3


@dataclass(frozen=True)
class LiveEvent:
    state: LiveState
    start_inspection: bool = False
    cancel_inspection: bool = False
    cycle_released: bool = False
    message: str = ""


class LiveController:
    def __init__(self, config: LiveConfig | None = None) -> None:
        self.config = config or LiveConfig()
        self.state = LiveState.EMPTY
        self._stable_since: float | None = None
        self._empty_since: float | None = None
        self._empty_observations = 0
        self._motion_history: deque[float] = deque(maxlen=3)

    def _event(
        self,
        message: str,
        *,
        start_inspection: bool = False,
        cancel_inspection: bool = False,
        cycle_released: bool = False,
    ) -> LiveEvent:
        return LiveEvent(
            self.state,
            start_inspection=start_inspection,
            cancel_inspection=cancel_inspection,
            cycle_released=cycle_released,
            message=message,
        )

    def result_ready(self) -> LiveEvent:
        if self.state not in {LiveState.INSPECTING, LiveState.READY}:
            return self._event("RESULTADO NO ESPERADO")
        self.state = LiveState.RESULT
        self._empty_since = None
        self._empty_observations = 0
        return self._event("RESULTADO LISTO")

    def reset(self) -> None:
        self.state = LiveState.EMPTY
        self._stable_since = None
        self._empty_since = None
        self._empty_observations = 0
        self._motion_history.clear()

    def update(self, metrics: PresenceMetrics, board_ok: bool, now: float) -> LiveEvent:
        occupied = metrics.occupied_ratio >= self.config.occupied_enter_ratio
        empty = metrics.occupied_ratio <= self.config.empty_exit_ratio

        if not board_ok:
            self._stable_since = None
            self._motion_history.clear()
            if self.state == LiveState.REMOVING:
                self._empty_since = None
                self._empty_observations = 0
            return self._event("REVISAR TABLERO")

        if empty:
            self._motion_history.clear()
        else:
            self._motion_history.append(metrics.motion)
        stable_motion = (
            metrics.motion
            if len(self._motion_history) < self._motion_history.maxlen
            else median(self._motion_history)
        )
        stable = bool(self._motion_history) and stable_motion <= self.config.motion_stable_max

        if self.state == LiveState.EMPTY:
            if occupied:
                self.state = LiveState.ENTERING
                self._stable_since = now if stable else None
                return self._event("PIEZA DETECTADA")
            return self._event("ÁREA LIBRE")

        if self.state == LiveState.ENTERING:
            if empty:
                self.state = LiveState.EMPTY
                self._stable_since = None
                return self._event("ÁREA LIBRE")
            if not stable:
                self._stable_since = None
                self.state = LiveState.STABILIZING
                return self._event("ESTABILIZANDO")
            if self._stable_since is None:
                self._stable_since = now
            if now - self._stable_since >= self.config.stability_seconds:
                self.state = LiveState.INSPECTING
                return self._event("ANALIZANDO", start_inspection=True)
            self.state = LiveState.STABILIZING
            return self._event("ESTABILIZANDO")

        if self.state == LiveState.STABILIZING:
            if empty:
                self.state = LiveState.EMPTY
                self._stable_since = None
                return self._event("ÁREA LIBRE")
            if not stable:
                self._stable_since = None
                return self._event("ESTABILIZANDO")
            if self._stable_since is None:
                self._stable_since = now
            if now - self._stable_since >= self.config.stability_seconds:
                self.state = LiveState.INSPECTING
                return self._event("ANALIZANDO", start_inspection=True)
            return self._event("ESTABILIZANDO")

        if self.state == LiveState.INSPECTING:
            if empty:
                self.state = LiveState.REMOVING
                self._empty_since = now
                self._empty_observations = 1
                return self._event("RETIRANDO", cancel_inspection=True)
            return self._event("ANALIZANDO")

        if self.state == LiveState.RESULT:
            if empty:
                self.state = LiveState.REMOVING
                self._empty_since = now
                self._empty_observations = 1
                return self._event("RETIRANDO")
            return self._event("RESULTADO MOSTRADO")

        if self.state == LiveState.REMOVING:
            if not empty:
                self._empty_since = None
                self._empty_observations = 0
                self.state = LiveState.RESULT
                return self._event("RETIRADA NO CONFIRMADA")
            self._empty_observations += 1
            elapsed = now - (self._empty_since or now)
            if (
                elapsed >= self.config.empty_confirm_seconds
                and self._empty_observations >= self.config.empty_confirm_observations
            ):
                self.reset()
                return self._event("ÁREA LIBRE", cycle_released=True)
            return self._event("RETIRANDO")

        return self._event("ESTADO NO RECONOCIDO")
