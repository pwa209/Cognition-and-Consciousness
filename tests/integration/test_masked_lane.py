"""Synthetic lifecycle, calibration separation and future-artifact dispatch tests."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

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
                x = rng.normal(size=(80, 6))
                series = rng.normal(size=(80, 400))
                coverage = np.zeros(400)
                coverage[:4] = 1
                packed.writestr(
                    name,
                    m.npz_bytes(
                        series=series, coverage=coverage, task=x, nuisance=np.ones((80, 1))
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
        report / "posterior.json", {"posterior": posterior, "calibration_ids": cal_ids}
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
    assert len(calls) == 15
    assert set(result["jobs"]) >= {"P06", "P07", "P08", "P09", "P10", "bundle", "noise"}
    noise = load_structured(operations / "noise-input.json")
    assert set(noise["extractions"]) == {"sub-02", "sub-07"}
    assert "--array=0-999%2" in next(c for p, c in calls if p.name == "P09.json")
    assert "--dependency=afterok:111" in next(c for p, c in calls if p.name == "P07.json")
    assert len(load_structured(operations / "P10-input.json")["results"]) == 1002
