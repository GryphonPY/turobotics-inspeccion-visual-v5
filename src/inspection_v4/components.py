from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import cv2
import numpy as np

from .config import InspectionConfig
from .types import AlignedPiece, ComponentEvidence


def _as_u8(mask: np.ndarray) -> np.ndarray:
    return (mask > 127).astype(np.uint8) * 255


def _median_image(images: Sequence[np.ndarray]) -> np.ndarray:
    if not images:
        raise ValueError("No hay imágenes para construir una referencia")
    stack = np.stack(images, axis=0).astype(np.float32)
    return np.median(stack, axis=0).astype(np.uint8)


def _normalized_gray(gray: np.ndarray) -> np.ndarray:
    gray = gray.astype(np.float32)
    low, high = np.percentile(gray, (2, 98))
    if high - low < 1.0:
        return np.zeros_like(gray, dtype=np.uint8)
    return np.clip((gray - low) * 255.0 / (high - low), 0, 255).astype(np.uint8)


@dataclass
class ReferenceSet:
    """Frozen complete/missing signatures used by the V4 decision engine."""

    component_ids: tuple[str, ...]
    complete_mask: np.ndarray
    complete_gray: np.ndarray
    component_regions: dict[str, np.ndarray]
    missing_masks: dict[str, np.ndarray]
    missing_gray: dict[str, np.ndarray] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    version: str = "reference_set_v1"
    source_manifest: dict[str, object] = field(default_factory=dict)
    unresolved_components: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.component_ids:
            raise ValueError("La referencia no tiene componentes")
        if self.complete_mask.ndim != 2 or self.complete_gray.ndim != 2:
            raise ValueError("Las referencias deben ser imágenes monocromas")
        if self.complete_mask.shape != self.complete_gray.shape:
            raise ValueError("La máscara y el gris completo deben tener el mismo tamaño")
        for component_id in self.component_ids:
            if component_id not in self.component_regions:
                raise ValueError(f"Falta la región {component_id}")
            if component_id not in self.missing_masks:
                raise ValueError(f"Falta la máscara ausente {component_id}")
            if component_id not in self.missing_gray:
                raise ValueError(f"Falta la imagen ausente {component_id}")
            if self.component_regions[component_id].shape != self.complete_mask.shape:
                raise ValueError(f"Región con tamaño incorrecto: {component_id}")
        if not set(self.unresolved_components).issubset(self.component_ids):
            raise ValueError("La referencia contiene componentes UNRESOLVED desconocidos")

    def save(self, directory: Path) -> None:
        self.validate()
        directory.mkdir(parents=True, exist_ok=True)
        arrays: dict[str, np.ndarray] = {
            "complete_mask": _as_u8(self.complete_mask),
            "complete_gray": self.complete_gray.astype(np.uint8),
        }
        for component_id in self.component_ids:
            arrays[f"region_{component_id}"] = _as_u8(self.component_regions[component_id])
            arrays[f"missing_{component_id}"] = _as_u8(self.missing_masks[component_id])
            arrays[f"missing_gray_{component_id}"] = self.missing_gray[component_id].astype(np.uint8)
        np.savez_compressed(directory / f"{self.version}.npz", **arrays)
        metadata = {
            "version": self.version,
            "component_ids": list(self.component_ids),
            "thresholds": self.thresholds,
            "source_manifest": self.source_manifest,
            "unresolved_components": list(self.unresolved_components),
            "shape": list(self.complete_mask.shape),
        }
        (directory / f"{self.version}.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: Path, version: str = "reference_set_v1") -> "ReferenceSet":
        metadata = json.loads((directory / f"{version}.json").read_text(encoding="utf-8"))
        with np.load(directory / f"{version}.npz") as archive:
            component_ids = tuple(metadata["component_ids"])
            result = cls(
                component_ids=component_ids,
                complete_mask=archive["complete_mask"],
                complete_gray=archive["complete_gray"],
                component_regions={
                    component_id: archive[f"region_{component_id}"] for component_id in component_ids
                },
                missing_masks={
                    component_id: archive[f"missing_{component_id}"] for component_id in component_ids
                },
                missing_gray={
                    component_id: archive[f"missing_gray_{component_id}"] for component_id in component_ids
                },
                thresholds={k: float(v) for k, v in metadata.get("thresholds", {}).items()},
                version=metadata.get("version", version),
                source_manifest=metadata.get("source_manifest", {}),
                unresolved_components=tuple(metadata.get("unresolved_components", [])),
            )
        result.validate()
        return result


class ReferenceBuilder:
    """Build references from the eleven controlled capture states."""

    def __init__(self, component_ids: Sequence[str]) -> None:
        self.component_ids = tuple(component_ids)

    @staticmethod
    def _require_frames(state_frames: Mapping[str, Sequence[AlignedPiece]], state: str) -> list[AlignedPiece]:
        frames = [frame for frame in state_frames.get(state, ()) if frame.valid]
        if not frames:
            raise ValueError(f"No hay fotogramas válidos para {state}")
        return frames

    def build(self, state_frames: Mapping[str, Sequence[AlignedPiece]]) -> ReferenceSet:
        complete = self._require_frames(state_frames, "OK")
        complete_support = np.mean(
            np.stack([frame.mask > 0 for frame in complete], axis=0), axis=0
        )
        complete_mask = np.where(complete_support >= 0.90, 255, 0).astype(np.uint8)
        complete_gray = _median_image([frame.gray for frame in complete])
        regions: dict[str, np.ndarray] = {}
        missing_masks: dict[str, np.ndarray] = {}
        missing_gray: dict[str, np.ndarray] = {}
        thresholds: dict[str, float] = {}
        missing_frames: dict[str, list[AlignedPiece]] = {}
        missing_support: dict[str, np.ndarray] = {}

        for component_id in self.component_ids:
            missing = self._require_frames(state_frames, f"{component_id}_MISSING")
            missing_frames[component_id] = missing
            missing_mask = _as_u8(_median_image([frame.mask for frame in missing]))
            missing_masks[component_id] = missing_mask
            missing_gray[component_id] = _median_image([frame.gray for frame in missing])
            missing_support[component_id] = np.mean(
                np.stack([frame.mask > 0 for frame in missing], axis=0), axis=0
            )

        # A component region is an evidence map, not an independent contour assumption.
        # It must be stable in complete captures and absent in the matching missing state.
        for component_id in self.component_ids:
            region_bool = (complete_support >= 0.90) & (missing_support[component_id] <= 0.30)
            # Remove changes that recur when more than two different components are removed.
            repeated_absence = sum(
                missing_support[other_id] <= 0.30 for other_id in self.component_ids
            )
            region_bool &= repeated_absence <= 2
            region = np.where(region_bool, 255, 0).astype(np.uint8)
            region = cv2.morphologyEx(
                region,
                cv2.MORPH_OPEN,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            )
            region = cv2.dilate(
                region,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)),
                iterations=1,
            )
            # Keep the region tied to the complete assembly; unrelated noise is excluded.
            region = cv2.bitwise_and(region, complete_mask)
            if cv2.countNonZero(region) < 25:
                raise ValueError(
                    f"La región {component_id} no se separa de la referencia completa; "
                    "se requiere una captura mejor alineada"
                )
            regions[component_id] = region

        result = ReferenceSet(
            component_ids=self.component_ids,
            complete_mask=complete_mask,
            complete_gray=complete_gray,
            component_regions=regions,
            missing_masks=missing_masks,
            missing_gray=missing_gray,
            thresholds=thresholds,
        )
        unresolved: list[str] = []
        for component_id in self.component_ids:
            complete_scores = [
                ComponentEvaluator._score_only(result, frame, component_id)[0]
                for frame in complete
            ]
            missing_scores = [
                ComponentEvaluator._score_only(result, frame, component_id)[0]
                for frame in missing_frames[component_id]
            ]
            maximum_absent = max(missing_scores)
            minimum_present = min(complete_scores)
            if minimum_present > maximum_absent:
                # Choose the lowest threshold that still rejects every known absent
                # development frame, minimizing false rejects for complete pieces.
                result.thresholds[component_id] = float(
                    np.nextafter(maximum_absent, np.inf)
                )
            else:
                # Safety first: no absent development frame may pass. The unresolved flag
                # prevents the demo from treating geometry alone as a release decision.
                result.thresholds[component_id] = float(maximum_absent + 1e-6)
                unresolved.append(component_id)
        result.unresolved_components = tuple(unresolved)
        result.validate()
        return result


