"""Synthetic tests of quota-only P09 retry selection and lossless P10 coverage."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/alliance"
PLAN = Path(__file__).resolve().parents[2] / "conf/masked_p09_quota_recovery_20260926.yaml"


def module():
    """Load the dispatcher with its production sibling imports on Windows."""
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "submit_masked_p09_quota_recovery", SCRIPTS / "submit_masked_p09_quota_recovery.py"
    )
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_fixed_quota_only_retry_ids():
    m = module()
    plan = json.loads(PLAN.read_text())
    ids = m.expected_retry_ids(plan)
    assert len(ids) == len(set(ids)) == 95
    assert ids[:3] == (83, 84, 85)
    assert ids[-1] == 499
    assert 80 not in ids and 120 not in ids and 483 not in ids
    plan["failed_batch_completed_prefixes"]["4"] = [80, 81, 84]
    with pytest.raises(ValueError, match="prefix"):
        m.expected_retry_ids(plan)


def test_reconciled_graph_replaces_only_retry_rows():
    m = module()
    ids = m.expected_retry_ids(json.loads(PLAN.read_text()))
    original = {
        "stage": "P10", "bundle": "original-bundle",
        "results": [
            {"phase": "P07", "status": "p07"},
            {"phase": "P08", "status": "p08"},
            *(
                {"phase": "P09", "replicate": i,
                 "status": f"analysis/downstream/P09/21744877-{i}/status.json"}
                for i in range(1000)
            ),
        ],
    }
    value = m.build_reconciled_p10(original, ids, "999123")
    assert original["results"][2 + 83]["status"].endswith("21744877-83/status.json")
    assert value["results"][2 + 83]["status"].endswith("999123-83/status.json")
    assert value["results"][2 + 82]["status"].endswith("21744877-82/status.json")
    assert value["results"][2 + 500]["status"].endswith("21744877-500/status.json")
    assert len(value["results"]) == 1002
    assert value["recovery"]["retry_replicates"] == list(ids)
    original["results"][2 + 500] = original["results"][2 + 499]
    with pytest.raises(ValueError, match="duplicate"):
        m.build_reconciled_p10(original, ids, "999123")


def test_old_failure_audit_requires_capacity_error_and_preserves_successes(tmp_path, monkeypatch):
    m = module()
    plan = json.loads(PLAN.read_text())
    root = tmp_path
    analysis = root / "analysis_source"
    batch_source = root / "batch_source"
    input_path = root / m.OLD_OPERATIONS / "P09-input.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("{}")
    p06 = root / "analysis/downstream/P06/21744874/status.json"
    p06.parent.mkdir(parents=True)
    p06.write_text(json.dumps({"status": "SUCCESS", "source_release": str(analysis),
                               "campaign_sha256": "hash"}))
    observed_successes = []

    def predecessor(_root, path, source, _campaign, phase):
        assert source == analysis and phase == "P09"
        replicate = int(path.parent.name.split("-")[-1])
        observed_successes.append(replicate)
        return {"replicate": replicate}

    monkeypatch.setattr(m, "read_predecessor", predecessor)
    monkeypatch.setattr(m, "hash_file", lambda _: plan["original_p09_input_sha256"])
    for batch_str, completed in plan["failed_batch_completed_prefixes"].items():
        batch = int(batch_str)
        status = root / "analysis/masked-lane/BOOTSTRAP_BATCH" / f"21744877-{batch}" / "status.json"
        status.parent.mkdir(parents=True)
        status.write_text(json.dumps({
            "status": "FAILED", "phase": "P09_BATCH", "source_release": str(batch_source),
            "analysis_source_release": str(analysis), "completed": completed,
            "input_sha256": plan["original_p09_input_sha256"],
        }))
        failed = root / "analysis/downstream/P09" / f"21744877-{completed[-1] + 1}" / "status.json"
        failed.parent.mkdir(parents=True)
        failed.write_text(json.dumps({
            "status": "FAILED", "phase": "P09", "replicate": completed[-1] + 1,
            "source_release": str(analysis),
            "error": "CapacityError: personal quota service unavailable after 3 attempts",
        }))
    ids = m.audit_old_attempts(root, analysis, batch_source, plan)
    assert len(ids) == 95 and len(observed_successes) == 25
    failed.write_text(json.dumps({"status": "FAILED", "phase": "P09", "replicate": 484,
                                  "source_release": str(analysis), "error": "scientific result unfavorable"}))
    with pytest.raises(ValueError, match="not a quota-service failure"):
        m.audit_old_attempts(root, analysis, batch_source, plan)
