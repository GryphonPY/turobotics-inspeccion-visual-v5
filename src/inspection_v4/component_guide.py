from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ComponentGuide:
    component_id: str
    description: str


# The names are intentionally positional and color-independent. During capture,
# keep the yellow head at the top while removing the requested component.
COMPONENT_GUIDE = (
    ComponentGuide("C01", "superior izquierda"),
    ComponentGuide("C02", "superior derecha"),
    ComponentGuide("C03", "fila superior, izquierda"),
    ComponentGuide("C04", "fila superior, derecha"),
    ComponentGuide("C05", "pieza vertical central superior"),
    ComponentGuide("C06", "fila central, izquierda"),
    ComponentGuide("C07", "fila central, derecha"),
    ComponentGuide("C08", "pieza vertical central inferior"),
    ComponentGuide("C09", "base inferior izquierda"),
    ComponentGuide("C10", "base inferior derecha"),
)


def component_description(component_id: str) -> str:
    if component_id == "OK":
        return "ensamble completo: 10 componentes"
    for guide in COMPONENT_GUIDE:
        if guide.component_id == component_id:
            return guide.description
    return "componente no definido"


def draw_component_guide(width: int = 260, height: int = 420, active: str | None = None) -> np.ndarray:
    """Draw a color-independent numbered schematic for the capture assistant."""
    image = np.full((height, width, 3), 24, dtype=np.uint8)
    white = (225, 225, 225)
    highlight = (60, 220, 80)
    missing = (70, 80, 240)
    x0, y0 = 55, 22
    unit_w, unit_h = 64, 32
    boxes = {
        "C01": (x0 + 25, y0, unit_w, unit_h),
        "C02": (x0 + 92, y0, unit_w, unit_h),
        "C03": (x0, y0 + 38, unit_w, unit_h),
        "C04": (x0 + 67, y0 + 38, unit_w, unit_h),
        "C05": (x0 + 42, y0 + 76, unit_w, unit_h + 8),
        "C06": (x0, y0 + 122, unit_w, unit_h),
        "C07": (x0 + 67, y0 + 122, unit_w, unit_h),
        "C08": (x0 + 42, y0 + 160, unit_w, unit_h + 8),
        "C09": (x0, y0 + 206, unit_w, unit_h),
        "C10": (x0 + 67, y0 + 206, unit_w, unit_h),
    }
    for component_id, (x, y, w, h) in boxes.items():
        color = missing if component_id == active else white
        cv2.rectangle(image, (x, y), (x + w, y + h), color, thickness=2)
        cv2.putText(image, component_id, (x + 7, y + h // 2 + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    cv2.putText(image, "cabeza arriba", (x0 + 52, y0 + 265), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (175, 175, 175), 1, cv2.LINE_AA)
    cv2.putText(image, "rojo = retirar", (x0 + 52, y0 + 290), cv2.FONT_HERSHEY_SIMPLEX, 0.45, missing, 1, cv2.LINE_AA)
    return image
