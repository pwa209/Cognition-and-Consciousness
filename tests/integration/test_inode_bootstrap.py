"""Bootstrap consolidation only touches explicit scratch fixtures and zero-byte work files."""

import importlib.util
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "scripts/alliance/bootstrap_inodes.py"
    spec = importlib.util.spec_from_file_location("bootstrap_inodes", source)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    monkeypatch.setattr(
        value.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="", returncode=0)
    )
    return value


def setup(tmp_path, monkeypatch):
    m = module(monkeypatch)
    root = tmp_path.resolve()
    monkeypatch.setattr(m, "validate_fresh_root", lambda _: root)
    (root / "operations").mkdir()
    (root / "qualification/123/pytest-temp").mkdir(parents=True)
    (root / "qualification/123/status.json").write_text('{"status":"SUCCESS"}')
    (root / "qualification/123/pytest-temp/synthetic.txt").write_bytes(b"only fixture")
    (root / "cache/pip/a").mkdir(parents=True)
    (root / "cache/pip/a/wheel").write_bytes(b"regenerable")
    for attempt in ["21417200-1", "21417200-2"]:
        work = root / "analysis/masked-neural/PREPROCESS" / attempt / "work"
        work.mkdir(parents=True)
        (work / "zero").write_bytes(b"")
        (work / "nonempty").write_bytes(b"preserve")
    return m, root


def test_verified_bootstrap_preserves_nonempty_work_and_success_marker(tmp_path, monkeypatch):
    m, root = setup(tmp_path, monkeypatch)
    m.main()
    archive = root / "operations/inode-bootstrap-20260920.tar"
    with tarfile.open(archive) as tar:
        assert tar.extractfile("cache/pip/a/wheel").read() == b"regenerable"
        manifest = json.load(tar.extractfile("RECOVERY-MANIFEST.json"))
        assert len(manifest["empty_work_files"]) == 2
    assert not (root / "cache/pip").exists()
    assert (
        root / "analysis/masked-neural/PREPROCESS/21417200-1/work/nonempty"
    ).read_bytes() == b"preserve"
    assert (root / "qualification/123/status.json").exists()
    with pytest.raises(FileExistsError):
        m.main()


def test_active_array_stops_before_removal(tmp_path, monkeypatch):
    m, root = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        m.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="21417200_1|RUNNING")
    )
    with pytest.raises(ValueError, match="not quiescent"):
        m.main()
    assert (root / "cache/pip/a/wheel").exists()


def test_existing_cache_inode_bootstrap_when_new_inode_is_denied(tmp_path, monkeypatch):
    m, root = setup(tmp_path, monkeypatch)
    original_open = Path.open

    def quota(path, mode="r", *args, **kwargs):
        if path.name == "inode-bootstrap-20260920.tar" and mode == "xb":
            raise OSError(122, "synthetic inode quota")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", quota)
    m.main()
    with tarfile.open(root / "operations/inode-bootstrap-20260920.tar") as tar:
        assert tar.extractfile("cache/pip/a/wheel").read() == b"regenerable"
    assert not (root / "cache/pip").exists()


def test_bootstrap_excludes_linked_fixture_tree(tmp_path, monkeypatch):
    m, root = setup(tmp_path, monkeypatch)
    link = root / "qualification/123/pytest-temp/link"
    try:
        link.symlink_to(root / "absent", target_is_directory=True)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    m.main()
    assert link.is_symlink()
    assert (link.parent / "synthetic.txt").exists()
