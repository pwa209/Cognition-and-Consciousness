"""Structural-bootstrap recovery fixtures contain no participant measurements."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def module(monkeypatch):
    """Load the checked-in cluster script; paths are synthetic and no SSH is used."""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/alliance"))
    sys.modules.pop("masked_p10_structural_repair", None)
    import masked_p10_structural_repair

    return masked_p10_structural_repair


def test_model_compatibility_accepts_only_line_ending_changes(tmp_path, monkeypatch):
    script = module(monkeypatch)
    old, new = tmp_path / "old", tmp_path / "new"
    files = (
        "conf/analysis_spec.yaml",
        "conf/downstream_plan.yaml",
        "src/factorcon/config.py",
        "src/factorcon/util.py",
        "src/factorcon/pipeline/patterns.py",
        "src/factorcon/models/fit.py",
        "src/factorcon/stats/splits.py",
    )
    for name in files:
        for root, content in ((old, b"a\nb\n"), (new, b"a\r\nb\r\n")):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    script.verify_model_compatibility(old, new)
    (new / "src/factorcon/stats/splits.py").write_bytes(b"a\r\nc\r\n")
    with pytest.raises(ValueError, match=r"stats/splits\.py"):
        script.verify_model_compatibility(old, new)


def test_scheduler_copy_has_unix_line_endings_and_is_immutable(tmp_path, monkeypatch):
    script = module(monkeypatch)
    source, operations = tmp_path / "source", tmp_path / "operations"
    operations.mkdir()
    original = source / "scripts/alliance/masked_p10_structural_repair.sbatch"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"#!/usr/bin/env bash\r\necho ready\r\n")
    copy = script.scheduler_script(source, operations)
    assert copy.read_bytes() == b"#!/usr/bin/env bash\necho ready\n"
    assert script.scheduler_script(source, operations) == copy
    copy.write_bytes(b"different\n")
    with pytest.raises(ValueError, match="scheduler script differs"):
        script.scheduler_script(source, operations)


def test_repaired_graph_redirects_exact_structural_ids(monkeypatch):
    script = module(monkeypatch)
    old = Path(
        "/scratch/pwa209/cognition-and-consciousness/fresh-test/releases/" + "a" * 40 + "/source"
    )
    new = Path(
        "/scratch/pwa209/cognition-and-consciousness/fresh-test/releases/" + "b" * 40 + "/source"
    )
    original = {
        "results": [
            {"phase": "P07", "status": "analysis/downstream/P07/1/status.json"},
            {"phase": "P08", "status": "analysis/downstream/P08/2/status.json"},
            *(
                {
                    "phase": "P09",
                    "replicate": i,
                    "status": f"analysis/downstream/P09/old-{i}/status.json",
                }
                for i in range(1000)
            ),
        ]
    }
    failed = tuple(range(113))
    result = script.repaired_graph(original, failed, "12345", old, new)
    assert len(result["results"]) == 1002
    assert result["structural_retry_ids"] == list(failed)
    for row in result["results"][2:]:
        if row["replicate"] in failed:
            assert row["status"] == f"analysis/downstream/P09/12345-{row['replicate']}/status.json"
            assert row["original_status"].startswith("analysis/downstream/P09/old-")
            assert row["source_release"] == str(new)
        else:
            assert row["status"] == f"analysis/downstream/P09/old-{row['replicate']}/status.json"
            assert "original_status" not in row
            assert row["source_release"] == str(old)
    with pytest.raises(ValueError, match="113 unique"):
        script.repaired_graph(original, (0, 0, *range(2, 113)), "12345", old, new)


def test_technical_completion_replaces_only_quota_failed_attempt(monkeypatch):
    script = module(monkeypatch)
    release_root = Path("/scratch/pwa209/cognition-and-consciousness/fresh-test/releases")
    old = release_root / ("a" * 40) / "source"
    first = release_root / ("b" * 40) / "source"
    original = {
        "results": [
            {"phase": "P07", "status": "analysis/downstream/P07/1/status.json"},
            {"phase": "P08", "status": "analysis/downstream/P08/2/status.json"},
            *(
                {
                    "phase": "P09", "replicate": i,
                    "status": f"analysis/downstream/P09/original-{i}/status.json",
                }
                for i in range(1000)
            ),
        ]
    }
    failed = tuple([*range(112), 914])
    graph = script.technically_completed_graph(original, failed, old, first, "55555")
    assert graph["technical_retry_overrides"] == {"914": "55555"}
    assert graph["retry_job"] == script.FIRST_RETRY_JOB
    by_id = {row["replicate"]: row for row in graph["results"] if row["phase"] == "P09"}
    assert by_id[914]["status"] == "analysis/downstream/P09/55555-914/status.json"
    assert by_id[914]["source_release"] == str(first)
    assert by_id[914]["original_status"] == original["results"][916]["status"]
    assert by_id[0]["status"] == f"analysis/downstream/P09/{script.FIRST_RETRY_JOB}-0/status.json"
    assert by_id[113]["status"] == "analysis/downstream/P09/original-113/status.json"
    with pytest.raises(ValueError, match="new numeric"):
        script.technically_completed_graph(original, failed, old, first, script.FIRST_RETRY_JOB)
    with pytest.raises(ValueError, match="unique structural retry"):
        script.technically_completed_graph(original, tuple(range(113)), old, first, "55555")


def test_report_failure_marker_and_immutable_restart(tmp_path, monkeypatch):
    script = module(monkeypatch)
    root = tmp_path / "fresh-test"
    source = root / "releases" / ("b" * 40) / "source"
    old = root / "releases" / ("a" * 40) / "source"
    source.mkdir(parents=True)
    graph = {
        "results": [], "families": ["masked_content_fmri"],
        "retry_job": "12345", "original_graph_sha256": "digest",
    }
    input_path = root / "P10-input.json"
    input_path.write_text(json.dumps(graph))
    monkeypatch.setattr(
        script, "checked_plan", lambda *_: {"requested_replicates": 1000, "original_p10_job": "1"}
    )
    monkeypatch.setattr(
        script,
        "original_evidence",
        lambda *_: (old, "campaign", {"results": []}, tuple(range(113))),
    )
    monkeypatch.setattr(
        script,
        "repaired_graph",
        lambda *_: {
            "results": [], "families": ["masked_content_fmri"],
            "retry_job": "12345", "original_graph_sha256": "digest",
        },
    )
    monkeypatch.setattr(script, "hash_file", lambda *_: "digest")

    class Quota:
        def __init__(self, *_args):
            pass

        def __call__(self, _bytes):
            raise RuntimeError("synthetic quota failure")

    monkeypatch.setattr(script, "ScratchQuotaGuard", Quota)
    with pytest.raises(RuntimeError, match="synthetic quota"):
        script.run_report(root, source, input_path, "777")
    status = json.loads((root / "analysis/downstream/P10/777/status.json").read_text())
    assert status["status"] == "FAILED"
    assert "synthetic quota failure" in status["error"]
    assert json.loads((root / "analysis/downstream/P10/777/provenance.json").read_text()) == status
    with pytest.raises(FileExistsError):
        script.run_report(root, source, input_path, "777")

    class AvailableQuota:
        def __init__(self, *_args):
            pass

        def __call__(self, _bytes):
            return None

    def synthetic_report(output, **kwargs):
        assert kwargs["bootstrap_design"]["unconditional_interval"] is False
        for name in ("summary.json", "scores.tsv", "candidate-audits.json"):
            (output / name).write_text("synthetic fixture")
        return {"intervals": {"M4-M0": {"complete_replicates": 1000}}}

    monkeypatch.setattr(script, "ScratchQuotaGuard", AvailableQuota)
    monkeypatch.setattr(script, "report_results", synthetic_report)
    assert script.run_report(root, source, input_path, "778")["status"] == "SUCCESS"
    success = json.loads((root / "analysis/downstream/P10/778/status.json").read_text())
    assert success["outputs"].keys() == {
        "result.json", "summary.json", "scores.tsv", "candidate-audits.json"
    }
