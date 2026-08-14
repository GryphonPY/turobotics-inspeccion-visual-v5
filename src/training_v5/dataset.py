from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sample:
    path: Path
    session_id: str
    round_id: int
    clip_id: str
    state: str
    labels: tuple[int, ...]
    sha256: str
    dhash: str


@dataclass(frozen=True)
class DatasetSplit:
    train: tuple[Sample, ...]
    validation: tuple[Sample, ...]


def labels_for_state(state: str) -> tuple[int, ...]:
    if state == "OK":
        return (1,) * 10
    if state.startswith("C") and state.endswith("_MISSING"):
        missing = int(state[1:3])
        return tuple(0 if index == missing else 1 for index in range(1, 11))
    raise ValueError(f"Unsupported V5 state: {state}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dhash(path: Path) -> str:
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    small = cv2.resize(image, (9, 8), interpolation=cv2.INTER_AREA)
    bits = small[:, 1:] > small[:, :-1]
    return "".join("1" if bit else "0" for bit in bits.reshape(-1))


def index_session(root: Path, session_id: str) -> tuple[Sample, ...]:
    session = root / "data" / "raw_sessions" / session_id
    if not session.is_dir():
        raise FileNotFoundError(session)
    samples: list[Sample] = []
    for round_dir in sorted(session.glob("round_*")):
        if not round_dir.is_dir():
            continue
        round_id = int(round_dir.name.split("_")[-1])
        for state_dir in sorted(path for path in round_dir.iterdir() if path.is_dir()):
            state = state_dir.name
            labels = labels_for_state(state)
            clip_id = f"{session_id}:round_{round_id:02d}:{state}"
            for path in sorted(state_dir.glob("frame_*.png")):
                samples.append(
                    Sample(
                        path=path,
                        session_id=session_id,
                        round_id=round_id,
                        clip_id=clip_id,
                        state=state,
                        labels=labels,
                        sha256=_sha256(path),
                        dhash=_dhash(path),
                    )
                )
    if not samples:
        raise ValueError(f"No PNG frames found in {session}")
    return tuple(samples)


def group_split(
    samples: Iterable[Sample],
    train_rounds: set[int],
    validation_rounds: set[int],
    *,
    allow_unassigned: bool = False,
) -> DatasetSplit:
    if train_rounds & validation_rounds:
        raise ValueError("Training and validation rounds overlap")
    train: list[Sample] = []
    validation: list[Sample] = []
    for sample in samples:
        if sample.round_id in train_rounds:
            train.append(sample)
        elif sample.round_id in validation_rounds:
            validation.append(sample)
        elif not allow_unassigned:
            raise ValueError(f"Sample round {sample.round_id} is not assigned: {sample.path}")
    train_groups = {sample.clip_id for sample in train}
    validation_groups = {sample.clip_id for sample in validation}
    if train_groups & validation_groups:
        raise ValueError("Clip leakage between training and validation")
    return DatasetSplit(tuple(train), tuple(validation))


def sample_to_json(sample: Sample, root: Path) -> dict[str, object]:
    return {
        "path": sample.path.relative_to(root).as_posix(),
        "session_id": sample.session_id,
        "round_id": sample.round_id,
        "clip_id": sample.clip_id,
        "state": sample.state,
        "labels": list(sample.labels),
        "sha256": sample.sha256,
        "dhash": sample.dhash,
    }


def write_index(samples: Iterable[Sample], root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(sample_to_json(sample, root), ensure_ascii=False) for sample in samples]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
