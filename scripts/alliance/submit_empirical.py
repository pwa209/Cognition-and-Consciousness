"""Submit tested preparation phases only; durable receipts prevent duplicate dispatch."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def submit_one(receipt: Path, command: list[str]) -> str:
    """Submit one Slurm job, recording intent and job ID; no outcome-based decisions.

    An uncertain submission is never retried automatically. Existing submitted
    receipts must have the identical command. Queue/sacct reconciliation is then
    required for SUBMITTING or UNCERTAIN records before any further dispatch.
    """
    if receipt.exists():
        previous = json.loads(receipt.read_text())
        if previous.get("status") == "SUBMITTED" and previous.get("command") == command:
            return previous["job_id"]
        raise ValueError("submission receipt needs reconciliation; no automatic duplicate")
    value: dict[str, Any] = {"status": "SUBMITTING", "command": command, "created_utc": utc_now()}
    atomic_write_json(receipt, value)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=True)
        job = result.stdout.strip().split(";")[0]
        if not job.isdigit():
            raise ValueError("non-numeric scheduler receipt")
    except BaseException as exc:
        value.update(status="UNCERTAIN", error=f"{type(exc).__name__}: {exc}")
        atomic_write_json(receipt, value)
        raise
    value.update(status="SUBMITTED", job_id=job, submitted_utc=utc_now())
    atomic_write_json(receipt, value)
    return job


def main() -> int:
    """Dispatch qualification, two independent P03 lanes and eligible P04 successors."""
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True:
        raise ValueError("analysis execution authorization required")
    for relative, digest in record["files"].items():
        if hash_file(source / relative) != digest:
            raise ValueError("source release changed")
    plan = load_structured(source / "conf/empirical_plan.yaml")
    operations = root / "operations/empirical-deployment" / source.parent.name
    os.umask(0o077)
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "submission.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ScratchQuotaGuard(operations / "personal-quota.json")(0)
        common = f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source}"
        qualify = submit_one(
            operations / "qualification.json",
            [
                "sbatch",
                "--parsable",
                f"--job-name=fc-emp-qual-{source.parent.name[:7]}",
                f"--output={operations}/qualification-%j.log",
                f"--export={common},FACTORCON_PYTHON_MODULE=python/3.12.4",
                str(source / "scripts/alliance/qualify.sbatch"),
            ],
        )
        lanes: list[str | None] = [None, None]
        jobs = {"qualification": qualify}
        for index, family in enumerate(plan["families"]):
            dependency = f"afterok:{qualify}"
            if previous := lanes[index % 2]:
                dependency += f",afterany:{previous}"
            env = f"{common},FACTORCON_QUALIFICATION_JOB={qualify},FACTORCON_FAMILY={family}"
            job = submit_one(
                operations / f"P03-{family}.json",
                [
                    "sbatch",
                    "--parsable",
                    f"--job-name=fc-P03-{family}",
                    f"--output={operations}/P03-{family}-%j.log",
                    f"--dependency={dependency}",
                    f"--export={env},FACTORCON_PHASE=P03",
                    str(source / "scripts/alliance/empirical_phase.sbatch"),
                ],
            )
            lanes[index % 2] = job
            jobs[f"P03-{family}"] = job
            if family in plan["harmonization_ready"]:
                predecessor = root / "analysis/P03" / family / job / "status.json"
                jobs[f"P04-{family}"] = submit_one(
                    operations / f"P04-{family}.json",
                    [
                        "sbatch",
                        "--parsable",
                        f"--job-name=fc-P04-{family}",
                        "--time=04:00:00",
                        f"--output={operations}/P04-{family}-%j.log",
                        f"--dependency=afterok:{job}",
                        f"--export={env},FACTORCON_PHASE=P04,FACTORCON_PREDECESSOR={predecessor}",
                        str(source / "scripts/alliance/empirical_phase.sbatch"),
                    ],
                )
        atomic_write_json(
            operations / "campaign.json",
            {
                "jobs": jobs,
                "source": str(source),
                "created_utc": utc_now(),
                "scope": "P03_and_ready_P04_only",
                "scientific_gates": False,
            },
        )
        print(json.dumps(jobs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
