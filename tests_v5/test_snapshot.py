from __future__ import annotations

from pathlib import Path

from tools.v5_snapshot import build_manifest, verify_manifest


def test_verify_manifest_reports_changed_file(tmp_path: Path) -> None:
    protected = tmp_path / "src" / "inspection_v4"
    protected.mkdir(parents=True)
    target = protected / "engine.py"
    target.write_text("before", encoding="utf-8")
    manifest = build_manifest(tmp_path)

    target.write_text("after", encoding="utf-8")

    assert verify_manifest(tmp_path, manifest) == ["src/inspection_v4/engine.py"]


def test_manifest_ignores_gitkeep_and_cache_files(tmp_path: Path) -> None:
    protected = tmp_path / "data" / "models"
    protected.mkdir(parents=True)
    (protected / ".gitkeep").write_text("", encoding="utf-8")
    cache = tmp_path / "src" / "inspection_v4" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "ignored.pyc").write_bytes(b"ignored")

    assert build_manifest(tmp_path) == {}
