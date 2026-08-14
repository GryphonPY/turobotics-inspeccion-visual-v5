from __future__ import annotations

import numpy as np

from inspection_v5.live_state import LiveConfig, LiveController, LiveState
from inspection_v5.presence import PresenceMetrics


def metrics(occupied: float, motion: float = 0.0) -> PresenceMetrics:
    return PresenceMetrics(occupied, motion, 100.0, (1, 1, 10, 10), np.zeros((20, 20), np.uint8), 42.0, 24.0, 0.0)


def feed(controller: LiveController, occupied: float, motion: float, at: float, board_ok: bool = True):
    return controller.update(metrics(occupied, motion), board_ok, at)


def test_complete_live_cycle_releases_after_fast_empty() -> None:
    controller = LiveController(LiveConfig())
    feed(controller, occupied=0.50, motion=3.0, at=0.00)
    feed(controller, occupied=0.50, motion=0.2, at=0.10)
    event = feed(controller, occupied=0.50, motion=0.2, at=0.46)
    assert event.start_inspection
    controller.result_ready()
    feed(controller, occupied=0.08, motion=2.0, at=0.60)
    feed(controller, occupied=0.08, motion=0.1, at=0.72)
    event = feed(controller, occupied=0.08, motion=0.1, at=0.82)
    assert event.cycle_released
    assert event.state is LiveState.EMPTY


def test_missing_board_does_not_release_result() -> None:
    controller = LiveController()
    feed(controller, 0.5, 0.0, 0.0)
    feed(controller, 0.5, 0.0, 0.4)
    controller.result_ready()

    event = feed(controller, 0.0, 0.0, 0.7, board_ok=False)

    assert not event.cycle_released
    assert controller.state is LiveState.RESULT


def test_replacement_before_empty_confirmation_does_not_start_duplicate_cycle() -> None:
    controller = LiveController()
    feed(controller, 0.5, 0.0, 0.0)
    feed(controller, 0.5, 0.0, 0.4)
    controller.result_ready()
    feed(controller, 0.05, 0.0, 0.5)

    event = feed(controller, 0.5, 0.0, 0.6)

    assert not event.cycle_released
    assert controller.state is LiveState.RESULT


def test_isolated_motion_spike_does_not_reset_stability() -> None:
    controller = LiveController(LiveConfig(stability_seconds=0.35))
    feed(controller, occupied=0.50, motion=0.0, at=0.00)
    feed(controller, occupied=0.50, motion=0.0, at=0.10)
    feed(controller, occupied=0.50, motion=3.0, at=0.20)
    feed(controller, occupied=0.50, motion=0.0, at=0.30)
    event = feed(controller, occupied=0.50, motion=0.0, at=0.50)

    assert event.start_inspection
