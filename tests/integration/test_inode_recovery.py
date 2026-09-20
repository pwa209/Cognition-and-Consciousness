"""Storage recovery lifecycle fixtures contain no participant data."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(name):
    folder = Path(__file__).resolve().parents[2] / "scripts/alliance"
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("text", ["", "RUNNING|\n", "CANCELLED|\nCOMPLETING|\n"])
def test_quiescence_fails_closed(monkeypatch, text):
    m = module("inode_recovery")
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=text))
    with pytest.raises(ValueError, match="quiescent"):
        m.terminal("123")


def test_terminal_accounting(monkeypatch):
    m = module("inode_recovery")
    monkeypatch.setattr(
        m.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout="CANCELLED by 123|\nCOMPLETED|\n"),
    )
    assert m.terminal("123") == ["CANCELLED", "COMPLETED"]


def test_monitor_stops_process_group_on_quota_failure(monkeypatch):
    m = module("inode_recovery")
    calls = []
    process = SimpleNamespace(pid=123, poll=lambda: None)

    def wait(timeout):
        if not calls:
            raise subprocess.TimeoutExpired("fixture", timeout)
        return 0

    process.wait = wait
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(m.os, "killpg", lambda *a: calls.append(a), raising=False)

    def fail(_):
        raise ValueError("quota boundary")

    with pytest.raises(ValueError, match="quota boundary"):
        m.monitored_run(["fmriprep"], guard=fail, interval=0, check=True)
    assert calls == [(123, m.signal.SIGTERM)]


def test_failed_replicates_keep_seed_and_source(tmp_path):
    m = module("submit_inode_recovery")
    from factorcon.util import hash_file

    plan = {
        "pattern_source": "a" * 40,
        "pattern_failed_array": "123",
        "expected_failed_replicates": 1,
    }
    source = tmp_path / "releases" / plan["pattern_source"] / "source/conf"
    source.mkdir(parents=True)
    for filename in ["pattern_stress.yaml", "analysis_spec.yaml"]:
        (source / filename).write_text("{}")
    state = {
        "status": "FAILED",
        "error": "CapacityError: unrecognized diskusage_report personal quota format",
        "original_replicate": 155,
        "seed": 260985,
        "source_plan_sha256": hash_file(source / "pattern_stress.yaml"),
        "analysis_spec_sha256": hash_file(source / "analysis_spec.yaml"),
    }
    p = tmp_path / "analysis/P05/patterns/replicate-155/123/status.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(state))
    assert m.failed_replicates(tmp_path, plan) == [155]
    state["seed"] += 1
    p.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="identity"):
        m.failed_replicates(tmp_path, plan)


def test_archive_insufficient_byte_headroom_preserves_source(tmp_path, monkeypatch):
    m = module("inode_recovery")
    fake = SimpleNamespace(
        read_personal_quota=lambda: SimpleNamespace(
            limit_bytes=1, used_bytes=0, limit_files=1000, used_files=0
        ),
        pack=lambda *a, **k: {"source_bytes": 100, "members": 3},
    )
    monkeypatch.setattr(m, "load_module", lambda *a: fake)
    with pytest.raises(ValueError, match="byte headroom"):
        m.archive_work(tmp_path, tmp_path, tmp_path / "work", tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_submission_serializes_mri_after_archive_and_tests(tmp_path, monkeypatch):
    m = module("submit_inode_recovery")
    original = Path(__file__).resolve().parents[2]
    plan = json.loads((original / "conf/inode_recovery_plan.yaml").read_text())
    repair = tmp_path / "releases" / ("b" * 40) / "source"
    (repair / "conf").mkdir(parents=True)
    (repair / "conf/inode_recovery_plan.yaml").write_text(json.dumps(plan))
    for env in [
        plan[k] for k in ["qualification_environment", "mri_environment", "pattern_environment"]
    ]:
        p = tmp_path / "environments" / env / "bin/python"
        p.parent.mkdir(parents=True)
        p.touch()
    monkeypatch.setattr(m, "__file__", str(repair / "scripts/alliance/submit_inode_recovery.py"))
    monkeypatch.setattr(m, "validate_fresh_root", lambda _: tmp_path)
    monkeypatch.setattr(m, "verify_source", lambda *a: None)
    monkeypatch.setattr(m, "terminal", lambda *a: [])
    monkeypatch.setattr(m, "failed_replicates", lambda *a: list(range(155, 200)))
    monkeypatch.setitem(
        sys.modules, "fcntl", SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *a: None)
    )
    commands = []

    def submit(receipt, command):
        commands.append(command)
        return str(100 + len(commands))

    monkeypatch.setattr(m, "submit_one", submit)
    assert m.main() == 0
    assert len(commands) == 9
    assert "--dependency=afterok:101" in commands[1]
    assert "--dependency=afterok:102" in commands[2]
    assert "--dependency=afterok:102" in commands[3]
    for index in range(4, 9):
        assert f"--dependency=afterok:{100 + index}" in commands[index]
    assert any(s.endswith("199%1") for s in commands[2] if s.startswith("--array="))
