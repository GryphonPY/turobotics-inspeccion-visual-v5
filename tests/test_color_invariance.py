from __future__ import annotations

import cv2
import numpy as np

from inspection_v5.presence import PresenceAnalyzer, PresenceConfig


def test_presence_is_equal_after_hue_change() -> None:
    image = cv2.imread("tests_v5/fixtures/complete.png", cv2.IMREAD_COLOR)
    assert image is not None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hsv[..., 0] = (hsv[..., 0].astype(np.int16) + 70).astype(np.uint8)
    shifted = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    analyzer = PresenceAnalyzer(PresenceConfig(reference_area_px=19_000.0, margin_px=8, minimum_blob_area_px=12))

    original = analyzer.measure(image)
    recolored = analyzer.measure(shifted)

    assert abs(original.occupied_ratio - recolored.occupied_ratio) < 0.02
