from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BoardConfig:
    name: str
    page_mm: tuple[float, float]
    pixels_per_mm: float
    canonical_size_px: tuple[int, int]
    aruco_dictionary: str
    marker_size_mm: float
    markers: dict[int, dict[str, Any]]
    roi_mm: dict[str, float]
    roi_inner_margin_mm: float
    max_reprojection_error_px: float

    @property
    def width_px(self) -> int:
        return self.canonical_size_px[0]

    @property
    def height_px(self) -> int:
        return self.canonical_size_px[1]

    @property
    def roi_rect_px(self) -> tuple[int, int, int, int]:
        x = round(self.roi_mm["x"] * self.pixels_per_mm)
        y = round(self.roi_mm["y"] * self.pixels_per_mm)
        w = round(self.roi_mm["width"] * self.pixels_per_mm)
        h = round(self.roi_mm["height"] * self.pixels_per_mm)
        return x, y, w, h

    @property
    def roi_inner_margin_px(self) -> int:
        return round(self.roi_inner_margin_mm * self.pixels_per_mm)


@dataclass(frozen=True)
class InspectionConfig:
    component_ids: tuple[str, ...]
    min_component_area_px: int
    min_piece_area_fraction: float
    max_piece_area_fraction: float
    piece_margin_mm: float
    morphology_open_px: int
    morphology_close_px: int
    alignment_min_score: float
    alignment_scale_tolerance: float
    component_default_threshold: float
    component_min_advantage: float
    component_min_score: float
    quality_min_contrast: float
    quality_max_reprojection_px: float
    quality_min_laplacian: float
    quality_relative_blur_floor: float
    quality_max_marker_clipped_fraction: float
    quality_max_black_fraction: float
    quality_max_white_fraction: float
    quality_max_motion_mean: float
    stability_seconds: float
    collection_seconds: float
    min_valid_frames: int
    max_valid_frames: int
    frame_vote_fraction: float
    frame_spacing_seconds: float
    capture_sample_seconds: float
    capture_max_frames_per_state: int
    removal_seconds: float
    display_result_seconds: float


@dataclass(frozen=True)
class CameraConfig:
    max_index: int
    preferred_width: int
    preferred_height: int
    minimum_width: int
    minimum_height: int
    preferred_fps: int
    warmup_seconds: float
    read_timeout_seconds: float
    save_index: int | None
    save_backend: str | None
    backend_order: tuple[str, ...]


def _read(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_configs(root: Path) -> tuple[BoardConfig, InspectionConfig, CameraConfig]:
    config_dir = root / "config"
    board_raw = _read(config_dir / "board_letter_v1.json")
    inspection_raw = _read(config_dir / "inspection_v1.json")
    camera_raw = _read(config_dir / "camera.json")

    board = BoardConfig(
        name=board_raw["name"],
        page_mm=tuple(board_raw["page_mm"]),
        pixels_per_mm=float(board_raw["pixels_per_mm"]),
        canonical_size_px=tuple(board_raw["canonical_size_px"]),
        aruco_dictionary=board_raw["aruco_dictionary"],
        marker_size_mm=float(board_raw["marker_size_mm"]),
        markers={int(k): v for k, v in board_raw["markers"].items()},
        roi_mm=board_raw["roi_mm"],
        roi_inner_margin_mm=float(board_raw["roi_inner_margin_mm"]),
        max_reprojection_error_px=float(board_raw["max_reprojection_error_px"]),
    )
    inspection = InspectionConfig(
        component_ids=tuple(inspection_raw["component_ids"]),
        **{k: inspection_raw[k] for k in InspectionConfig.__dataclass_fields__ if k != "component_ids"},
    )
    camera = CameraConfig(
        **{
            **{k: camera_raw[k] for k in CameraConfig.__dataclass_fields__ if k != "backend_order"},
            "backend_order": tuple(camera_raw["backend_order"]),
        }
    )
    return board, inspection, camera
