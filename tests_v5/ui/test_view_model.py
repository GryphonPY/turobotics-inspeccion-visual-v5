from __future__ import annotations

from dataclasses import replace

import pytest

from inspection_v5.contracts import ComponentPublicState, PublicState, TrackingMode, Verdict
from inspection_v5.ui.view_model import PresentationViewModel


@pytest.mark.parametrize(
    ("verdict", "headline"),
    [(Verdict.PASS, "10/10 PRESENTES"), (Verdict.NO_PASS, "NO PASA"), (Verdict.UNRELIABLE, "CAPTURA NO CONFIABLE")],
)
def test_public_headlines(verdict: Verdict, headline: str) -> None:
    state = replace(PublicState(tracking_mode=TrackingMode.LOCKED), verdict=verdict)

    assert PresentationViewModel.from_public_state(state).headline == headline


def test_public_model_always_contains_ten_components() -> None:
    state = PublicState(component_states={"C01": ComponentPublicState.PRESENT})

    model = PresentationViewModel.from_public_state(state)

    assert list(model.component_states) == [f"C{i:02d}" for i in range(1, 11)]
    assert all("WAIT_" not in value for value in (model.headline, model.detail, model.instruction))


def test_no_pass_without_specific_missing_component_is_not_reported_as_missing() -> None:
    state = PublicState(
        verdict=Verdict.NO_PASS,
        component_states={f"C{i:02d}": ComponentPublicState.UNKNOWN for i in range(1, 11)},
    )

    model = PresentationViewModel.from_public_state(state)

    assert model.detail == "No se confirmaron los 10 componentes"
