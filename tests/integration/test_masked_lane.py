"""Synthetic lifecycle, calibration separation and future-artifact dispatch tests."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from factorcon.pipeline.neural_bundle import load_campaign
from factorcon.util import atomic_write_json, hash_file, load_structured

SOURCE = Path(__file__).resolve().parents[2]


def script(name, monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE / "scripts/alliance"))
    spec = importlib.util.spec_from_file_location(
        name, SOURCE / "scripts/alliance" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status(root, directory, phase, source=SOURCE):
    atomic_write_json(
        directory / "status.json",
        {
            "phase": phase,
            "status": "SUCCESS",
            "source_release": str(source),
            "scientific_gate": None,
            "outputs": {
                p.name: hash_file(p)
                for p in directory.iterdir()
                if p.is_file() and p.name != "status.json"
            },
        },
    )
    return (directory / "status.json").relative_to(root).as_posix()


def test_noise_bundle_and_future_handoff(tmp_path, monkeypatch):
    m = script("masked_lane_phase", monkeypatch)
    monkeypatch.setattr(m, "ScratchQuotaGuard", lambda _: lambda _: None)
    root = tmp_path
    rng = np.random.default_rng(42)
    subjects = [f"sub-0{i}" for i in range(1, 8)]
    calibration = ["sub-02", "sub-07"]
    evaluation = [s for s in subjects if s not in calibration]
    prep = root / "prepared"
    atomic_write_json(
        prep / "partition.json",
        {"calibration_subjects": calibration, "evaluation_subjects": evaluation},
    )
    prepared = status(root, prep, "PREPARE")
    extractions = {}
    for subject in subjects:
        directory = root / subject
        directory.mkdir()
        rows = []
        with zipfile.ZipFile(directory / "runs.zip", "w") as packed:
            for index in range(2):
                name = f"{subject}-{index}.npz"
                short = subject == "sub-07" and index == 1
                rows_count = 29 if short else 80
                x = rng.normal(size=(rows_count, 6))
                series = rng.normal(size=(rows_count, 400))
                coverage = np.zeros(400)
                coverage[:4] = 1
                packed.writestr(
                    name,
                    m.npz_bytes(
                        series=series, coverage=coverage, task=x,
                        nuisance=np.eye(rows_count) if short else np.ones((rows_count, 1))
                    ),
                )
                trials = [
                    {
                        "trial": i + 1,
                        "image_onset_seconds": i * 8 + 2,
                        "report": i % 3,
                        "nonliving": i // 3,
                        "probe_frames": i + 1,
                        "stimulus_id": f"image-{i}.jpg",
                        "response": (i % 2) + 1,
                        "correct": "1",
                    }
                    for i in range(6)
                ]
                rows.append(
                    {
                        "subject": subject,
                        "session": "ses-01",
                        "partition": index,
                        "member": name,
                        "timing": {"trials": trials},
                        "qc": {"excluded": False, "outside_scan_trials": []},
                    }
                )
        atomic_write_json(directory / "runs.json", {"subject": subject, "runs": rows})
        extractions[subject] = status(root, directory, "EXTRACT")
    noise = root / "analysis/masked-lane/NOISE/1"
    cfg = {
        "stage": "NOISE",
        "prepared": prepared,
        "extractions": {s: extractions[s] for s in calibration},
    }
    assert m.run(root, SOURCE, cfg, noise, dry_run=True)["dry_run"] and not noise.exists()
    result = m.run(root, SOURCE, cfg, noise)
    assert result["evaluation_neural_data_used"] is False
    assert result["retained_runs"] == 3
    assert result["design_excluded_runs"] == [{
        "subject": "sub-07", "member": "sub-07-1.npz", "rows": 29,
        "residual_df": 0, "reason": "design_residual_df_below_10",
    }]
    assert load_structured(noise / "provenance.json")["status"] == "SUCCESS"
    with pytest.raises(FileExistsError):
        m.run(root, SOURCE, cfg, noise)
    bad = root / "analysis/masked-lane/NOISE/bad"
    with pytest.raises(ValueError, match="reserved"):
        m.run(root, SOURCE, {**cfg, "extractions": {s: extractions[s] for s in evaluation}}, bad)
    assert load_structured(bad / "status.json")["status"] == "FAILED"
    m.run(root, SOURCE, cfg, root / "analysis/masked-lane/NOISE/retry")
    report = root / "reports"
    cal_ids = ["masked_content_fmri:" + s for s in calibration]
    posterior = {
        "beta": np.broadcast_to(np.array([-0.5, 2, 0.1, 0]), (1, 32, 4)).tolist(),
        "subject_effects": np.zeros((1, 32, 2)).tolist(),
        "context_effects": np.zeros((1, 32, 2)).tolist(),
        "thresholds": np.broadcast_to(np.array([0, 1]), (1, 32, 1, 2)).tolist(),
        "variances": np.ones((1, 32, 2)).tolist(),
        "subject_levels": cal_ids,
        "context_levels": [s + ":ses-01" for s in cal_ids],
        "anchor_id": "synthetic-test-not-empirical-E",
        "diagnostics": {},
        "context_specific_thresholds": False,
    }
    atomic_write_json(
        report / "posterior.json",
        {
            "posterior": posterior,
            "calibration_ids": cal_ids,
            "diagnostic_flags": {"rhat_above_1_01": False},
        },
    )
    reports = status(root, report, "CALIBRATE_NUTS")
    bundle = root / "analysis/masked-lane/BUNDLE/2"
    config = {
        "stage": "BUNDLE",
        "prepared": prepared,
        "reports": reports,
        "noise": str((noise / "status.json").relative_to(root)),
        "extractions": {s: extractions[s] for s in evaluation},
    }
    result = m.run(root, SOURCE, config, bundle)
    assert result["features"] == 4 and result["groups"] == 5
    data, _ = load_campaign(root, bundle / "campaign.json", ridge_fraction=0.1)
    assert data[0].design_draws.shape == (32, 5, 6, 3)
    assert data[0].noise.shape == (5, 12, 12)
    assert not set(data[0].group_ids) & set(data[0].calibration_ids)
    downstream = script("masked_lane_downstream", monkeypatch)
    producer = str((bundle / "status.json").relative_to(root))
    assert downstream.resolve_bundle(root, SOURCE, {"bundle": producer}) == bundle / "campaign.json"
    atomic_write_json(bundle / "campaign.json", {"tampered": True})
    with pytest.raises(ValueError, match="bytes changed"):
        downstream.resolve_bundle(root, SOURCE, {"bundle": producer})


def test_queued_dag_preserves_cohort_and_has_actual_phase_commands(tmp_path, monkeypatch):
    m = script("submit_masked_lane", monkeypatch)
    partition = {
        "calibration_subjects": ["sub-02", "sub-07"],
        "evaluation_subjects": ["sub-01", "sub-03", "sub-04", "sub-05", "sub-06"],
    }
    atomic_write_json(tmp_path / "partition.json", partition)
    monkeypatch.setattr(m, "proof", lambda *_a, **_kw: tmp_path)
    calls = []

    def submit(receipt, command):
        calls.append((receipt, command))
        return str(100 + len(calls))

    monkeypatch.setattr(m, "submit_one", submit)
    operations = tmp_path / "operations"
    result = m.dispatch(tmp_path, SOURCE, operations, "aux/status.json")
    assert len(calls) == 16
    assert set(result["jobs"]) >= {"P06", "P07", "P08", "P09", "P10", "bundle", "noise"}
    noise = load_structured(operations / "noise-input.json")
    assert set(noise["extractions"]) == {"sub-02", "sub-07"}
    assert "--array=0-999%2" in next(c for p, c in calls if p.name == "P09.json")
    assert "--dependency=afterok:112" in next(c for p, c in calls if p.name == "P07.json")
    assert len(load_structured(operations / "P10-input.json")["results"]) == 1002


def test_noise_recovery_dispatch_reuses_only_pinned_receipts(tmp_path, monkeypatch):
    """Retry graph preserves seven producers and all 1,000 seed identities."""
    m = script("submit_masked_noise_recovery", monkeypatch)
    root = tmp_path / "fresh-test"
    source = tmp_path / "new-release" / "source"
    operations = root / "operations/noise-recovery/new-release"
    producer = root / "releases" / ("a" * 40) / "source"
    batch = root / "releases" / ("b" * 40) / "source"
    plan = {
        "root": str(root), "scientific_gates": False,
        "extraction_source": str(producer.relative_to(root)).replace("\\", "/"),
        "batch_source": "b" * 40, "failed_noise_job": "123",
        "prepared": "prep/status.json", "reports": "reports/status.json",
        "calibration_extractions": {"sub-02": "extractions/02/status.json", "sub-07": "extractions/07/status.json"},
        "evaluation_extractions": {f"sub-0{i}": f"extractions/0{i}/status.json" for i in (1, 3, 4, 5, 6)},
        "bootstrap_replicates": 1000, "bootstrap_scheduler_tasks": 50,
        "bootstrap_concurrency": 2,
    }
    real_load = m.load_structured
    monkeypatch.setattr(m, "load_structured", lambda path: plan if path == source / "conf" / m.PLAN else real_load(path))
    monkeypatch.setattr(m, "verify_source", lambda *_: None)
    monkeypatch.setattr(m, "terminal", lambda _: ["FAILED"])
    monkeypatch.setattr(m, "ScratchQuotaGuard", lambda _: lambda _: None)
    atomic_write_json(root / "qualification/777/status.json", {"status": "SUCCESS", "source_release": str(source)})
    atomic_write_json(root / "analysis/masked-lane/NOISE/123/status.json", {"status": "FAILED", "error": "ValueError: insufficient residual degrees of freedom"})
    for subject, relative in (plan["calibration_extractions"] | plan["evaluation_extractions"]).items():
        atomic_write_json(root / relative, {"status": "SUCCESS", "phase": "EXTRACT", "configuration": {"subject": subject}, "source_release": str(producer)})
    commands = []

    def submit(_receipt, command):
        commands.append(command)
        return str(800 + len(commands))

    monkeypatch.setattr(m, "submit_one", submit)
    result = m.dispatch(root, source, operations, "777")
    assert set(result["jobs"]) == {"noise", "bundle", "P06", "P07", "P08", "P09", "P10"}
    assert result["P09_replicates"] == 1000 and result["P09_scheduler_tasks"] == 50
    assert len(load_structured(operations / "P10-input.json")["results"]) == 1002
    assert any("--array=0-49%2" in item for command in commands for item in command)
    assert plan["extraction_source"] == load_structured(operations / "noise-input.json")["extraction_source"]


def test_corrected_report_input_reuses_model_not_old_posterior(tmp_path, monkeypatch):
    from factorcon.models import report_nuts
    from factorcon.models.report_measurement import OrdinalPosterior

    m = script("masked_lane_phase", monkeypatch)
    monkeypatch.setattr(m, "ScratchQuotaGuard", lambda _: lambda _: None)
    monkeypatch.setattr(
        m, "version", lambda name: {"pymc": "5.24.0", "arviz": "0.22.0"}.get(name, "test")
    )
    root = tmp_path
    prepared = root / "prepared"
    atomic_write_json(
        prepared / "partition.json",
        {"calibration_subjects": ["sub-02", "sub-07"], "evaluation_subjects": ["sub-01"]},
    )
    prepared_status = status(root, prepared, "PREPARE")
    oldsource = root / "releases/old/source"
    for name in (
        "conf/masked_report_nuts_plan.yaml",
        "conf/analysis_spec.yaml",
        "src/factorcon/models/report_nuts.py",
        "src/factorcon/models/report_measurement.py",
    ):
        path = oldsource / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((SOURCE / name).read_bytes())
    old = root / "old-reports"
    atomic_write_json(old / "posterior.json", {"preserve": True})
    oldstatus = status(root, old, "CALIBRATE_NUTS", oldsource)
    aux = root / "aux"
    ids = ["masked_content_fmri:sub-02", "masked_content_fmri:sub-07"]
    value = {
        "schema_version": 1,
        "predictor_source": "non_neural_fixed_units",
        "categories": 3,
        "anchor_id": "synthetic",
        "design": [[1, 1.2, 0, 0], [1, 1.5, 1, 0]],
        "reports": [0, 2],
        "subjects": ids,
        "contexts": [i + ":ses-01" for i in ids],
    }
    atomic_write_json(aux / "calibration-input.json", value)
    auxstatus = status(root, aux, "AUX")

    def fit(data, **settings):
        assert np.allclose(data.design[:, 1], [1.2, 1.5])
        assert settings["parameterization"] == "centered" and settings["draws"] == 4000
        posterior = OrdinalPosterior(
            np.zeros((1, 32, 4)),
            np.zeros((1, 32, 2)),
            np.zeros((1, 32, 2)),
            np.zeros((1, 32, 1, 2)),
            np.ones((1, 32, 2)),
            tuple(ids),
            tuple(value["contexts"]),
            "synthetic",
            {},
        )
        fake = SimpleNamespace(data_vars={"fixture": SimpleNamespace(values=np.zeros(1))})
        return (
            posterior,
            {"flags": {"rhat": False}},
            SimpleNamespace(posterior=fake, sample_stats=fake),
        )

    monkeypatch.setattr(report_nuts, "fit_ordinal_nuts", fit)
    config = {
        "stage": "REPORT",
        "prepared": prepared_status,
        "previous_reports": oldstatus,
        "auxiliary": auxstatus,
    }
    attempt = root / "analysis/masked-lane/REPORT/1"
    result = m.run(root, SOURCE, config, attempt)
    assert result["corrected_physical_frame_counts"]
    assert load_structured(old / "posterior.json") == {"preserve": True}
    assert load_structured(attempt / "status.json")["status"] == "SUCCESS"
    with pytest.raises(FileExistsError):
        m.run(root, SOURCE, config, attempt)
