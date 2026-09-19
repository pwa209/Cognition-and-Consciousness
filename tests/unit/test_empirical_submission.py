"""Scheduler submission receipts using mocks, never real queue writes."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / "scripts/alliance/submit_empirical.py"
    spec = importlib.util.spec_from_file_location("submit_empirical", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_submission_is_idempotent_and_command_bound(tmp_path, monkeypatch):
    m = module()
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="12345;rorqual\n")

    monkeypatch.setattr(m.subprocess, "run", run)
    path = tmp_path / "receipt.json"
    assert m.submit_one(path, ["sbatch", "test"]) == "12345"
    assert m.submit_one(path, ["sbatch", "test"]) == "12345"
    assert len(calls) == 1
    with pytest.raises(ValueError, match="reconciliation"):
        m.submit_one(path, ["sbatch", "changed"])


def test_uncertain_submit_never_retried(tmp_path, monkeypatch):
    m = module()

    def run(*_a, **_k):
        raise TimeoutError("connection lost after scheduler might accept")

    monkeypatch.setattr(m.subprocess, "run", run)
    path = tmp_path / "receipt.json"
    with pytest.raises(TimeoutError):
        m.submit_one(path, ["sbatch", "test"])
    assert json.loads(path.read_text())["status"] == "UNCERTAIN"
    with pytest.raises(ValueError, match="reconciliation"):
        m.submit_one(path, ["sbatch", "test"])
