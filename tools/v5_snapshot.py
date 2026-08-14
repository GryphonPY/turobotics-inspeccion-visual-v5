from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

MANIFEST_RELATIVE = Path("data/v5/manifests/v4_protected_files.json")
PROTECTED_FILES = (
    Path("config/board_letter_v1.json"),
    Path("config/inspection_v1.json"),
)
PROTECTED_DIRECTORIES = (
    Path("src/inspection_v4"),
    Path("data/references"),
    Path("data/models"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _protected_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for relative in PROTECTED_FILES:
        candidate = root / relative
        if candidate.is_file():
            paths.add(candidate)
    for relative_directory in PROTECTED_DIRECTORIES:
        directory = root / relative_directory
        if not directory.is_dir():
            continue
        for candidate in directory.rglob("*"):
            if candidate.is_file() and candidate.name != ".gitkeep" and "__pycache__" not in candidate.parts:
                paths.add(candidate)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def build_manifest(root: Path) -> dict[str, str]:
    root = root.resolve()
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in _protected_paths(root)
    }


def verify_manifest(root: Path, manifest: Mapping[str, str]) -> list[str]:
    root = root.resolve()
    current = build_manifest(root)
    mismatches: set[str] = set()
    for relative, expected_hash in manifest.items():
        candidate = root / Path(relative)
        if not candidate.is_file() or current.get(relative) != expected_hash:
            mismatches.add(relative)
    for relative in current.keys() - manifest.keys():
        mismatches.add(relative)
    return sorted(mismatches)


def _manifest_path(root: Path) -> Path:
    return root / MANIFEST_RELATIVE


def create_manifest(root: Path) -> Path:
    path = _manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "v5-v4-protection-v1",
        "root": ".",
        "files": build_manifest(root),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def verify_saved_manifest(root: Path) -> list[str]:
    path = _manifest_path(root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "v5-v4-protection-v1":
        raise ValueError(f"Unsupported manifest schema: {payload.get('schema')!r}")
    return verify_manifest(root, payload.get("files", {}))


def main() -> int:
    parser = argparse.ArgumentParser(description="Protect and verify V4 files before V5 work")
    parser.add_argument("command", choices=("create", "verify"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "create":
        path = create_manifest(root)
        print(f"Created V4 protection manifest: {path}")
        print(f"Protected files: {len(build_manifest(root))}")
        return 0
    mismatches = verify_saved_manifest(root)
    if mismatches:
        print("Protected files changed:")
        print("\n".join(mismatches))
        return 1
    print("Protected files unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
