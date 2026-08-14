from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description="Render V5 component anchors")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    anchors = json.loads((root / "config" / "v5" / "component_anchors.json").read_text(encoding="utf-8"))
    image = np.full((224, 224, 3), (9, 17, 31), dtype=np.uint8)
    for index, (component_id, anchor) in enumerate(anchors.items()):
        x0 = round(float(anchor["x"]) * 224)
        y0 = round(float(anchor["y"]) * 224)
        x1 = round((float(anchor["x"]) + float(anchor["width"])) * 224)
        y1 = round((float(anchor["y"]) + float(anchor["height"])) * 224)
        color = (40 + (index * 37) % 180, 80 + (index * 53) % 150, 180 + (index * 17) % 70)
        cv2.rectangle(image, (x0, y0), (x1, y1), color, 2)
        cv2.putText(image, component_id, (x0 + 3, y0 + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    output = root / "data" / "v5" / "reports" / "component_anchors.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), image)
    print(f"Rendered {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
