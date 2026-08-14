from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_public_launchers_use_pythonw_and_the_v5_module() -> None:
    bat = (ROOT / "ABRIR_DEMO_V5.bat").read_text(encoding="utf-8")
    vbs = (ROOT / "ABRIR_DEMO_V5.vbs").read_text(encoding="utf-8")

    assert "pythonw.exe" in bat
    assert "inspection_v5.qt_app" in bat
    assert "Run" in vbs
    assert "ABRIR_DEMO_V5.bat" in vbs
