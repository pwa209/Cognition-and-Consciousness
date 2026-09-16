"""Synthetic wrapper checks; no SSH, scheduler, participant data or real quota reads."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from factorcon.util import atomic_write_json, hash_file


def _load(name):
    path = Path(__file__).resolve().parents[2] / "scripts/alliance" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stress_wrapper_dry_run_failure_success_and_retry(tmp_path, monkeypatch):
    module = _load("stress_shard")
    root = tmp_path / "fresh-fixture"
    source = root / "releases" / ("a" * 40) / "source"
    (source / "conf").mkdir(parents=True)
    plan = {
        "suite": "reports",
        "replicates": 200,
        "groups": 4,
        "conditions": 4,
        "features": 2,
        "draws": 8,
        "warmup": 8,
        "chains": 2,
        "scenarios": ["complete"],
    }
    atomic_write_json(source / "conf/report_stress.yaml", plan)
    atomic_write_json(source / "conf/analysis_spec.yaml", {})
    atomic_write_json(
        root / "FRESH_RUN.json",
        {
            "release": str(source),
            "download_root": str(root),
            "reuse_prior_data": False,
            "analysis_execution_authorized": True,
            "files": {
                p.relative_to(source).as_posix(): hash_file(p) for p in source.rglob("*.yaml")
            },
        },
    )
    monkeypatch.setattr(module, "__file__", str(source / "scripts/alliance/stress_shard.py"))
    monkeypatch.setattr(module, "validate_fresh_root", lambda path: path)
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda _path: lambda n: None)
    monkeypatch.setattr(module.signal, "signal", lambda *_args: None)
    argv = ["stress_shard.py", "--root", str(root), "--suite", "reports", "--replicate", "2"]
    monkeypatch.setattr(sys, "argv", [*argv, "--dry-run"])
    assert module.main() == 0
    assert not (root / "analysis").exists()
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setenv("SLURM_ARRAY_JOB_ID", "100")
    monkeypatch.setenv("SLURM_ARRAY_TASK_ID", "2")

    def fail(*_args, **_kwargs):
        raise ValueError("fixture technical failure")

    monkeypatch.setattr(module, "run_stress_plan", fail)
    with pytest.raises(ValueError, match="fixture technical"):
        module.main()
    base = root / "analysis/P05/reports/replicate-002"
    assert json.loads((base / "100/status.json").read_text())["status"] == "FAILED"
    monkeypatch.setenv("SLURM_ARRAY_JOB_ID", "101")

    def succeed(plan_path, output, **kwargs):
        assert kwargs["seed"] == 260832
        assert json.loads(plan_path.read_text())["replicates"] == 1
        atomic_write_json(output, {"rows": [{"status": "completed", "covered": False}]})

    monkeypatch.setattr(module, "run_stress_plan", succeed)
    assert module.main() == 0
    assert json.loads((base / "101/status.json").read_text())["status"] == "SUCCESS"
    assert json.loads((base / "101/provenance.json").read_text())["original_replicate"] == 2
    # An unfavorable scientific result is retained; never overwritten by a rerun.
    with pytest.raises(FileExistsError):
        module.main()
    assert json.loads((base / "101/result.json").read_text())["rows"][0]["covered"] is False


def test_transfer_rejects_shared_root_before_git(monkeypatch):
    module = _load("prepare_release")
    from factorcon.errors import IntegrityError

    def unexpected(*_args, **_kwargs):
        pytest.fail("git should not be reached")

    monkeypatch.setattr(module.subprocess, "check_output", unexpected)
    with pytest.raises(IntegrityError):
        module.build_transfer("HEAD", "/project/def-ptewarie/pwa209/study", Path.cwd())


def test_wm_phase_crc_failure_and_versioned_retry(tmp_path, monkeypatch):
    module = _load("wm_phase")
    source = tmp_path / "source"
    for name in (
        "analysis_spec.yaml",
        "base.yaml",
        "datasets/multisite_working_memory.yaml",
        "construct_maps/multisite_working_memory.yaml",
    ):
        atomic_write_json(source / "conf" / name, {})
    project = SimpleNamespace(root=source)
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda _path: lambda n: None)
    monkeypatch.setattr(module.signal, "signal", lambda *_args: None)

    def validator(_project, _root, _family, output, **_kwargs):
        result = {"status": "valid", "archives": {"fixture.zip": {"test_result": "bad_crc"}}}
        atomic_write_json(output, result)
        return result

    monkeypatch.setattr(module, "validate_family", validator)
    attempt = tmp_path / "failed"
    with pytest.raises(ValueError, match="technical validation"):
        module.run_phase(project, tmp_path, "P03", attempt)
    assert json.loads((attempt / "status.json").read_text())["status"] == "FAILED"
    assert (attempt / "report.json").exists()

    def valid(_project, _root, _family, output, **_kwargs):
        result = {"status": "valid", "archives": {}, "files": 1, "bytes": 10}
        atomic_write_json(output, result)
        return result

    monkeypatch.setattr(module, "validate_family", valid)
    retry = tmp_path / "retry"
    assert module.run_phase(project, tmp_path, "P03", retry)["files"] == 1
    assert json.loads((retry / "status.json").read_text())["status"] == "SUCCESS"
    assert json.loads((retry / "provenance.json").read_text())["outputs"]["report.json"]
    with pytest.raises(FileExistsError):
        module.run_phase(project, tmp_path, "P03", retry)


def test_wm_harmonization_keeps_private_rows_and_only_returns_counts(tmp_path, monkeypatch):
    module = _load("wm_phase")
    source = tmp_path / "source"
    for name in (
        "analysis_spec.yaml",
        "base.yaml",
        "datasets/multisite_working_memory.yaml",
        "construct_maps/multisite_working_memory.yaml",
    ):
        atomic_write_json(source / "conf" / name, {})
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda _path: lambda n: None)
    monkeypatch.setattr(module.signal, "signal", lambda *_args: None)

    def harmonizer(_project, _root, _family, output, report):
        atomic_write_json(output, {"observed_experience": None})
        result = {"status": "harmonized", "records": 1, "participants": 1}
        atomic_write_json(report, result)
        return result

    monkeypatch.setattr(module, "harmonize_family", harmonizer)
    result = module.run_phase(SimpleNamespace(root=source), tmp_path, "P04", tmp_path / "attempt")
    assert result == {"status": "harmonized", "records": 1, "participants": 1}
