"""Synthetic fixtures only: verify inode carrier and do not follow hostile fixture links."""

import importlib.util
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_fixture_carrier_is_preserved_inside_archive(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/alliance/bootstrap_fixtures.py"
    spec = importlib.util.spec_from_file_location("bootstrap_fixtures", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    root = tmp_path.resolve()
    (root / "operations").mkdir()
    base = root / "qualification/123/pytest-temp"
    base.mkdir(parents=True)
    (base / "empty").touch()
    (base / "payload").write_bytes(b"synthetic fixture")
    (base.parent / "status.json").write_text('{"status":"SUCCESS"}')
    monkeypatch.setattr(m, "validate_fresh_root", lambda _: root)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=""))
    m.main()
    assert not base.exists()
    with tarfile.open(root / "operations/inode-fixtures-20260920.tar") as tar:
        assert (
            tar.extractfile("qualification/123/pytest-temp/payload").read() == b"synthetic fixture"
        )
        assert len(json.load(tar.extractfile("RECOVERY-MANIFEST.json"))["members"]) == 3
    assert (base.parent / "status.json").is_file()
    with pytest.raises(FileExistsError):
        m.main()
