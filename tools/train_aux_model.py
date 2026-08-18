from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from inspection_v4.aux_model import HOGSVMComponentModel, crop_component
from inspection_v4.capture import (
    _as_roi,
    build_reference_from_session,
    load_capture_frames_by_round,
)
from inspection_v4.components import ComponentEvaluator, ReferenceSet
from inspection_v4.config import load_configs
from inspection_v4.piece import PieceAligner, PieceSegmenter


def _aligned_by_round(root: Path, session_id: str, reference: ReferenceSet) -> dict[int, dict[str, list]]:
    board, inspection, _ = load_configs(root)
    frames = load_capture_frames_by_round(root, session_id, max_frames_per_state=6)
    x, y, width, height = board.roi_rect_px
    segmenter = PieceSegmenter(board, inspection, background_mad_multiplier=4.0)
    # The auxiliary is only reached after the normal pose gate. For its
    # calibration set, retain slightly lower-overlap incomplete assemblies so
    # the holdout contains real missing examples instead of an empty class.
    aligner = PieceAligner(min(inspection.alignment_min_score, 0.70))
    aligned: dict[int, dict[str, list]] = {}
    required_states = {"OK", "C08_MISSING"}
    for round_number, states in sorted(frames.items()):
        for state, images in states.items():
            if state not in required_states:
                continue
            for image in images:
                piece = segmenter.segment(_as_roi(image, x, y, width, height))
                if not piece.valid:
                    continue
                candidate = aligner.align(piece, reference.complete_mask, reference.complete_gray)
                if candidate.valid:
                    aligned.setdefault(round_number, {}).setdefault(state, []).append(candidate)
    return aligned


def _combined_scores(
    reference: ReferenceSet,
    component_id: str,
    model: HOGSVMComponentModel,
    frames: list,
) -> list[float]:
    scores: list[float] = []
    for frame in frames:
        geometric, _, _, _ = ComponentEvaluator._score_only(reference, frame, component_id)
        auxiliary = model.predict_present_score(
            crop_component(frame.gray, reference.component_regions[component_id])
        )
        scores.append(0.60 * geometric + 0.40 * auxiliary)
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Entrena el auxiliar CPU para componentes UNRESOLVED")
    parser.add_argument("session_id")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--component", default="C08")
    args = parser.parse_args()

    root = args.root
    training_rounds = (1, 2, 3, 4, 5, 6)
    holdout_round = 7
    build_reference_from_session(
        root,
        args.session_id,
        training_rounds=training_rounds,
        allow_unresolved=True,
    )
    reference_dir = root / "data" / "references"
    reference = ReferenceSet.load(reference_dir)
    component_id = args.component
    if component_id not in reference.unresolved_components:
        raise ValueError(f"{component_id} no está marcado como UNRESOLVED")

    aligned = _aligned_by_round(root, args.session_id, reference)
    present_train = [
        frame
        for round_number in training_rounds
        for frame in aligned.get(round_number, {}).get("OK", [])
    ]
    absent_train = [
        frame
        for round_number in training_rounds
        for frame in aligned.get(round_number, {}).get(f"{component_id}_MISSING", [])
    ]
    if not present_train or not absent_train:
        raise ValueError(f"No hay suficientes datos alineados para {component_id}")

    model = HOGSVMComponentModel.train(
        component_id,
        [crop_component(frame.gray, reference.component_regions[component_id]) for frame in present_train]
        + [crop_component(frame.gray, reference.component_regions[component_id]) for frame in absent_train],
        [1] * len(present_train) + [0] * len(absent_train),
    )
    train_present = _combined_scores(reference, component_id, model, present_train)
    train_absent = _combined_scores(reference, component_id, model, absent_train)
    threshold = float(np.nextafter(max(train_absent), np.inf))
    model.combined_threshold = threshold

    holdout_present = aligned.get(holdout_round, {}).get("OK", [])
    holdout_absent = aligned.get(holdout_round, {}).get(f"{component_id}_MISSING", [])
    holdout_present_scores = _combined_scores(reference, component_id, model, holdout_present)
    holdout_absent_scores = _combined_scores(reference, component_id, model, holdout_absent)
    report = {
        "component_id": component_id,
        "session_id": args.session_id,
        "training_rounds": list(training_rounds),
        "holdout_round": holdout_round,
        "train_present": len(train_present),
        "train_absent": len(train_absent),
        "holdout_present": len(holdout_present_scores),
        "holdout_absent": len(holdout_absent_scores),
        "threshold": threshold,
        "train_false_passes": sum(score >= threshold for score in train_absent),
        "holdout_false_passes": sum(score >= threshold for score in holdout_absent_scores),
        "holdout_false_rejects": sum(score < threshold for score in holdout_present_scores),
        "holdout_present_min": min(holdout_present_scores) if holdout_present_scores else None,
        "holdout_absent_max": max(holdout_absent_scores) if holdout_absent_scores else None,
    }
    if report["train_false_passes"] or report["holdout_false_passes"]:
        raise RuntimeError(f"El auxiliar {component_id} produce falsos pases: {report}")
    if report["holdout_false_rejects"] > max(1, int(len(holdout_present_scores) * 0.01)):
        raise RuntimeError(f"El auxiliar {component_id} rechaza demasiados completos: {report}")

    model_path = root / "data" / "models" / f"aux_{component_id}_v1.joblib"
    model.save(model_path)
    report_path = root / "data" / "models" / f"aux_{component_id}_v1.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Modelo: {model_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
