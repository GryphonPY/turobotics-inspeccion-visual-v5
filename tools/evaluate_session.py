from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from inspection_v4.board import BoardRectifier
from inspection_v4.capture import _as_roi, build_reference_from_session, load_capture_frames_by_round
from inspection_v4.components import ComponentEvaluator, ReferenceSet
from inspection_v4.config import load_configs
from inspection_v4.decision import decide_frame
from inspection_v4.piece import PieceAligner, PieceSegmenter


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa la ronda 7 contra referencias de rondas 1-6")
    parser.add_argument("session_id")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    board, inspection, _ = load_configs(args.root)
    build_reference_from_session(
        args.root, args.session_id, training_rounds=(1, 2, 3, 4, 5, 6)
    )
    reference = ReferenceSet.load(args.root / "data" / "references")
    evaluator = ComponentEvaluator(reference, inspection)
    segmenter = PieceSegmenter(board, inspection)
    aligner = PieceAligner(inspection.alignment_min_score)
    rounds = load_capture_frames_by_round(args.root, args.session_id)
    holdout = rounds.get(7, {})
    report: dict[str, object] = {"session_id": args.session_id, "round": 7, "states": {}}
    all_correct = True
    for state in ("OK",) + tuple(f"C{i:02d}_MISSING" for i in range(1, 11)):
        expected_pass = state == "OK"
        predictions: list[str] = []
        for image in holdout.get(state, []):
            x, y, width, height = board.roi_rect_px
            roi = _as_roi(image, x, y, width, height)
            piece = segmenter.segment(roi)
            if not piece.valid:
                predictions.append("UNRELIABLE")
                continue
            aligned = aligner.align(piece, reference.complete_mask, reference.complete_gray)
            frame = decide_frame(evaluator.evaluate(aligned), aligned.alignment_score, 1.0)
            predictions.append(frame.verdict.value)
        expected_verdict = "PASS" if expected_pass else "NO_PASS"
        correct = sum(prediction == expected_verdict for prediction in predictions)
        state_report = {
            "expected": expected_verdict,
            "frames": len(predictions),
            "correct": correct,
            "accuracy": correct / len(predictions) if predictions else 0.0,
            "predictions": predictions,
        }
        report["states"][state] = state_report
        if not predictions or correct != len(predictions):
            all_correct = False
    report["all_correct"] = all_correct
    output = args.root / "data" / "golden_test" / f"{args.session_id}_holdout_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Reporte: {output}")
    return 0 if all_correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
