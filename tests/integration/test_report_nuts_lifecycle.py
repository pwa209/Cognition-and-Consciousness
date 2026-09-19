"""Mocked lifecycle tests do not substitute for actual server-side sampling tests."""

import importlib.util
from pathlib import Path

import pytest

from factorcon.util import atomic_write_json, hash_file, load_structured

SOURCE = Path(__file__).resolve().parents[2]


def module(name, monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE / "scripts/alliance"))
    spec = importlib.util.spec_from_file_location(
        name, SOURCE / "scripts/alliance" / (name + ".py")
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_plan_validation(tmp_path, monkeypatch):
    m = module("repair_masked_report", monkeypatch)
    assert m.plan(SOURCE)["probability_model_changed"] is False
    for name in ("analysis_spec.yaml", "masked_report_nuts_plan.yaml"):
        atomic_write_json(tmp_path / "conf" / name, load_structured(SOURCE / "conf" / name))
    value = load_structured(tmp_path / "conf/masked_report_nuts_plan.yaml")
    value["scientific_gates"] = True
    atomic_write_json(tmp_path / "conf/masked_report_nuts_plan.yaml", value)
    with pytest.raises(ValueError, match="unsupported sampler"):
        m.plan(tmp_path)


@pytest.mark.parametrize("phase", ["QUALIFY_NUTS", "CALIBRATE_NUTS"])
def test_lifecycle_dry_failure_success_and_preserved_retry(tmp_path, monkeypatch, phase):
    m = module("repair_masked_report", monkeypatch)
    root = tmp_path / "root"
    base = root / "analysis/masked-neural" / phase
    prepared = tmp_path / "prepared.json"
    atomic_write_json(prepared, {"fixture": True})
    monkeypatch.setattr(m, "check_inputs", lambda *_: prepared)
    monkeypatch.setattr(m, "ScratchQuotaGuard", lambda _: lambda _: None)
    args = (root, SOURCE, SOURCE, prepared)
    assert m.run(*args, base / "dry", phase, dry_run=True)["dry_run"]
    assert not (base / "dry").exists()

    def fail(*_):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(m, "action", fail)
    with pytest.raises(ValueError, match="synthetic failure"):
        m.run(*args, base / "failed", phase)
    assert load_structured(base / "failed/status.json")["status"] == "FAILED"
    monkeypatch.setattr(m, "action", lambda *_: {"diagnostic_flags": {"poor_mixing": True}})
    result = m.run(*args, base / "retry", phase)
    assert result["diagnostic_flags"]["poor_mixing"]
    assert m.verified_outputs(base / "retry/status.json", SOURCE, phase)["status"] == "SUCCESS"
    assert load_structured(base / "retry/provenance.json")["outputs"]["result.json"]
    assert load_structured(base / "failed/status.json")["status"] == "FAILED"
    with pytest.raises(FileExistsError):
        m.run(*args, base / "retry", phase)
    atomic_write_json(base / "retry/result.json", {"tampered": True})
    with pytest.raises(ValueError, match="changed"):
        m.verified_outputs(base / "retry/status.json", SOURCE, phase)


def test_submit_only_calibration_and_qualification(tmp_path, monkeypatch):
    m = module("submit_report_nuts", monkeypatch)
    commands = []

    def submit(path, command):
        commands.append(command)
        return str(len(commands))

    monkeypatch.setattr(m, "submit_one", submit)
    result = m.submit_graph(tmp_path, SOURCE, tmp_path / "ops", SOURCE, tmp_path / "prepared")
    assert result["jobs"] == {"QUALIFY_NUTS": "1", "CALIBRATE_NUTS": "2"}
    assert "--dependency=afterok:1" in commands[1]
    assert not result["scientific_gates"] and not result["MRI_jobs_changed"]
    assert hash_file(tmp_path / "ops/campaign.json")
