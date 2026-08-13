from __future__ import annotations

import argparse
from pathlib import Path

from inspection_v4.capture import build_reference_from_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_id")
    parser.add_argument(
        "--training-rounds",
        nargs="+",
        type=int,
        default=None,
        help="Rondas que se usarán para calibrar; deja fuera la ronda reservada como prueba.",
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    rounds = tuple(args.training_rounds) if args.training_rounds else None
    print(build_reference_from_session(args.root, args.session_id, training_rounds=rounds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
