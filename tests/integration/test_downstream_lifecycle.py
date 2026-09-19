"""Tiny synthetic software fixtures for empirical contracts, not participant findings."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from factorcon.pipeline.neural_bundle import load_bundle, load_campaign
from factorcon.simulation_stress import simulate_patterns
from factorcon.util import atomic_write_json, hash_file

SOURCE = Path(__file__).resolve().parents[2]


def script(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / f"scripts/alliance/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(root, path, **extra):
    return {"path": path.relative_to(root).as_posix(), "sha256": hash_file(path), **extra}


def fixture(root, family="fixture", seed=10):
    directory = root / family
    directory.mkdir(parents=True)
    data = simulate_patterns("unitary", seed=seed, groups=3, conditions=4, features=1)
    arrays = dict(
        patterns=data.patterns,
        group_ids=np.array([f"{family}:sub-{i}" for i in range(3)]),
        names=np.asarray(data.names),
        design_draws=data.design_draws,
        sensory=data.sensory,
        noise=data.noise,
        calibration_residuals=np.random.default_rng(seed).normal(size=(20, 1)),
        calibration_ids=np.array([f"{family}:cal-1"]),
        design_calibration_ids=np.array([f"{family}:cal-2"]),
        feature_ids=np.array(["feature-1"]),
        calibration_feature_ids=np.array(["feature-1"]),
        condition_ids=np.array([f"condition-{i}" for i in range(4)]),
        partition_ids=np.array([f"run-{i}" for i in range(data.patterns.shape[1])]),
    )
    array_path = directory / "input.npz"
    np.savez(array_path, **arrays)
    proof = directory / "synthetic-test-provenance.json"
    atomic_write_json(
        proof,
        {
            "status": "SUCCESS",
            "scientific_gate": None,
            "fixture_only_not_real_participant_data": True,
        },
    )
    bundle = dict(
        schema_version=1,
        source_kind="derived_neural_patterns",
        family=family,
        anchor_id="fixture-anchor",
        source_units="synthetic-test-units",
        feature_definition="single synthetic feature",
        noise_definition="known fixture noise",
        condition_definition="four synthetic conditions",
        partition_definition="simulated runs",
        independent_unit="participant",
        modality="fmri",
        design_source="external_calibration",
        noise_source="fixed_design",
        selection_basis="design_and_technical_integrity_only",
        arrays=record(root, array_path),
        provenance=[
            record(root, proof, role=r)
            for r in (
                "preprocessing",
                "noise_calibration",
                "condition_mapping",
                "report_or_construct_calibration",
            )
        ],
    )
    path = directory / "bundle.json"
    atomic_write_json(path, bundle)
    return path, bundle, arrays


def campaign(root, paths):
    path = root / "campaign.json"
    atomic_write_json(
        path,
        {
            "schema_version": 1,
            "scientific_gates": False,
            "bundles": [record(root, p) for p in paths],
        },
    )
    return path


def test_bundle_roundtrip_hashes_counts_traversal_and_isolation(tmp_path):
    path, bundle, arrays = fixture(tmp_path)
    data, meta = load_bundle(tmp_path, record(tmp_path, path), ridge_fraction=0.1)
    assert data.patterns.shape == arrays["patterns"].shape
    assert meta["units"] == "independent_residual_SD"
    assert set(data.calibration_ids).isdisjoint(data.group_ids)
    with pytest.raises(ValueError, match="SHA-256"):
        load_bundle(tmp_path, {**record(tmp_path, path), "sha256": "0" * 64}, ridge_fraction=0.1)
    from factorcon.errors import IntegrityError

    with pytest.raises(IntegrityError):
        load_bundle(tmp_path, {"path": "../escape.json", "sha256": "0" * 64}, ridge_fraction=0.1)
    for key, replacement, match in [
        ("calibration_ids", np.array(["fixture:sub-0"]), "overlap"),
        ("calibration_feature_ids", np.array(["wrong-feature"]), "order mismatch"),
        ("condition_ids", np.array(["a", "b", "c"]), "count mismatch"),
    ]:
        changed = {**arrays, key: replacement}
        np.savez(tmp_path / bundle["arrays"]["path"], **changed)
        bundle["arrays"] = record(tmp_path, tmp_path / bundle["arrays"]["path"])
        atomic_write_json(path, bundle)
        with pytest.raises(ValueError, match=match):
            load_bundle(tmp_path, record(tmp_path, path), ridge_fraction=0.1)


def test_global_calibration_leakage_and_empirical_only(tmp_path):
    a, va, _ = fixture(tmp_path, "a")
    b, vb, arrays = fixture(tmp_path, "b")
    arrays["calibration_ids"] = np.array(["a:sub-0"])
    np.savez(tmp_path / vb["arrays"]["path"], **arrays)
    vb["arrays"] = record(tmp_path, tmp_path / vb["arrays"]["path"])
    atomic_write_json(b, vb)
    with pytest.raises(ValueError, match="calibration"):
        load_campaign(tmp_path, campaign(tmp_path, [a, b]), ridge_fraction=0.1)
    va["source_kind"] = "synthetic_fixture"
    atomic_write_json(a, va)
    with pytest.raises(ValueError, match="empirical bundle"):
        load_bundle(tmp_path, record(tmp_path, a), ridge_fraction=0.1)


def test_full_stage_lifecycle_with_real_numerics(tmp_path, monkeypatch):
    module = script("downstream_phase")
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda _: lambda _: None)
    # Only computational size changes for this numerical smoke test.
    actual_loader = module.load_analysis_spec

    def small_spec(path):
        value = actual_loader(path)
        value["pattern_evaluation"].update(penalties=[0.01], optimizer_starts=1, max_iter=200)
        return value

    monkeypatch.setattr(module, "load_analysis_spec", small_spec)
    a, _, _ = fixture(tmp_path)
    config = campaign(tmp_path, [a])
    base = tmp_path / "analysis/downstream"
    dry = base / "P06/dry"
    assert module.run_phase(tmp_path, SOURCE, config, dry, "P06", dry_run=True)["dry_run"]
    assert not dry.exists()
    p06 = base / "P06/1"
    module.run_phase(tmp_path, SOURCE, config, p06, "P06")
    status = p06 / "status.json"
    assert json.loads(status.read_text())["status"] == "SUCCESS"
    for phase in ("P07", "P08", "P09"):
        attempt = base / phase / "2"
        module.run_phase(tmp_path, SOURCE, config, attempt, phase, p06=status, replicate=0)
        assert json.loads((attempt / "provenance.json").read_text())["status"] == "SUCCESS"
    scores = json.loads((base / "P07/2/result.json").read_text())
    assert {r["model"] for r in scores["rows"]} == {f"M{i}" for i in range(6)}
    assert json.loads((base / "P08/2/result.json").read_text())["status"] == "not_applicable"
    graph = tmp_path / "graph.json"
    atomic_write_json(
        graph,
        {
            "campaign_sha256": hash_file(config),
            "source_release": str(SOURCE),
            "families": ["fixture"],
            "results": [
                {"phase": "P07", "status": "analysis/downstream/P07/2/status.json"},
                {"phase": "P08", "status": "analysis/downstream/P08/2/status.json"},
                {"phase": "P09", "replicate": 0, "status": "analysis/downstream/P09/2/status.json"},
                {
                    "phase": "P09",
                    "replicate": 1,
                    "status": "analysis/downstream/P09/missing/status.json",
                },
            ],
        },
    )
    module.run_phase(tmp_path, SOURCE, config, base / "P10/3", "P10", graph=graph)
    report = json.loads((base / "P10/3/summary.json").read_text())
    assert report["coverage"][-1]["status"] == "UNAVAILABLE"
    assert all(v["percentile_95"] is None for v in report["intervals"].values())
    with pytest.raises(FileExistsError):
        module.run_phase(tmp_path, SOURCE, config, p06, "P06")
    (p06 / "family-00.npz").write_bytes(b"corrupt fixture")
    failed = base / "P07/failed"
    with pytest.raises(ValueError, match="bytes changed"):
        module.run_phase(tmp_path, SOURCE, config, failed, "P07", p06=status)
    assert json.loads((failed / "status.json").read_text())["status"] == "FAILED"
    # A new P06 attempt preserves the failed predecessor, and a dry retry succeeds.
    module.run_phase(tmp_path, SOURCE, config, base / "P06/retry", "P06")
    assert module.run_phase(
        tmp_path,
        SOURCE,
        config,
        base / "P07/retry",
        "P07",
        p06=base / "P06/retry/status.json",
        dry_run=True,
    )["dry_run"]


def test_submission_dag_and_missing_inputs(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE / "scripts/alliance"))
    module = script("submit_downstream")
    calls = []

    def submit(_receipt, command):
        calls.append(command)
        return str(len(calls))

    monkeypatch.setattr(module, "submit_one", submit)
    result = module.dispatch(tmp_path, SOURCE, tmp_path / "operations")
    assert result["empirical_jobs_submitted"] is False
    assert len(calls) == 2 and "fc-neural-input-audit" in " ".join(calls[-1])
    calls.clear()
    path, _, _ = fixture(tmp_path)
    result = module.dispatch(
        tmp_path, SOURCE, tmp_path / "with-input", campaign=campaign(tmp_path, [path])
    )
    assert result["empirical_jobs_submitted"]
    assert set(result["jobs"]) == {"qualification", "P06", "P07", "P08", "P09", "P10"}
    assert "--dependency=afterok:1" in calls[1]
    assert "--dependency=afterok:2" in calls[2]
    assert "--array=0-999%2" in calls[4]
    assert "--dependency=afterany:3:4:5" in calls[5]


@pytest.mark.parametrize("phase", ["P06", "P07", "P08", "P09", "P10"])
def test_every_phase_marks_missing_technical_input_failed(tmp_path, monkeypatch, phase):
    module = script("downstream_phase")
    monkeypatch.setattr(module, "ScratchQuotaGuard", lambda _: lambda _: None)
    config = tmp_path / "campaign.json"
    atomic_write_json(config, {"schema_version": 1, "scientific_gates": False, "bundles": []})
    attempt = tmp_path / "analysis/downstream" / phase / "missing"
    with pytest.raises(ValueError):
        module.run_phase(tmp_path, SOURCE, config, attempt, phase, replicate=0, dry_run=True)
    assert not attempt.exists()
    with pytest.raises(ValueError):
        module.run_phase(tmp_path, SOURCE, config, attempt, phase, replicate=0)
    value = json.loads((attempt / "status.json").read_text())
    assert value["status"] == "FAILED" and value["scientific_gate"] is None
    assert json.loads((attempt / "provenance.json").read_text())["error"]
