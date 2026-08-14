from __future__ import annotations

from pathlib import Path

import numpy as np

from inspection_v5.contracts import TrackingMode
from inspection_v5.runtime import InspectionRuntime
from inspection_v5.ui.component_map import ComponentMap
from inspection_v5.ui.main_window import MainWindow
from inspection_v5.ui.video_view import TrackingVideoView

ROOT = Path(__file__).resolve().parents[2]


def test_component_map_keeps_all_tiles_visible(qtbot) -> None:
    widget = ComponentMap()
    widget.resize(420, 250)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(20)
    assert widget.grab().size().width() == 420
    assert widget.grab().size().height() == 250


def test_video_view_accepts_gray_and_color_frames(qtbot) -> None:
    widget = TrackingVideoView()
    qtbot.addWidget(widget)
    widget.resize(800, 500)
    widget.set_frame(np.zeros((560, 320), dtype=np.uint8))
    widget.set_tracking((70, 110, 180, 280), TrackingMode.STABILIZING, "ESTABILIZANDO")
    widget.show()
    qtbot.wait(20)
    assert not widget.grab().isNull()
    widget.set_frame(np.zeros((560, 320, 3), dtype=np.uint8))


def test_main_window_renders_at_television_size(qtbot) -> None:
    runtime = InspectionRuntime(ROOT)
    window = MainWindow(runtime, ROOT)
    qtbot.addWidget(window)
    window.resize(1280, 720)
    window.show()
    qtbot.wait(30)

    assert window.video.width() >= 780
    assert window.panel.width() <= 460
    assert not window.grab().isNull()
