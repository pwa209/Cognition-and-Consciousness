"""Lifecycle contract with tiny fake MRI paths; no claim to test real neuroimaging locally."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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


def fixture(tmp_path):
    source, root = tmp_path / "source", tmp_path / "root"
    raw = root / "data/raw/masked_content_fmri/1.0.3"
    plan = load_structured(SOURCE / "conf/masked_neural_plan.yaml")
    plan.update(
        expected_bold_runs=7, expected_trial_count_histogram={"2": 7}, expected_source_trials=14
    )
    atomic_write_json(source / "conf/masked_neural_plan.yaml", plan)
    for name in ("analysis_spec.yaml", "construct_maps/masked_content_fmri.yaml"):
        atomic_write_json(source / "conf" / name, load_structured(SOURCE / "conf" / name))
    for i in range(1, 8):
        subject = f"sub-0{i}"
        folder = raw / subject / "ses-1/func"
        folder.mkdir(parents=True)
        (raw / subject / (subject + "_T1w.nii.gz")).write_text("NOT REAL MRI: UNIT FIXTURE")
        stem = subject + "_ses-1_task-test_run-1"
        (folder / (stem + "_bold.nii.gz")).write_text("NOT REAL MRI: UNIT FIXTURE")
        atomic_write_json(folder / (stem + "_bold.json"), {"RepetitionTime": 0.85})
        (folder / (stem + "_events.tsv")).write_bytes(
            (SOURCE / "tests/fixtures/masked_volume_events.tsv").read_bytes()
        )
    p03 = root / "analysis/P03/masked_content_fmri/1/status.json"
    atomic_write_json(p03, {"status": "SUCCESS"})
    return source, root, raw, p03


def test_prepare_calibrate_preprocess_lifecycles(tmp_path, monkeypatch):
    m = module("masked_neural_phase", monkeypatch)
    source, root, raw, p03 = fixture(tmp_path)
    monkeypatch.setattr(
        m, "source_integrity", lambda *_: SimpleNamespace(data_root=raw, manifest_sha256="fixture")
    )
    monkeypatch.setattr(m, "ScratchQuotaGuard", lambda _: lambda _: None)
    base = root / "analysis/masked-neural"
    kwargs = dict(p03=p03, producer=source)
    assert m.run_phase(root, source, "PREPARE", base / "PREPARE/dry", dry_run=True, **kwargs)[
        "dry_run"
    ]
    assert not (base / "PREPARE/dry").exists()
    result = m.run_phase(root, source, "PREPARE", base / "PREPARE/1", **kwargs)
    assert result["trials"] == 14 and result["calibration_trials"] == 4
    prepared = base / "PREPARE/1/status.json"
    assert load_structured(prepared)["status"] == "SUCCESS"
    assert load_structured(prepared.with_name("provenance.json"))["outputs"][
        "calibration-input.json"
    ]
    with pytest.raises(FileExistsError):
        m.run_phase(root, source, "PREPARE", prepared.parent, **kwargs)

    def fail(*_a, **_kw):
        raise ValueError("synthetic failure")

    for phase in ("CALIBRATE", "PREPROCESS"):
        options = dict(kwargs, prepared=prepared, subject_index=0)
        assert m.run_phase(root, source, phase, base / phase / "dry", dry_run=True, **options)[
            "dry_run"
        ]
        target = "fit_report_file" if phase == "CALIBRATE" else "preprocess"
        monkeypatch.setattr(m, target, fail)
        with pytest.raises(ValueError, match="synthetic failure"):
            m.run_phase(root, source, phase, base / phase / "failed", **options)
        assert load_structured(base / phase / "failed/status.json")["status"] == "FAILED"

        def fit(path, output, **_kw):
            data = load_structured(path)
            value = {
                "calibration_ids": sorted(set(data["subjects"])),
                "diagnostic_flags": {"poor_mixing": True},
            }
            atomic_write_json(output, value)
            return value

        monkeypatch.setattr(
            m, target, fit if phase == "CALIBRATE" else lambda *_: {"fixture_only": True}
        )
        m.run_phase(root, source, phase, base / phase / "retry", **options)
        assert load_structured(base / phase / "retry/status.json")["status"] == "SUCCESS"
        assert load_structured(base / phase / "failed/status.json")["status"] == "FAILED"
    with pytest.raises(ValueError, match="unknown"):
        m.run_phase(root, source, "P06", base / "invalid", **kwargs)
    artifact = prepared.with_name("partition.json")
    artifact.write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        m.preparation(root, source, prepared)


def test_preprocess_requires_actual_outputs(tmp_path, monkeypatch):
    m = module("masked_neural_phase", monkeypatch)
    plan = load_structured(SOURCE / "conf/masked_neural_plan.yaml")
    monkeypatch.setattr(m, "runtime", lambda *_: (["fake-container"], {}))
    monkeypatch.setattr(m.subprocess, "check_output", lambda *_a, **_k: "fMRIPrep 25.1.3")
    monkeypatch.setattr(m.subprocess, "run", lambda *_a, **_k: None)
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    runs = [dict(subject="sub-01", session="ses-1", run_id="sub-01_ses-1_task-test_run-1")]
    with pytest.raises(ValueError, match="required run output missing"):
        m.preprocess(tmp_path, plan, tmp_path / "raw", attempt, "sub-01", runs)


def test_submission_graph_has_real_subject_jobs_and_no_score_dependencies(tmp_path, monkeypatch):
    m = module("submit_masked_neural", monkeypatch)
    commands = []

    def submit(path, command):
        commands.append(command)
        return str(len(commands))

    monkeypatch.setattr(m, "submit_one", submit)
    graph = m.submit_graph(
        tmp_path, SOURCE, tmp_path / "ops", tmp_path / "p03", tmp_path / "producer"
    )
    assert len(commands) == 5
    assert graph["jobs"]["calibrate"] == "3"
    assert "--dependency=afterok:2" in commands[3]
    assert "--dependency=afterok:4" in commands[4]
    assert "--array=1-6%2" in commands[4]
    assert not graph["P06_P10_ready"]
    assert hash_file(tmp_path / "ops/campaign.json")


def test_prepare_failure_preserved_and_successful_new_attempt(tmp_path, monkeypatch):
    m = module("masked_neural_phase", monkeypatch)
    source, root, raw, p03 = fixture(tmp_path)
    monkeypatch.setattr(
        m, "source_integrity", lambda *_: SimpleNamespace(data_root=raw, manifest_sha256="fixture")
    )
    monkeypatch.setattr(m, "ScratchQuotaGuard", lambda _: lambda _: None)
    base = root / "analysis/masked-neural/PREPARE"
    event = next(raw.rglob("*_events.tsv"))
    original = event.read_bytes()
    event.write_text("wrong schema")
    with pytest.raises(ValueError, match="columns missing"):
        m.run_phase(root, source, "PREPARE", base / "failed", p03=p03, producer=source)
    assert load_structured(base / "failed/status.json")["status"] == "FAILED"
    event.write_bytes(original)
    m.run_phase(root, source, "PREPARE", base / "retry", p03=p03, producer=source)
    assert load_structured(base / "retry/status.json")["status"] == "SUCCESS"
    assert load_structured(base / "failed/status.json")["status"] == "FAILED"


def test_sampling_extension_lifecycle_preserves_model_and_failures(tmp_path, monkeypatch):
    m = module("extend_masked_report", monkeypatch)
    source, root, _raw, _p03 = fixture(tmp_path)
    atomic_write_json(
        source / "conf/masked_report_sampling_extension.yaml",
        load_structured(SOURCE / "conf/masked_report_sampling_extension.yaml"),
    )
    original = load_structured(source / "conf/analysis_spec.yaml")
    spec = m.extended_spec(source)
    assert spec["report_measurement"]["draws"] == 10000
    original["report_measurement"].update(draws=10000, warmup=20000)
    assert spec == original
    prepared = root / "analysis/masked-neural/PREPARE/1/status.json"
    atomic_write_json(prepared, {"status": "SUCCESS"})
    atomic_write_json(prepared.with_name("calibration-input.json"), {"fixture": True})
    monkeypatch.setattr(m, "preparation", lambda *_: None)
    monkeypatch.setattr(m, "load_report_calibration", lambda *_: None)
    monkeypatch.setattr(m, "ScratchQuotaGuard", lambda _: lambda _: None)
    base = root / "analysis/masked-neural/CALIBRATE_EXTENDED"
    assert m.run_extension(root, source, source, prepared, base / "dry", dry_run=True)["dry_run"]
    assert not (base / "dry").exists()

    def fail(*_a, **_k):
        raise ValueError("synthetic sampler failure")

    monkeypatch.setattr(m, "fit_report_file", fail)
    with pytest.raises(ValueError, match="sampler failure"):
        m.run_extension(root, source, source, prepared, base / "failed")
    assert load_structured(base / "failed/status.json")["status"] == "FAILED"

    def fit(path, output, **kwargs):
        value = {
            "calibration_ids": ["fixture:1", "fixture:2"],
            "diagnostic_flags": {"poor_mixing": True},
            "posterior": {"diagnostics": {"fixture": True}},
        }
        atomic_write_json(output, value)
        return value

    monkeypatch.setattr(m, "fit_report_file", fit)
    m.run_extension(root, source, source, prepared, base / "retry")
    assert load_structured(base / "retry/status.json")["status"] == "SUCCESS"
    assert load_structured(base / "retry/provenance.json")["outputs"]["posterior.json"]
    assert load_structured(base / "failed/status.json")["status"] == "FAILED"
    with pytest.raises(FileExistsError):
        m.run_extension(root, source, source, prepared, base / "retry")
