from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from inspection_v4.board import BoardRectifier
from inspection_v4.config import load_configs
from inspection_v4.quality import assess_frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    board, config, _ = load_configs(args.root)
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"No se pudo leer {args.image}")
    rectifier = BoardRectifier(board)
    canonical, observation = rectifier.warp(image)
    report = assess_frame(canonical, observation, board, config) if canonical is not None else None
    print({
        "found_ids": observation.found_ids,
        "reprojection_error_px": observation.reprojection_error_px,
        "reason": observation.reason,
        "quality": report.metrics if report else None,
        "quality_valid": report.valid if report else False,
    })
    if canonical is not None and args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.output), canonical)
    return 0 if canonical is not None and report and report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
