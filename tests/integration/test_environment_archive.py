"""Synthetic retired-environment fixtures exercise packing without touching live runtimes."""

import importlib.util
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from factorcon.work_archive import environment_target, pack, retire


def test_environment_lifecycle_and_protected_roots(tmp_path):
    root = tmp_path.resolve()
    env = root / "environments/qualification-123"
    (env / "lib").mkdir(parents=True)
    (env / "lib/module.py").write_bytes(b"synthetic module")
    dest = root / "archives/environments/qualification-123"
    assert pack(root, env, dest, category="environments", dry_run=True)["members"] == 3
    assert not dest.exists()
    pack(root, env, dest, category="environments")
    with pytest.raises(ValueError):
        retire(root, env, dest)
    assert retire(root, env, dest, category="environments")["status"] == "RETIRED"
    assert retire(root, env, dest, category="environments")["source_removed"]
    with tarfile.open(dest / "work.tar") as tar:
        assert tar.extractfile("qualification-123/lib/module.py").read() == b"synthetic module"
    for name in [
        "qualification-21169236",
        "qualification-21417196",
        "report-pymc-5.24.0-arviz-0.22.0-v1",
    ]:
        with pytest.raises(ValueError):
            environment_target(root, root / "environments" / name)
    with pytest.raises(ValueError):
        environment_target(root, root / "data/qualification-123")


def test_environment_symlink_preserved_without_following(tmp_path):
    root = tmp_path.resolve()
    env = root / "environments/qualification-123"
    env.mkdir(parents=True)
    (env / "library").mkdir()
    link = env / "lib64"
    try:
        link.symlink_to("library", target_is_directory=True)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    dest = root / "archives/environments/qualification-123"
    pack(root, env, dest, category="environments")
    retire(root, env, dest, category="environments")
    with tarfile.open(dest / "work.tar") as tar:
        assert tar.getmember("qualification-123/lib64").issym()


def test_unknown_consumer_and_target_reference_stop_cleanup(tmp_path, monkeypatch):
    folder = Path(__file__).resolve().parents[2] / "scripts/alliance"
    monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location(
        "archive_environments", folder / "archive_environments.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    plan = {
        "targets": ["qualification-123"],
        "protected": ["qualification-456"],
        "active_campaign_source": "a" * 40,
    }
    p = tmp_path / "operations/inode-recovery" / plan["active_campaign_source"] / "campaign.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"jobs": {"archive": "111"}}))
    monkeypatch.setenv("SLURM_JOB_ID", "222")
    monkeypatch.setattr(
        m.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=f"999|{tmp_path}|unknown.sh")
    )
    with pytest.raises(ValueError, match="unknown live"):
        m.check_consumers(tmp_path, plan)
    monkeypatch.setattr(
        m.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout=f"111|{tmp_path}|qualification-123/bin/python"),
    )
    with pytest.raises(ValueError, match="references"):
        m.check_consumers(tmp_path, plan)
