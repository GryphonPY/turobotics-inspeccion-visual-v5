from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def _write(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write fixture: {path}")


def _synthetic_board() -> np.ndarray:
    config = json.loads((Path(__file__).resolve().parents[1] / "config" / "v5" / "runtime.json").read_text(encoding="utf-8"))
    width, height = config["canonical_size_px"]
    scale = float(config["pixels_per_mm"])
    image = np.full((height, width, 3), 24, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    patch = round(50 * scale)
    quiet = round(7 * scale)
    for marker_id, marker in config["markers"].items():
        x = round(float(marker["x_mm"]) * scale)
        y = round(float(marker["y_mm"]) * scale)
        size = round(float(marker["size_mm"]) * scale)
        canvas = np.full((patch, patch, 3), 255, dtype=np.uint8)
        marker_image = cv2.aruco.generateImageMarker(dictionary, int(marker_id), size)
        canvas[quiet : quiet + size, quiet : quiet + size] = cv2.cvtColor(marker_image, cv2.COLOR_GRAY2BGR)
        image[y - quiet : y - quiet + patch, x - quiet : x - quiet + patch] = canvas
    return image


def build_fixtures(root: Path) -> list[dict[str, object]]:
    source = root / "data" / "raw_sessions" / "session_20260813_001845"
    complete = _read(source / "round_01" / "OK" / "frame_0000.png")
    missing = {
        f"missing_c{index:02d}": _read(source / "round_01" / f"C{index:02d}_MISSING" / "frame_0000.png")
        for index in range(1, 11)
    }
    fixtures_dir = root / "tests_v5" / "fixtures"
    fixture_images: dict[str, np.ndarray] = {
        "complete": complete,
        "missing_c01": missing["missing_c01"],
        "missing_c08": missing["missing_c08"],
        "missing_c10": missing["missing_c10"],
        "blurred": cv2.GaussianBlur(complete, (31, 31), 0),
        "bad_light": np.clip(complete.astype(np.float32) * 0.22 + 8.0, 0, 255).astype(np.uint8),
    }

    reference = np.load(root / "data" / "v5" / "references" / "reference_v1.npz")
    reference_gray = reference["gray"]
    reference_mask = reference["mask"] > 127
    background = int(np.median(reference_gray[~reference_mask]))
    empty = reference_gray.copy()
    empty[reference_mask] = background
    fixture_images["empty"] = cv2.cvtColor(empty, cv2.COLOR_GRAY2BGR)

    # A displaced local block is a deterministic structural challenge, not a color cue.
    rearranged = complete.copy()
    block = rearranged[160:330, 210:430].copy()
    rearranged[160:330, 210:430] = background
    rearranged[120:290, 250:470] = block
    fixture_images["rearranged"] = rearranged

    hand = complete.copy()
    polygon = np.array([[150, 380], [490, 380], [560, 700], [80, 700]], dtype=np.int32)
    cv2.fillPoly(hand, [polygon], (220, 220, 220))
    fixture_images["hand"] = hand

    # This fixture intentionally has no ArUco board; the campaign must reject it as unsafe.
    fixture_images["board_incomplete"] = complete

    manifest_rows: list[dict[str, object]] = []
    expected = {
        "complete": ("PASS", "complete"),
        "missing_c01": ("NO_PASS", "missing_component"),
        "missing_c08": ("NO_PASS", "missing_component"),
        "missing_c10": ("NO_PASS", "missing_component"),
        "rearranged": ("NO_PASS", "geometry"),
        "empty": ("UNRELIABLE", "empty"),
        "blurred": ("UNRELIABLE", "quality"),
        "hand": ("UNRELIABLE", "invasive_object"),
        "bad_light": ("UNRELIABLE", "quality"),
        "board_incomplete": ("UNRELIABLE", "board"),
    }
    for name, image in fixture_images.items():
        filename = f"{name}.png"
        path = fixtures_dir / filename
        _write(path, image)
        verdict, reason = expected[name]
        manifest_rows.append(
            {
                "id": name,
                "path": f"tests_v5/fixtures/{filename}",
                "input_kind": "board" if name == "board_incomplete" else "roi",
                "expected_verdict": verdict,
                "expected_reason_family": reason,
                "sha256": _sha256(path),
            }
        )
    manifest_path = fixtures_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"version": 1, "fixtures": manifest_rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write(fixtures_dir / "board_complete.png", _synthetic_board())
    return manifest_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Create deterministic V5 regression fixtures")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    rows = build_fixtures(args.root.resolve())
    print(json.dumps({"fixture_count": len(rows), "manifest": "tests_v5/fixtures/manifest.json"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
