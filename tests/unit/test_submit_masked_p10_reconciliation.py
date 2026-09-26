"""Safe dependency construction for the quota-recovery report attempt."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def module():
    """Load the bounded P10 reconciler without a remote scheduler."""
    scripts = Path(__file__).resolve().parents[2] / "scripts/alliance"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(
        "submit_masked_p10_reconciliation", scripts / "submit_masked_p10_reconciliation.py"
    )
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_completed_jobs_are_verified_not_used_as_aged_dependencies(tmp_path):
    m = module()
    source = Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916")
    analysis = source / "releases" / m.ANALYSIS_RELEASE / "source"
    p10 = tmp_path / "P10-input.json"
    p10.write_text('{"stage":"P10"}')
    command = m.p10_command(source, analysis, tmp_path, "21842371", p10)
    assert "--dependency=afterany:21744877:21842371" in command
    assert not any("21744873" in arg or "21744875" in arg or "21744876" in arg for arg in command)
    assert "FACTORCON_STAGE=P10" in command[-2]
    assert command[-1].endswith("masked_lane.sbatch")
    with pytest.raises(ValueError, match="numeric retry job"):
        m.p10_command(source, analysis, tmp_path, "not-a-job", p10)
