from __future__ import annotations

from dataclasses import dataclass

from ..contracts import ComponentPublicState, PublicState, TrackingMode, Verdict
from .theme import AMBER, CYAN, GRAY, GREEN, RED


@dataclass(frozen=True)
class PresentationViewModel:
    headline: str
    detail: str
    instruction: str
    accent: str
    tracking_mode: TrackingMode
    component_states: dict[str, ComponentPublicState]
    show_result: bool
    counters: dict[str, int]

    @classmethod
    def from_public_state(cls, state: PublicState) -> PresentationViewModel:
        if state.verdict is Verdict.PASS:
            headline, detail, accent, show_result = "10/10 PRESENTES", "INSPECCIÓN APROBADA", GREEN, True
            components = {
                f"C{index:02d}": state.component_states.get(
                    f"C{index:02d}", ComponentPublicState.UNKNOWN
                )
                for index in range(1, 11)
            }
        elif state.verdict is Verdict.NO_PASS:
            if any(r in state.reasons for r in ("outside_mass_detected", "silhouette_incompatible")):
                detail = "FORMA NO RECONOCIDA / PIEZAS FUERA DE LUGAR"
                components = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
            else:
                missing = [name for name, value in state.component_states.items() if value is ComponentPublicState.MISSING]
                if not missing:
                    detail = "No se confirmaron los 10 componentes"
                    components = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
                else:
                    detail = f"FALTAN {', '.join(missing)}"
                    components = {
                        f"C{index:02d}": state.component_states.get(
                            f"C{index:02d}", ComponentPublicState.UNKNOWN
                        )
                        for index in range(1, 11)
                    }
            headline, accent, show_result = "NO PASA", RED, True
        elif state.verdict is Verdict.UNRELIABLE:
            headline, detail, accent, show_result = "CAPTURA NO CONFIABLE", "Repite con la pieza quieta", AMBER, True
            components = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
        elif state.tracking_mode is TrackingMode.STABILIZING:
            headline, detail, accent, show_result = "ESTABILIZANDO", "No muevas la pieza", AMBER, False
            components = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
        elif state.tracking_mode is TrackingMode.INSPECTING:
            headline, detail, accent, show_result = "ANALIZANDO", "Verificando ensamble", AMBER, False
            components = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
        elif state.tracking_mode is TrackingMode.EMPTY:
            headline, detail, accent, show_result = "ÁREA LIBRE", "Coloca la pieza dentro del tablero", GRAY, False
            components = {f"C{index:02d}": ComponentPublicState.UNKNOWN for index in range(1, 11)}
        else:
            headline, detail, accent, show_result = state.headline, state.detail, CYAN, False
            components = {
                f"C{index:02d}": state.component_states.get(
                    f"C{index:02d}", ComponentPublicState.UNKNOWN
                )
                for index in range(1, 11)
            }
        return cls(headline, detail, state.instruction, accent, state.tracking_mode, components, show_result, dict(state.counters))
