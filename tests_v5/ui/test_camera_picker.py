from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QDialog

from inspection_v5 import camera_picker


def test_choose_camera_releases_preview_before_main_camera_starts(monkeypatch, tmp_path: Path) -> None:
    released = False

    class FakeDialog:
        def __init__(self, root: Path, indices: list[int], selected: int) -> None:
            del root, indices, selected

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def selected_index(self) -> int:
            return 1

        def release_capture(self) -> None:
            nonlocal released
            released = True

    monkeypatch.setattr(camera_picker, "_scan_indices", lambda: [1])
    monkeypatch.setattr(camera_picker, "CameraPicker", FakeDialog)

    selected = camera_picker.choose_camera(tmp_path, object())

    assert selected == 1
    assert released is True
    saved = json.loads((tmp_path / "config" / "v5" / "camera.json").read_text(encoding="utf-8"))
    assert saved["index"] == 1
