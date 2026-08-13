from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from inspection_v4.capture import CaptureWizard, load_capture_frames_by_round
from inspection_v4.config import load_configs
from inspection_v4.board import BoardRectifier
from inspection_v4.storage import CaptureSession


def test_capture_loader_preserves_round_identity(tmp_path: Path) -> None:
    session = CaptureSession(tmp_path, "session_test")
    image = np.zeros((20, 20, 3), np.uint8)
    session.save_frame("OK", 0, image, group="round_01")
    session.save_frame("OK", 1, image, group="round_02")
    session.save_frame("C04_MISSING", 0, image, group="round_02")
    loaded = load_capture_frames_by_round(tmp_path, "session_test")
    assert sorted(loaded) == [1, 2]
    assert len(loaded[1]["OK"]) == 1
    assert set(loaded[2]) == {"OK", "C04_MISSING"}


def test_capture_round_saves_bounded_gray_roi(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    board, config, _ = load_configs(root)
    session = CaptureSession(tmp_path, "session_bounded")
    wizard = CaptureWizard(tmp_path, board, config, BoardRectifier(board), session)
    wizard.raw_frames = [
        np.zeros((board.roi_rect_px[3], board.roi_rect_px[2]), np.uint8)
        for _ in range(5)
    ]
    wizard.active = True
    wizard.finish_state(now=10.0)
    saved = next((tmp_path / "data" / "raw_sessions" / "session_bounded").rglob("frame_*.png"))
    image = cv2.imread(str(saved), cv2.IMREAD_UNCHANGED)
    assert image.shape == (board.roi_rect_px[3], board.roi_rect_px[2])
    assert image.ndim == 2