class ComponentEvaluator:
    def __init__(self, reference: ReferenceSet, config: InspectionConfig) -> None:
        reference.validate()
        self.reference = reference
        self.config = config

    @staticmethod
    def _occupancy(mask: np.ndarray, region: np.ndarray) -> float:
        region_bool = region > 0
        count = int(np.count_nonzero(region_bool))
        if count == 0:
            return 0.0
        return float(np.count_nonzero((mask > 0) & region_bool) / count)

    @staticmethod
    def _edge_similarity(edges: np.ndarray, reference_edges: np.ndarray, region: np.ndarray) -> float:
        region_bool = region > 0
        if not np.any(region_bool):
            return 0.0
        candidate = edges[region_bool] > 0
        expected = reference_edges[region_bool] > 0
        union = np.count_nonzero(candidate | expected)
        return float(np.count_nonzero(candidate & expected) / max(1, union))

    @staticmethod
    def _advantage(
        current: np.ndarray, present: np.ndarray, absent: np.ndarray, region: np.ndarray
    ) -> float:
        region_bool = region > 0
        if not np.any(region_bool):
            return 0.0
        current_values = _normalized_gray(current)[region_bool].astype(np.float32)
        present_values = _normalized_gray(present)[region_bool].astype(np.float32)
        absent_values = _normalized_gray(absent)[region_bool].astype(np.float32)
        present_distance = float(np.mean(np.abs(current_values - present_values)) / 255.0)
        absent_distance = float(np.mean(np.abs(current_values - absent_values)) / 255.0)
        return float(np.clip(absent_distance - present_distance + 0.5, 0.0, 1.0))

    @classmethod
    def _score_only(
        cls, reference: ReferenceSet, aligned: AlignedPiece, component_id: str
    ) -> tuple[float, float, float, float]:
        region = reference.component_regions[component_id]
        current_mask = _as_u8(aligned.mask)
        current_edges = aligned.edges
        complete_edges = cv2.Canny(reference.complete_gray, 40, 120)
        occupancy = cls._occupancy(current_mask, region)
        edge_score = cls._edge_similarity(current_edges, complete_edges, region)
        advantage = cls._advantage(
            aligned.gray,
            reference.complete_gray,
            reference.missing_gray[component_id],
            region,
        )
        score = 0.50 * occupancy + 0.30 * edge_score + 0.20 * advantage
        return float(score), float(occupancy), float(edge_score), float(advantage)

    def evaluate(self, aligned: AlignedPiece) -> list[ComponentEvidence]:
        if not aligned.valid:
            return [
                ComponentEvidence(
                    component_id, False, 0.0, 0.0, 0.0, 0.0,
                    self.reference.thresholds.get(component_id, self.config.component_default_threshold),
                    aligned.reason,
                )
                for component_id in self.reference.component_ids
            ]
        evidence: list[ComponentEvidence] = []
        for component_id in self.reference.component_ids:
            region = self.reference.component_regions[component_id]
            score, occupancy, edge_score, advantage = self._score_only(
                self.reference, aligned, component_id
            )
            threshold = self.reference.thresholds.get(
                component_id, self.config.component_default_threshold
            )
            unresolved = component_id in self.reference.unresolved_components
            present = (
                not unresolved
                and score >= threshold
                and occupancy >= self.config.component_min_score
                and advantage >= self.config.component_min_advantage
            )
            reason = "component_unresolved" if unresolved else ("" if present else "component_missing")
            evidence.append(
                ComponentEvidence(
                    component_id, present, float(score), float(occupancy), float(edge_score),
                    float(advantage), float(threshold), reason,
                )
            )
        return evidence
