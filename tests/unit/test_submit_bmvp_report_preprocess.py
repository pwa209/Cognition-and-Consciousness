"""Synthetic BMVP report dispatch topology tests; never submit Slurm jobs."""

from __future__ import annotations

import importlib.util
import shlex
import sys
from pathlib import Path


def module():
    """Load the dispatcher with its sibling submit helpers available."""
    directory = Path(__file__).resolve().parents[2] / "scripts/alliance"
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location(
        "submit_bmvp_report_preprocess", directory / "submit_bmvp_report_preprocess.py"
    )
    assert spec is not None and spec.loader is not None
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_qualification_then_serial_preprocessing() -> None:
    """The stage cannot run before tests, and only one MRI subject runs at once."""
    m = module()
    root = Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916")
    source = root / "releases" / ("a" * 40) / "source"
    operations = root / "operations/bmvp-report-preprocess" / ("a" * 40)
    jobs = {
        "QUALIFY": "101", "PREPARE": "102", "PREPROCESS-191": "103",
        "PREPROCESS-223": "104",
    }
    commands = m.commands(root, source, operations, jobs)
    assert "--dependency=afterok:101" in commands["PREPARE"]
    assert "--dependency=afterok:102" in commands["PREPROCESS-191"]
    assert "--dependency=afterok:103" in commands["PREPROCESS-223"]
    assert "--dependency=afterok:104" in commands["PREPROCESS-238"]
    assert all("--cpus-per-task=8" in commands[x] for x in (
        "PREPROCESS-191", "PREPROCESS-223", "PREPROCESS-238"
    ))
    assert all("--no-requeue" in value for value in commands.values())
    for participant in ("191", "223", "238"):
        shell, flag, body = shlex.split(commands[f"PREPROCESS-{participant}"][-1])
        assert (shell, flag) == ("bash", "-lc")
        assert body.startswith("module load fmriprep/25.1.1; ")
        assert f"--participant {participant}" in body
