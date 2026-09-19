"""Full dry-run/failure/success/restart contract using tiny synthetic inputs."""

import importlib.util
import json
from pathlib import Path

import pytest

from factorcon.util import atomic_write_json


def runner():
    path = Path(__file__).resolve().parents[2] / "scripts/alliance/empirical_phase.py"
    spec = importlib.util.spec_from_file_location("empirical_phase", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dry_run_failure_success_retry(tmp_path, monkeypatch):
    from types import SimpleNamespace

    module = runner()
    source = Path(__file__).resolve().parents[2]
    inputs = SimpleNamespace(
        records=[1],
        manifest_sha256="abc",
        acquisition_identity="abc",
        ledger=source / "conf/base.yaml",
        holds=[],
    )
    monkeypatch.setattr(module, "resolve_acquired_input", lambda *_: inputs)
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda _: lambda _: None)
    monkeypatch.setattr(module, "inventory_sources", lambda *_a, **_k: {})
    result = module.run_phase(
        source, tmp_path, "P03", "masked_content_fmri", tmp_path / "dry", dry_run=True
    )
    assert result["dry_run"] and not (tmp_path / "dry").exists()

    def fail(*_a, **_k):
        raise ValueError("corrupt fixture")

    monkeypatch.setattr(module, "verify_downloads", fail)
    with pytest.raises(ValueError, match="corrupt"):
        module.run_phase(source, tmp_path, "P03", "masked_content_fmri", tmp_path / "failed")
    assert json.loads((tmp_path / "failed/status.json").read_text())["status"] == "FAILED"
    monkeypatch.setattr(module, "verify_downloads", lambda *_a, **_k: {"files": 1, "bytes": 20})
    module.run_phase(source, tmp_path, "P03", "masked_content_fmri", tmp_path / "retry")
    assert json.loads((tmp_path / "retry/status.json").read_text())["status"] == "SUCCESS"
    assert json.loads((tmp_path / "retry/provenance.json").read_text())["outputs"]["report.json"]
    with pytest.raises(FileExistsError):
        module.run_phase(source, tmp_path, "P03", "masked_content_fmri", tmp_path / "retry")
    assert json.loads((tmp_path / "failed/status.json").read_text())["status"] == "FAILED"


def test_predecessor_and_unsupported_phase(tmp_path):
    module = runner()
    source = Path(__file__).resolve().parents[2]
    predecessor = tmp_path / "analysis/P03/masked_content_fmri/1/status.json"
    good = {
        "status": "SUCCESS",
        "phase": "P03",
        "family": "masked_content_fmri",
        "source_release": str(source),
        "manifest_sha256": "abc",
    }
    atomic_write_json(predecessor, good)
    module.check_predecessor(tmp_path, source, "masked_content_fmri", "abc", predecessor)
    with pytest.raises(ValueError):
        module.check_predecessor(tmp_path, source, "masked_content_fmri", "different", predecessor)
    with pytest.raises(ValueError):
        module.run_phase(
            source, tmp_path, "P07", "masked_content_fmri", tmp_path / "invalid", dry_run=True
        )
    with pytest.raises(ValueError, match="not validated"):
        module.run_phase(source, tmp_path, "P04", "dream", tmp_path / "invalid", dry_run=True)


def test_p04_harmonization_lifecycle(tmp_path, monkeypatch):
    from types import SimpleNamespace

    module = runner()
    source = Path(__file__).resolve().parents[2]
    inputs = SimpleNamespace(
        records=[1],
        manifest_sha256="abc",
        acquisition_identity="abc",
        ledger=source / "conf/base.yaml",
        holds=[],
    )
    monkeypatch.setattr(module, "resolve_acquired_input", lambda *_: inputs)
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda _: lambda _: None)
    predecessor = tmp_path / "analysis/P03/masked_content_fmri/1/status.json"
    atomic_write_json(
        predecessor,
        {
            "status": "SUCCESS",
            "phase": "P03",
            "family": "masked_content_fmri",
            "source_release": str(source),
            "manifest_sha256": "abc",
        },
    )

    def harmonize(*_args):
        return {"status": "harmonized", "records": 2, "participants": 1}

    monkeypatch.setattr(module, "harmonize_family", harmonize)
    assert (
        module.run_phase(
            source, tmp_path, "P04", "masked_content_fmri", tmp_path / "p04", predecessor
        )["records"]
        == 2
    )
    assert json.loads((tmp_path / "p04/status.json").read_text())["status"] == "SUCCESS"
