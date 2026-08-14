from __future__ import annotations

import argparse
import json
from pathlib import Path

from training_v5.dataset import group_split, index_session, write_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build leakage-safe V5 dataset index")
    parser.add_argument("--session", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    samples = index_session(root, args.session)
    split = group_split(
        samples,
        train_rounds={1, 2, 3, 4, 5},
        validation_rounds={6},
        allow_unassigned=True,
    )
    output = root / "data" / "v5" / "dataset" / "index.jsonl"
    manifest = root / "data" / "v5" / "dataset" / "split_manifest.json"
    if not args.verify_only:
        write_index(samples, root, output)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "session_id": args.session,
                    "sample_count": len(samples),
                    "train_rounds": [1, 2, 3, 4, 5],
                    "validation_rounds": [6],
                    "holdout_rounds": [7],
                    "train_count": len(split.train),
                    "validation_count": len(split.validation),
                    "train_clips": sorted({sample.clip_id for sample in split.train}),
                    "validation_clips": sorted({sample.clip_id for sample in split.validation}),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    print(
        f"session={args.session} samples={len(samples)} train={len(split.train)} "
        f"validation={len(split.validation)} holdout=round_7"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
