from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from inspection_v5.contracts import ComponentPublicState, PublicState, TrackingMode, Verdict
from inspection_v5.ui.main_window import MainWindow


class FakeRuntime:
    def __init__(self, state: PublicState) -> None:
        self.state = state

    def latest_public_state(self) -> PublicState:
        return self.state

    def stop(self) -> None:
        return None


def state_for(name: str) -> PublicState:
    frame = np.full((560, 320), 24, dtype=np.uint8)
    cv2 = __import__("cv2")
    cv2.rectangle(frame, (80, 130), (240, 380), 180, -1)
    if name == "empty":
        return PublicState(frame=frame, tracking_mode=TrackingMode.EMPTY, version=1)
    if name == "pass":
        components = {f"C{i:02d}": ComponentPublicState.PRESENT for i in range(1, 11)}
        return PublicState(frame=frame, tracking_mode=TrackingMode.PASS, verdict=Verdict.PASS, component_states=components, counters={"passed": 12, "failed": 2, "unreliable": 1}, version=2)
    components = {f"C{i:02d}": ComponentPublicState.PRESENT for i in range(1, 11)}
    components["C08"] = ComponentPublicState.MISSING
    return PublicState(frame=frame, tracking_mode=TrackingMode.FAIL, verdict=Verdict.NO_PASS, component_states=components, counters={"passed": 12, "failed": 3, "unreliable": 1}, version=3)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    app = QApplication([])
    output_dir = root / "data" / "v5" / "reports" / "ui_review"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("empty", "pass", "fail"):
        window = MainWindow(FakeRuntime(state_for(name)), root)
        window.resize(1920, 1080)
        window.refresh()
        window.show()
        app.processEvents()
        window.grab().save(str(output_dir / f"{name}.png"))
        window.close()
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
