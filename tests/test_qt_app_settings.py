from __future__ import annotations

from pathlib import Path

from inspection_v5.qt_app import _camera_settings

ROOT = Path(__file__).resolve().parents[1]


def test_camera_settings_are_loaded_from_runtime_config() -> None:
    assert _camera_settings(ROOT) == (1920, 1080, 30, 8)
