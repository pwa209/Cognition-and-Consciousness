"""The inode census must not follow external links or mutate inputs."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_study_census_counts_prefixes(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/alliance"))
    from study_inode_census import census

    (tmp_path / "fresh" / "raw").mkdir(parents=True)
    (tmp_path / "fresh" / "raw" / "one.txt").write_text("one")
    (tmp_path / "fresh" / "raw" / "two.txt").write_text("two")
    result = census(tmp_path)
    assert result["entries_including_root"] == 5
    assert result["by_prefix"]["fresh"] == 4
    assert result["by_prefix"]["fresh/raw"] == 3
    assert result["by_prefix"]["fresh/raw/one.txt"] == 1


def test_study_census_does_not_follow_symlinks(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/alliance"))
    from study_inode_census import census

    external = tmp_path.parent / "external-census-test"
    try:
        (tmp_path / "outside").symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("local symlink creation unavailable")
    result = census(tmp_path)
    assert result["entries_including_root"] == 2
    assert result["by_prefix"]["outside"] == 1
    assert "external-census-test" not in str(result)
