from __future__ import annotations

from pathlib import Path

from tools.run_v5_campaign import load_fixture_manifest, sha256_file


def test_all_regression_fixtures_exist_and_match_hash() -> None:
    root = Path(__file__).resolve().parents[1]
    fixtures = load_fixture_manifest(root, root / "tests" / "fixtures" / "manifest.json")

    assert len(fixtures) >= 8
    for fixture in fixtures:
        assert fixture.path.exists()
        assert sha256_file(fixture.path) == fixture.sha256
