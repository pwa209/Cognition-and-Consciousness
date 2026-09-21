"""Qualify the new release in the protected study environment without duplicating its files."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from masked_neural_phase import runtime

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def main() -> int:
    """Run full suite and actual imaging-runtime fixture with atomic qualification markers."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    root = validate_fresh_root(parser.parse_args().root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / p) != h for p, h in record["files"].items()
    ):
        raise ValueError("immutable authorized release required")
    directory = root / "qualification" / os.environ["SLURM_JOB_ID"]
    directory.mkdir(parents=True, exist_ok=False)
    value = {
        "status": "RUNNING",
        "phase": "QUALIFY_MASKED_LANE",
        "source_release": str(source),
        "scientific_gate": None,
        "started_utc": utc_now(),
        "scope": "synthetic_tests_and_runtime_only",
        "reused_environment": sys.prefix,
    }

    def state() -> None:
        for name in ("status.json", "provenance.json"):
            atomic_write_json(directory / name, value)

    state()
    try:
        ScratchQuotaGuard(directory / "personal-quota.json")(0)
        with (directory / "tests.log").open("x") as log:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    f"cache_dir={directory}/pytest-cache",
                    "--basetemp",
                    str(directory / "pytest-temp"),
                    "--junitxml",
                    str(directory / "tests.xml"),
                ],
                cwd=source,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        prefix, env = runtime(root, load_structured(source / "conf/masked_neural_plan.yaml"))
        env["APPTAINERENV_PYTHONPATH"] = str(source / "src")
        env["APPTAINERENV_PYTHONDONTWRITEBYTECODE"] = "1"
        with (directory / "imaging-smoke.log").open("x") as log:
            subprocess.run(
                [
                    *prefix,
                    "python",
                    str(source / "scripts/alliance/masked_parcel_smoke.py"),
                    str(directory / "imaging-fixture"),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        value.update(
            status="SUCCESS",
            ended_utc=utc_now(),
            outputs={
                n: hash_file(directory / n) for n in ("tests.log", "tests.xml", "imaging-smoke.log")
            },
        )
        state()
    except BaseException as exc:
        value.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        state()
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
