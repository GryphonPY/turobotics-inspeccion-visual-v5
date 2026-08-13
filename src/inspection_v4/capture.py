from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .board import BoardRectifier
from .component_guide import component_description
from .config import BoardConfig, InspectionConfig
from .piece import PieceAligner, PieceSegmenter
from .quality import assess_frame
from .storage import CaptureSession
from .types import AlignedPiece


CAPTURE_STATES = ("OK",) + tuple(f"C{index:02d}_MISSING" for index in range(1, 11))


@dataclass
class CaptureProgress:
    state: str
    state_index: int
    total_states: int
    seconds_remaining: float
    valid_frames: int
    status: str
    complete: bool = False


@dataclass
class CaptureWizard:
    root: Path
    board: BoardConfig
    config: InspectionConfig
    rectifier: BoardRectifier
    session: CaptureSession
    round_index: int = 1
    state_index: int = 0
    active: bool = False
    recording_started: float | None = None
    raw_frames: list[np.ndarray] = field(default_factory=list)
    manifests: list[dict[str, object]] = field(default_factory=list)
    round_manifests: list[dict[str, object]] = field(default_factory=list)
    last_error: str = ""
    stable_since: float | None = None
    previous_canonical: np.ndarray | None = None
    last_sampled_at: float | None = None

    def __post_init__(self) -> None:
        self.segmenter = PieceSegmenter(self.board, self.config)

    @property
    def state(self) -> str:
        return CAPTURE_STATES[self.state_index]

    @property
    def total_states(self) -> int:
        return len(CAPTURE_STATES)

    def current_instruction(self) -> str:
        if self.state == "OK":
            return "Coloca el ensamble completo con la cabeza amarilla arriba."
        component_id = self.state[:3]
        return f"Retira {component_id}: {component_description(component_id)}. Cabeza arriba."

    def start_state(self, now: float | None = None) -> CaptureProgress:
        self.last_error = ""
        self.active = True
        self.recording_started = now if now is not None else time.monotonic()
        self.raw_frames.clear()
        self.stable_since = None
        self.previous_canonical = None
        self.last_sampled_at = None
        return self.progress(self.recording_started)

    def progress(self, now: float | None = None) -> CaptureProgress:
        current = now if now is not None else time.monotonic()
        elapsed = 0.0 if self.recording_started is None else current - self.recording_started
        remaining = max(0.0, 10.0 - elapsed) if self.active else 0.0
        return CaptureProgress(
            self.state, self.state_index, self.total_states, remaining, len(self.raw_frames),
            "grabando" if self.active else "preparado",
        )

    def add_frame(self, frame: np.ndarray, now: float | None = None) -> CaptureProgress:
        if not self.active:
            return self.progress(now)
        current = now if now is not None else time.monotonic()
        canonical, observation = self.rectifier.warp(frame)
        if canonical is not None and observation.roi is not None:
            quality = assess_frame(
                canonical,
                observation,
                self.board,
                self.config,
                previous_canonical=self.previous_canonical,
            )
            self.previous_canonical = canonical
            if quality.valid:
                piece = self.segmenter.segment(observation.roi)
                if piece.valid:
                    if self.stable_since is None:
                        self.stable_since = current
                    if current - self.stable_since < self.config.stability_seconds:
                        return self.progress(current)
                    if (
                        self.last_sampled_at is None
                        or current - self.last_sampled_at >= self.config.capture_sample_seconds
                    ):
                        # Color is intentionally discarded: V4 is color-independent, and
                        # keeping only the rectified ROI prevents multi-gigabyte sessions.
                        roi_gray = cv2.cvtColor(observation.roi, cv2.COLOR_BGR2GRAY)
                        self.raw_frames.append(roi_gray.copy())
                        self.last_sampled_at = current
                        if len(self.raw_frames) > self.config.capture_max_frames_per_state:
                            self.raw_frames = _select_diverse_frames(
                                self.raw_frames, self.config.capture_max_frames_per_state
                            )
            else:
                self.stable_since = None
        if self.recording_started is not None and current - self.recording_started >= 10.0:
            self.finish_state(current)
        return self.progress(current)

    def finish_state(self, now: float | None = None) -> CaptureProgress:
        if not self.active:
            return self.progress(now)
        if len(self.raw_frames) < 5:
            self.active = False
            self.last_error = (
                f"{self.state}: sólo se obtuvieron {len(self.raw_frames)} fotogramas válidos. "
                "Aplana la hoja, verifica los cuatro ArUco y repite."
            )
            raise RuntimeError(
                f"La captura {self.state} sólo obtuvo {len(self.raw_frames)} fotogramas válidos; "
                "repite la toma con la hoja plana y la cámara estable"
            )
        kept = _select_diverse_frames(
            self.raw_frames, maximum=self.config.capture_max_frames_per_state
        )
        hashes: list[str] = []
        for index, image in enumerate(kept):
            path = self.session.save_frame(
                self.state, index, image, group=f"round_{self.round_index:02d}"
            )
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        state_manifest = {
            "round": self.round_index,
            "state": self.state,
            "frames_saved": len(kept),
            "frame_hashes": hashes,
            "frame_kind": "rectified_roi_gray",
            "frame_shape": list(kept[0].shape),
            "captured_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.manifests.append(state_manifest)
        self.round_manifests.append(state_manifest)
        self.active = False
        if self.state_index == self.total_states - 1:
            manifest = {
                "session_id": self.session.session_id,
                "round": self.round_index,
                "states": self.round_manifests,
                "template": "letter_v1",
            }
            self.session.save_manifest(manifest, suffix=f"round_{self.round_index:02d}")
            self.round_manifests.clear()
            self.state_index = 0
            self.round_index += 1
        else:
            self.state_index += 1
        self.recording_started = None
        self.raw_frames.clear()
        self.stable_since = None
        self.previous_canonical = None
        self.last_sampled_at = None
        return self.progress(now)


def load_capture_frames(root: Path, session_id: str) -> dict[str, list[np.ndarray]]:
    """Load saved rectified ROI frames grouped by state for offline reference building."""
    session_dir = root / "data" / "raw_sessions" / session_id
    if not session_dir.exists():
        raise FileNotFoundError(f"No existe la sesión de captura: {session_id}")
    states: dict[str, list[np.ndarray]] = {}
    state_dirs = sorted(
        path for path in session_dir.rglob("*")
        if path.is_dir() and path.name in CAPTURE_STATES
    )
    for state_dir in state_dirs:
        frames: list[np.ndarray] = []
        for path in sorted(state_dir.glob("frame_*.png")):
            image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if image is not None:
                frames.append(image)
        if frames:
            states.setdefault(state_dir.name, []).extend(frames)
    return states


def load_capture_frames_by_round(
    root: Path, session_id: str
) -> dict[int, dict[str, list[np.ndarray]]]:
    """Load canonical session images preserving round identity for leakage-free evaluation."""
    session_dir = root / "data" / "raw_sessions" / session_id
    if not session_dir.exists():
        raise FileNotFoundError(f"No existe la sesión de captura: {session_id}")
    result: dict[int, dict[str, list[np.ndarray]]] = {}
    for round_dir in sorted(session_dir.glob("round_*")):
        if not round_dir.is_dir():
            continue
        try:
            round_number = int(round_dir.name.split("_")[-1])
        except ValueError:
            continue
        for state_dir in sorted(path for path in round_dir.iterdir() if path.is_dir()):
            frames: list[np.ndarray] = []
            for path in sorted(state_dir.glob("frame_*.png")):
                image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                if image is not None:
                    frames.append(image)
            if frames:
                result.setdefault(round_number, {})[state_dir.name] = frames
    return result


def build_reference_from_session(
    root: Path,
    session_id: str,
    version: str = "reference_set_v1",
    training_rounds: tuple[int, ...] | None = None,
) -> Path:
    """Create a reference set from canonical session images after pose normalization."""
    from .components import ReferenceBuilder

    from .config import load_configs

    board, inspection, _ = load_configs(root)
    by_round = load_capture_frames_by_round(root, session_id)
    if training_rounds is None:
        training_rounds = tuple(sorted(by_round))
    state_images: dict[str, list[np.ndarray]] = {}
    for round_number in training_rounds:
        for state, images in by_round.get(round_number, {}).items():
            state_images.setdefault(state, []).extend(images)
    if "OK" not in state_images:
        raise ValueError("La sesión no tiene estado OK")
    x, y, width, height = board.roi_rect_px
    state_images = {
        state: [_as_roi(image, x, y, width, height) for image in images]
        for state, images in state_images.items()
    }
    segmenter = PieceSegmenter(board, inspection)
    aligner = PieceAligner(inspection.alignment_min_score)
    # Do not average raw captures before alignment: the wizard intentionally changes
    # translation and rotation between rounds. A valid complete frame supplies the
    # provisional pose; every other frame is registered to that pose first.
    provisional_piece = None
    for image in state_images["OK"]:
        candidate = segmenter.segment(image)
        if candidate.valid:
            provisional_piece = candidate
            break
    if provisional_piece is None:
        raise ValueError("No se pudo segmentar ningún estado OK para fijar la pose provisional")
    provisional_mask = provisional_piece.mask
    complete_gray = provisional_piece.gray
    aligned_states: dict[str, list[AlignedPiece]] = {}
    for state, images in state_images.items():
        aligned: list[AlignedPiece] = []
        for image in images:
            piece = segmenter.segment(image)
            if not piece.valid:
                continue
            aligned_piece = aligner.align(piece, provisional_mask, complete_gray)
            if aligned_piece.valid:
                aligned.append(aligned_piece)
        if aligned:
            aligned_states[state] = aligned
    expected_states = {"OK", *(f"C{index:02d}_MISSING" for index in range(1, 11))}
    missing = sorted(expected_states - aligned_states.keys())
    if missing:
        raise ValueError(f"Faltan estados con fotogramas válidos: {', '.join(missing)}")
    reference = ReferenceBuilder(inspection.component_ids).build(aligned_states)
    if reference.unresolved_components:
        unresolved = ", ".join(reference.unresolved_components)
        raise ValueError(
            f"La calibración no separa con seguridad: {unresolved}. "
            "Se requiere repetir la captura o activar el modelo auxiliar."
        )
    reference.version = version
    reference.source_manifest = {
        "session_id": session_id,
        "training_rounds": list(training_rounds),
        "states": sorted(aligned_states),
        "holdout_rounds": [
            round_number for round_number in sorted(by_round)
            if round_number not in training_rounds
        ],
    }
    output = root / "data" / "references"
    reference.save(output)
    return output / f"{version}.json"


def _select_diverse_frames(frames: list[np.ndarray], maximum: int) -> list[np.ndarray]:
    if not frames:
        return []
    exact_unique: list[np.ndarray] = []
    exact_hashes: set[str] = set()
    for image in frames:
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        if digest not in exact_hashes:
            exact_hashes.add(digest)
            exact_unique.append(image)
    if len(exact_unique) <= maximum:
        return exact_unique
    indices = np.linspace(0, len(exact_unique) - 1, maximum, dtype=int)
    selected: list[np.ndarray] = []
    last_signature: np.ndarray | None = None
    for index in indices.tolist():
        image = exact_unique[index]
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        signature = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
        if last_signature is None or float(np.mean(np.abs(signature - last_signature))) >= 1.0:
            selected.append(image)
            last_signature = signature
    return selected or [exact_unique[0]]


def _as_roi(image: np.ndarray, x: int, y: int, width: int, height: int) -> np.ndarray:
    """Accept both legacy full-canonical frames and the bounded ROI-gray format."""
    if image.ndim == 2 and image.shape == (height, width):
        return image.copy()
    if image.ndim == 3 and image.shape[:2] == (height, width):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    roi = image[y : y + height, x : x + width]
    return cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi.copy()
