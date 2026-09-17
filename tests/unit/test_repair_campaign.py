"""Tiny mocked campaign exercises status, frozen manifests and restart without SSH."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("family", ["propofol_volition_fmri", "bmvp"])
def test_campaign_dry_run_failure_success_and_restart(tmp_path, monkeypatch, family):
    locks = []
    monkeypatch.setitem(
        sys.modules,
        "fcntl",
        SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda f, n: locks.append(f.name)),
    )
    path = Path(__file__).parents[2] / "scripts/alliance/repair_acquisition.py"
    spec = importlib.util.spec_from_file_location("repair_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "validate_fresh_root", lambda p: p)
    monkeypatch.setattr(module, "read_source_record", lambda *a: {"files": {}})
    monkeypatch.setattr(
        module,
        "load_project",
        lambda p: SimpleNamespace(
            datasets=[
                SimpleNamespace(
                    family=family, snapshot_label="v1", values={"expected_archive_urls": 1}
                )
            ]
        ),
    )
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda p: lambda n: None)
    monkeypatch.setattr(module, "scratch_environment", lambda p: {})
    monkeypatch.setattr(module.signal, "signal", lambda *a: None)
    monkeypatch.setattr(module.os, "umask", lambda n: 0)
    calls = []

    def resolve(config):
        calls.append("resolve")
        return [module.FileRecord("propofol_volition_fmri", "v1", "x", "https://example.test/x", 3)]

    monkeypatch.setattr(module, "resolve_openneuro", resolve)
    args = ["repair", "--root", str(tmp_path), "--family", family]
    monkeypatch.setattr(sys, "argv", [*args, "--dry-run"])
    assert module.main() == 0
    assert not (tmp_path / "operations").exists()
    run = tmp_path / "operations/acquisition-repair-v1" / family
    if family == "bmvp":
        original = tmp_path / "manifests/generated/bmvp/v1.jsonl"
        records = [module.FileRecord("bmvp", "v1", "x", "https://example.test/x", 3)]
        module.write_jsonl(original, (r.as_dict() for r in records))
        ledger = tmp_path / "run_state/P02/bmvp.v1.downloads.json"
        module.atomic_write_json(ledger, {"source_manifest_sha256": module._fingerprint(records)})
        (tmp_path / "operations/acquisition").mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", args)

    def fail(*a, **k):
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(module, "download_many", fail)
    with pytest.raises(RuntimeError, match="fixture failure"):
        module.main()
    assert json.loads((run / "status.json").read_text())["status"] == "FAILED"
    frozen = (run / "manifest.jsonl").read_bytes()

    def success(*a, **k):
        if family == "bmvp":
            assert a[2] == ledger
            assert k["source_manifest_sha256"] == module._fingerprint(records)
        return {"success": True, "complete": 1, "bytes": 3}

    monkeypatch.setattr(module, "download_many", success)
    assert module.main() == 0
    assert json.loads((run / "status.json").read_text())["status"] == "SUCCESS"
    assert (run / "manifest.jsonl").read_bytes() == frozen
    assert calls == ([] if family == "bmvp" else ["resolve"])
    if family == "bmvp":
        assert str(tmp_path / "operations/acquisition/campaign.lock") in locks
    assert len(list(run.glob("attempt-*.json"))) == 2
