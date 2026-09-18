"""Digest RPC fixtures contain synthetic bytes only; no cluster or network calls."""

from __future__ import annotations

import json
from hashlib import sha256

import pytest

from factorcon.errors import IntegrityError, SourceError
from factorcon.hash_queue import queued_hash


def test_hash_queue_binding_success_failure_and_confinement(tmp_path, monkeypatch):
    import factorcon.hash_queue as module

    queue = tmp_path / "operations/hash-service"
    path = tmp_path / "data/raw/fixture"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abc")

    def reply(seconds):
        request_path = next((queue / "requests").glob("*.json"))
        request = json.loads(request_path.read_text())
        module.atomic_write_json(
            queue / "results" / request_path.name,
            {"request": request, "status": "SUCCESS", "digest": sha256(b"abc").hexdigest()},
        )

    monkeypatch.setattr(module.time, "sleep", reply)
    assert queued_hash(path, "sha256", queue) == sha256(b"abc").hexdigest()
    with pytest.raises(IntegrityError):
        queued_hash(tmp_path / "outside", "sha256", queue)
    with pytest.raises(IntegrityError):
        queued_hash(path, "sha1", queue)
    with pytest.raises(SourceError, match="timed out"):
        queued_hash(path, "sha256", queue, timeout=0)


def test_scheduled_worker_hashes_and_rejects_changed_request(tmp_path, monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    from factorcon.util import atomic_write_json

    monkeypatch.setitem(
        sys.modules, "fcntl", SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *a: None)
    )
    spec = importlib.util.spec_from_file_location(
        "hash_service_fixture", Path(__file__).parents[2] / "scripts/alliance/hash_service.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "validate_fresh_root", lambda p: p)
    monkeypatch.setattr(module, "read_source_record", lambda *a: {})
    monkeypatch.setattr(module.signal, "signal", lambda *a: None)
    monkeypatch.setattr(module.os, "umask", lambda n: 0)
    monkeypatch.setattr(
        module.os, "uname", lambda: SimpleNamespace(nodename="fixture"), raising=False
    )
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    monkeypatch.setattr(sys, "argv", ["service", "--root", str(tmp_path), "--once"])
    path = tmp_path / "data/raw/x"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abc")
    queue = tmp_path / "operations/hash-service"
    request = {
        "path": str(path),
        "algorithm": "sha256",
        "size": 3,
        "mtime_ns": path.stat().st_mtime_ns,
    }
    atomic_write_json(queue / "requests/good.json", request)
    atomic_write_json(queue / "requests/bad.json", {**request, "size": 4})
    assert module.main() == 0
    good = json.loads((queue / "results/good.json").read_text())
    assert good["digest"] == sha256(b"abc").hexdigest() and good["status"] == "SUCCESS"
    assert json.loads((queue / "results/bad.json").read_text())["status"] == "FAILED"
