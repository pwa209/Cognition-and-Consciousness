from __future__ import annotations

from pathlib import Path

from factorcon.config import load_project, validate_project

ROOT = Path(__file__).resolve().parents[2]


def test_project_is_explicitly_non_preregistered_and_gate_free() -> None:
    project = load_project(ROOT / "conf" / "base.yaml")
    assert project.analysis_spec["registration"] is None
    assert project.analysis_spec["scientific_gates"] is False
    assert project.analysis_spec["report_all_candidate_models"] is True
    assert project.analysis_spec["policy"]["negative_results_continue"] is True


def test_all_dataset_families_have_construct_maps() -> None:
    summary = validate_project(ROOT / "conf" / "base.yaml")
    assert summary["valid"] is True
    assert len(summary["dataset_families"]) == 7
    assert summary["candidate_models"] == ["M0", "M1", "M2", "M3", "M4", "M5"]

