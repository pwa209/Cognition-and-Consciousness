"""Synthetic fixed-plan and scheduler topology tests; no cluster submission."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/alliance"


def module():
    """Load the production dispatcher with its sibling submit helper."""
    sys.path.insert(0, str(SCRIPTS))
    path = SCRIPTS / "submit_bmvp_report_cohort.py"
    spec = importlib.util.spec_from_file_location("submit_bmvp_report_cohort", path)
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_fixed_non_neural_cohort_plan_and_two_lanes() -> None:
    """Only the observed 223/238 series and <=2 active jobs can be dispatched."""
    m = module()
    plan = json.loads((Path(__file__).parents[2] / "conf/bmvp_report_cohort_pilot.yaml").read_text())
    items = m.validate_plan(plan)
    assert len(items) == 9
    source = Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916/releases/" + "a" * 40 + "/source")
    root = Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916")
    first = m.commands(root, source, (None, None), items[0], 0, root / "logs")
    second = m.commands(root, source, ("123", "456"), items[2], 0, root / "logs")
    assert not any(arg.startswith("--dependency") for arg in first)
    assert "--dependency=afterany:123" in second
    assert "--cpus-per-task=2" in second and "--mem=8G" in second
    assert "--series 223_RP_MRI_0008" in second[-1]


def test_plan_mutation_and_bad_lane_fail_closed() -> None:
    """Series/count drift and fabricated scheduler IDs cannot silently enter P08 prep."""
    m = module()
    plan = json.loads((Path(__file__).parents[2] / "conf/bmvp_report_cohort_pilot.yaml").read_text())
    plan["pending"][0]["dicom_count"] = 719
    with pytest.raises(ValueError, match="fixed non-neural"):
        m.validate_plan(plan)
    root = Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916")
    source = root / "releases" / ("a" * 40) / "source"
    with pytest.raises(ValueError, match="lane"):
        m.commands(root, source, ("not-a-job", None), {}, 0, root / "logs")
