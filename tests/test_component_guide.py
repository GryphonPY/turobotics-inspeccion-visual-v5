from __future__ import annotations

import numpy as np

from inspection_v4.component_guide import draw_component_guide


def test_component_guide_keeps_c09_and_c10_inside_canvas() -> None:
    image = draw_component_guide(300, 260, active="C10", round_index=1)

    assert image.shape == (260, 300, 3)
    # C10 is the lower-right block. Its highlighted fill must still be visible
    # in the lower part of the guide instead of being clipped by the canvas.
    lower_right = image[207:230, 150:230]
    assert np.any(np.all(lower_right == (70, 80, 240), axis=2))
