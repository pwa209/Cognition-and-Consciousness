"""Safety checks for the exact historical MRI workspace consolidation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/alliance"))
    sys.modules.pop("archive_quota_work_20260928", None)
    import archive_quota_work_20260928

    return archive_quota_work_20260928


def test_historical_work_requires_matching_failed_receipts(tmp_path, monkeypatch):
    script = module(monkeypatch)
    root = tmp_path
    attempt = root / "analysis/masked-neural/PREPROCESS" / script.ATTEMPT
    (attempt / "work").mkdir(parents=True)
    monkeypatch.setattr(script, "verify_source", lambda *_: None)
    expected_source = root / "releases" / script.HISTORICAL_SOURCE / "source"
    receipt = {
        "phase": "PREPROCESS", "status": "FAILED",
        "source_release": str(expected_source), "ended_utc": "2026-09-21T01:44:40Z",
    }
    for name in ("status.json", "provenance.json"):
        (attempt / name).write_text(json.dumps(receipt))
    assert script.historical_work(root) == (attempt, attempt / "work")
    (attempt / "status.json").write_text(json.dumps({**receipt, "status": "RUNNING"}))
    with pytest.raises(ValueError, match="identity changed"):
        script.historical_work(root)
    (attempt / "status.json").write_text(json.dumps(receipt))
    (attempt / "provenance.json").write_text(json.dumps({**receipt, "ended_utc": "other"}))
    with pytest.raises(ValueError, match="identity changed"):
        script.historical_work(root)


def test_quiescence_rejects_any_other_live_study_job(tmp_path, monkeypatch):
    script = module(monkeypatch)
    monkeypatch.setattr(script, "terminal", lambda *_: ["FAILED"])
    root = tmp_path

    def queue_with(job):
        return SimpleNamespace(stdout=f"123|{root}|self\n{job}|{root}|other\n")

    monkeypatch.setattr(script.subprocess, "run", lambda *_args, **_kwargs: queue_with("999"))
    with pytest.raises(ValueError, match="another live study job"):
        script.check_quiescence(root, "123")
    monkeypatch.setattr(script.subprocess, "run", lambda *_args, **_kwargs: queue_with("123"))
    assert script.check_quiescence(root, "123")["source_job_states"] == ["FAILED"]
    monkeypatch.setattr(script, "terminal", lambda *_: ["RUNNING"])
    with pytest.raises(ValueError, match="terminal FAILED"):
        script.check_quiescence(root, "123")
