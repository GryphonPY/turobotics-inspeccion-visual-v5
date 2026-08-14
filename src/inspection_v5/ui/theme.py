from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFontDatabase

BG = "#09111F"
PANEL = "#111C2E"
PANEL_2 = "#16243A"
TEXT = "#F4F7FB"
MUTED = "#9FB0C7"
CYAN = "#35C2FF"
GREEN = "#35E36F"
AMBER = "#FFBF3F"
RED = "#FF4D5E"
GRAY = "#687A91"


def install_fonts() -> None:
    windows_dir = Path(os.environ.get("WINDIR", "C:/Windows"))
    for filename in ("segoeui.ttf", "segoeuib.ttf"):
        path = windows_dir / "Fonts" / filename
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


def stylesheet() -> str:
    return f"""
    QWidget {{ color: {TEXT}; font-family: 'Segoe UI', Arial, sans-serif; }}
    QMainWindow, QWidget#root {{ background: {BG}; }}
    QFrame#panel {{ background: {PANEL}; border: 1px solid #20324A; border-radius: 18px; }}
    QLabel#eyebrow {{ color: {MUTED}; font-size: 17px; font-weight: 700; letter-spacing: 2px; }}
    QLabel#title {{ color: {TEXT}; font-size: 28px; font-weight: 800; }}
    QLabel#headline {{ color: {TEXT}; font-size: 54px; font-weight: 850; }}
    QLabel#detail {{ color: {MUTED}; font-size: 25px; }}
    QLabel#instruction {{ color: {CYAN}; font-size: 22px; font-weight: 700; }}
    QLabel#counter {{ color: {MUTED}; font-size: 20px; }}
    QPushButton {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid #2A4363; border-radius: 12px; padding: 12px 18px; font-size: 18px; font-weight: 700; }}
    QPushButton:hover {{ border-color: {CYAN}; background: #1A3150; }}
    QPushButton:pressed {{ background: #203B5D; }}
    """
