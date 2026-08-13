from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np

from inspection_v4.capture import CAPTURE_STATES, build_reference_from_session
from inspection_v4.components import ReferenceSet
from inspection_v4.config import load_configs
from inspection_v4.storage import CaptureSession


def _connected_ten_component_piece(shape: tuple[int, int]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    height, width = shape
    complete = np.zeros(shape, np.uint8)
    parts: dict[str, np.ndarray] = {}
    x_positions = (width // 2 - 70, width // 2)
    for index, component_id in enumerate((f"C{i:02d}" for i in range(1, 11))):
        row, column = divmod(index, 2)
        x = x_positions[column]
        y = 280 + row * 72
        mask = np.zeros(shape, np.uint8)
        cv2.rectangle(mask, (x, y), (x + 90, y + 88), 255, thickness=-1)
        parts[component_id] = mask
        complete = cv2.bitwise_or(complete, mask)
    return complete, parts


def test_reference_builder_accepts_bounded_gray_capture_format(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    shutil.copytree(source_root / "config", tmp_path / "config")
    board, _, _ = load_configs(tmp_path)
    complete, parts = _connected_ten_component_piece((board.roi_rect_px[3], board.roi_rect_px[2]))
    session = CaptureSession(tmp_path, "session_roi_format")
    for state in CAPTURE_STATES:
        image = complete if state == "OK" else cv2.subtract(complete, parts[state[:3]])
        for frame_index in range(5):
            session.save_frame(state, frame_index, image, group="round_01")

    output = build_reference_from_session(tmp_path, session.session_id, training_rounds=(1,))
    reference = ReferenceSet.load(tmp_path / "data" / "references")
    assert output.exists()
    assert reference.complete_mask.shape == (board.roi_rect_px[3], board.roi_rect_px[2])
    assert reference.unresolved_components == ()
