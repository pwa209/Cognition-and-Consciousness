"""Scheduler packing must preserve all original replicate identities and stage behavior."""

import importlib.util
from pathlib import Path

import pytest

from factorcon.util import atomic_write_json, hash_file, load_structured

SOURCE = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location(
        "masked_bootstrap_batch", SOURCE / "scripts/alliance/masked_bootstrap_batch.py"
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_partition_and_lifecycle(tmp_path, monkeypatch):
    m = module()
    assert [i for batch in range(50) for i in m.batch_indices(batch)] == list(range(1000))
    with pytest.raises(ValueError):
        m.batch_indices(50)
    input_path = tmp_path / "input.json"
    atomic_write_json(input_path, {"stage": "P09"})
    args = (tmp_path, SOURCE, SOURCE, input_path, hash_file(input_path))
    attempt = tmp_path / "analysis/masked-lane/BOOTSTRAP_BATCH/100-2"
    assert m.run_batch(*args, attempt, 2, dry_run=True)["replicates"] == list(range(40, 60))
    assert not attempt.exists()
    called = []

    def call(command, *, env, check):
        called.append(int(env["SLURM_ARRAY_TASK_ID"]))
        assert env["PYTHONPATH"] == str(SOURCE / "src") and check

    monkeypatch.setattr(m.subprocess, "run", call)
    assert m.run_batch(*args, attempt, 2)["status"] == "SUCCESS"
    assert called == list(range(40, 60))
    with pytest.raises(FileExistsError):
        m.run_batch(*args, attempt, 2)

    def fail(*_a, **_kw):
        raise ValueError("synthetic technical failure")

    monkeypatch.setattr(m.subprocess, "run", fail)
    bad = tmp_path / "analysis/masked-lane/BOOTSTRAP_BATCH/101-2"
    with pytest.raises(ValueError, match="technical"):
        m.run_batch(*args, bad, 2)
    assert load_structured(bad / "status.json")["status"] == "FAILED"
    monkeypatch.setattr(m.subprocess, "run", call)
    assert (
        m.run_batch(*args, tmp_path / "analysis/masked-lane/BOOTSTRAP_BATCH/102-2", 2)["status"]
        == "SUCCESS"
    )


def test_repair_only_submits_p09_and_p10_with_all_global_indices(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE / "scripts/alliance"))
    spec = importlib.util.spec_from_file_location(
        "repair_masked_array", SOURCE / "scripts/alliance/repair_masked_array.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    operations = tmp_path / "operations"
    atomic_write_json(
        operations / "P09-reconciliation.json",
        {
            "submission_reconciled_no_job": True,
            "matching_original_jobs": [],
            "matching_live_jobs": [],
        },
    )
    atomic_write_json(operations / "P09.json", {"status": "UNCERTAIN"})
    atomic_write_json(operations / "P09-input.json", {"stage": "P09"})
    names = (
        "qualification",
        "reports",
        "noise",
        "bundle",
        "P06",
        "P07",
        "P08",
        *[f"extract-sub-0{i}" for i in range(1, 8)],
    )
    for i, name in enumerate(names):
        atomic_write_json(
            operations / (name + ".json"), {"status": "SUBMITTED", "job_id": str(100 + i)}
        )
    monkeypatch.setattr(m.subprocess, "check_output", lambda *_a, **_kw: "")
    calls = []

    def submit(receipt, command):
        calls.append(command)
        return str(9000 + len(calls))

    monkeypatch.setattr(m, "submit_one", submit)
    value = m.dispatch(tmp_path, SOURCE, SOURCE, operations)
    assert len(calls) == 2 and value["jobs"]["P09"] == "9001" and value["P09_replicates"] == 1000
    assert "--array=0-49%2" in calls[0] and "--dependency=afterok:104" in calls[0]
    assert "--dependency=afterany:105:106:9001" in calls[1]
    graph = load_structured(next(operations.glob("scheduler-repair-*/P10-input.json")))
    bootstrap = [r for r in graph["results"] if r["phase"] == "P09"]
    assert [r["replicate"] for r in bootstrap] == list(range(1000))
    assert bootstrap[-1]["status"].endswith("9001-999/status.json")
    monkeypatch.setattr(m.subprocess, "check_output", lambda *_a, **_kw: "500 fc-masked-P09\n")
    with pytest.raises(ValueError, match="exists"):
        m.dispatch(tmp_path, SOURCE, SOURCE, operations)
