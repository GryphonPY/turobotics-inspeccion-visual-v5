from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    data = np.load(root / "data" / "v5" / "references" / "reference_v1.npz")
    gray = data["gray"]
    mask = data["mask"] > 127
    canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    canvas[mask] = (235, 235, 235)
    for x in range(0, 321, 32):
        cv2.line(canvas, (x, 0), (x, 559), (70, 70, 70), 1)
    for y in range(0, 561, 56):
        cv2.line(canvas, (0, y), (319, y), (70, 70, 70), 1)
    output = root / "data" / "v5" / "reports" / "reference_v1.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), canvas)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
