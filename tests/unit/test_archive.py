from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from factorcon.errors import IntegrityError
from factorcon.io.archive import extract_archive_safe


def test_safe_zip_extraction(tmp_path: Path) -> None:
    archive = tmp_path / "safe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("sub-01/events.tsv", "onset\tduration\n0\t1\n")
    summary = extract_archive_safe(archive, tmp_path / "out")
    assert summary.files == 1
    assert (tmp_path / "out" / "sub-01" / "events.tsv").is_file()


def test_zip_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", "no")
    with pytest.raises(IntegrityError):
        extract_archive_safe(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()

