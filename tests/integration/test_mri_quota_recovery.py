"""Transient-quota recovery preserves cohort, science releases and exact DAG coverage."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from factorcon.util import load_structured

SOURCE = Path(__file__).resolve().parents[2]


def module():
    """Load the submission module with its sibling command helpers."""
    sys.path.insert(0, str(SOURCE / "scripts/alliance"))
    spec = importlib.util.spec_from_file_location(
        "submit_mri_quota_recovery", SOURCE / "scripts/alliance/submit_mri_quota_recovery.py"
    )
    value = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(value)
    return value


def test_recovery_dag_archives_first_and_keeps_all_bootstraps(tmp_path, monkeypatch):
    m = module()
    plan = json.loads((SOURCE / "conf/mri_quota_recovery_plan.yaml").read_text())
    calls = []

    def submit(receipt, command):
        calls.append((receipt, command))
        return str(1000 + len(calls))

    monkeypatch.setattr(m, "submit_one", submit)
    operations = tmp_path / "operations"
    result = m.dispatch(tmp_path, SOURCE, SOURCE, SOURCE, operations, plan)
    assert len(calls) == 15
    assert result["jobs"]["archive-failed-work"] == "1002"
    assert "--dependency=afterok:1002" in calls[2][1]
    assert "--dependency=afterok:1003" in calls[3][1]
    assert "--dependency=afterok:1004" in calls[4][1]
    for _receipt, command in calls[2:5]:
        exported = next(item for item in command if item.startswith("--export="))
        assert "FACTORCON_QUALIFICATION_JOB=1001" in exported
    assert "--dependency=afterok:1003" in calls[5][1]
    assert "--dependency=afterok:1004" in calls[6][1]
    assert "--dependency=afterok:1005" in calls[7][1]
    assert "--array=0-49%2" in calls[13][1]
    assert "--dependency=afterok:1010,afterany:1012:1013:1014" in calls[14][1]
    graph = load_structured(operations / "P10-input.json")
    bootstraps = [item for item in graph["results"] if item["phase"] == "P09"]
    assert [item["replicate"] for item in bootstraps] == list(range(1000))
    assert bootstraps[-1]["status"].endswith("1014-999/status.json")
    bundle = load_structured(operations / "bundle-input.json")
    assert set(bundle["extractions"]) == {"sub-01", "sub-03", "sub-04", "sub-05", "sub-06"}
    noise = load_structured(operations / "noise-input.json")
    assert set(noise["extractions"]) == {"sub-02", "sub-07"}


def test_recovery_plan_uses_stricter_stale_inode_reserve():
    plan = json.loads((SOURCE / "conf/mri_quota_recovery_plan.yaml").read_text())
    assert plan["quota_stale_reserve_files"] > plan["live_reserve_files"]
    assert plan["quota_stale_reserve_bytes"] > plan["live_reserve_bytes"]
    assert plan["quota_stale_charge_files"] > 0 and plan["quota_stale_charge_bytes"] > 0
