from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFontDatabase

# Neutral industrial console. Result colors carry meaning; the rest stays
# grayscale so the screen does not compete with the inspected piece.
BG = "#101010"
PANEL = "#1C1C1C"
PANEL_2 = "#292929"
TEXT = "#F3F3F3"
MUTED = "#B0B0B0"
CYAN = "#D9D9D9"  # compatibility name; intentionally neutral, not blue
GREEN = "#62D47A"
AMBER = "#D9B66F"
RED = "#E47777"
GRAY = "#858585"
LINE = "#484848"


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
    QFrame#panel {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; }}
    QLabel#eyebrow {{ color: {MUTED}; font-size: 16px; font-weight: 700; letter-spacing: 2px; }}
    QLabel#brand {{ color: {TEXT}; font-size: 29px; font-weight: 850; letter-spacing: 1px; }}
    QLabel#headerDivider {{ color: {GRAY}; font-size: 29px; font-weight: 400; }}
    QLabel#title {{ color: {TEXT}; font-size: 29px; font-weight: 750; letter-spacing: 1px; }}
    QLabel#headline {{ color: {TEXT}; font-size: 42px; font-weight: 850; }}
    QLabel#detail {{ color: {MUTED}; font-size: 22px; }}
    QLabel#instruction {{ color: {CYAN}; font-size: 19px; font-weight: 700; }}
    QFrame#stats {{ background: transparent; }}
    QFrame#statCard {{ background: {PANEL_2}; border: 1px solid {LINE}; border-radius: 6px; }}
    QLabel#statValue {{ font-size: 23px; font-weight: 850; }}
    QLabel#statLabel {{ color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
    QPushButton {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid #626262; border-radius: 6px; padding: 10px 16px; font-size: 17px; font-weight: 700; }}
    QPushButton:hover {{ border-color: {TEXT}; background: #383838; }}
    QPushButton:pressed {{ background: #444444; }}
    """
