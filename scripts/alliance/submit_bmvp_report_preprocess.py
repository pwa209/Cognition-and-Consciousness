"""Queue a qualified BMVP report-MRI BIDS stage and three serial fMRIPrep jobs."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from submit_bmvp_report_cohort import validate_plan as validate_conversion_plan
from submit_empirical import submit_one

from factorcon.alliance import read_personal_quota, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured

from bmvp_report_prepare import validate_plan


def commands(root: Path, source: Path, operations: Path, jobs: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Define bounded, serial Slurm commands; no login-node production compute."""
    jobs = jobs or {}
    python = root / "environments/qualification-21417196/bin/python"
    export = f"export PYTHONPATH={shlex.quote(str(source))}:{shlex.quote(str(source / 'src'))}; "
    base = ["sbatch", "--parsable", "--account=def-ptewarie_cpu", "--no-requeue"]
    qualify = base + [
        "--job-name=fc-bmvp-report-qual", "--time=00:30:00", "--cpus-per-task=2", "--mem=4G",
        f"--output={operations}/QUALIFY-%j.log",
        "--wrap", export + f"cd {shlex.quote(str(source))}; {shlex.quote(str(python))} -m pytest -q",
    ]
    result = {"QUALIFY": qualify}
    prepare_dependency = [f"--dependency=afterok:{jobs['QUALIFY']}"] if "QUALIFY" in jobs else []
    result["PREPARE"] = base + [
        "--job-name=fc-bmvp-report-prepare", "--time=03:00:00", "--cpus-per-task=2", "--mem=8G",
        f"--output={operations}/PREPARE-%j.log", *prepare_dependency,
        "--wrap", export + (
            f"{shlex.quote(str(python))} {shlex.quote(str(source / 'scripts/alliance/bmvp_report_prepare.py'))} "
            f"--root {shlex.quote(str(root))} --job $SLURM_JOB_ID"
        ),
    ]
    previous = jobs.get("PREPARE")
    for participant in ("191", "223", "238"):
        dependency = [f"--dependency=afterok:{previous}"] if previous else []
        result[f"PREPROCESS-{participant}"] = base + [
            f"--job-name=fc-bmvp-preproc-{participant}", "--time=1-12:00:00",
            "--cpus-per-task=8", "--mem=64G",
            f"--output={operations}/PREPROCESS-{participant}-%j.log", *dependency,
            "--wrap", export + (
                f"{shlex.quote(str(python))} {shlex.quote(str(source / 'scripts/alliance/bmvp_report_preprocess.py'))} "
                f"--root {shlex.quote(str(root))} --prepared-job {jobs.get('PREPARE', '<PREPARE_JOB>')} "
                f"--participant {participant} --job $SLURM_JOB_ID"
            ),
        ]
        previous = jobs.get(f"PREPROCESS-{participant}")
    return result


def dispatch(root: Path, source: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Submit one immutable source release, failing closed on quota/receipts.

    Qualification runs full tests, then a 13-run BIDS stage, then subject jobs
    serially. Any technical failure leaves successors dependency-held. Scientific
    results cannot cancel or select a participant; work trees are safely archived.
    """
    import fcntl

    root = validate_fresh_root(root)
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("authorized intact source release required")
    plan = load_structured(source / "conf/bmvp_report_preprocess.yaml")
    validate_plan(plan)
    validate_conversion_plan(load_structured(source / "conf/bmvp_report_cohort_pilot.yaml"))
    p03 = load_structured(root / "analysis/P03/bmvp/21409966/status.json")
    if p03.get("status") != "SUCCESS" or p03.get("family") != "bmvp":
        raise ValueError("BMVP P03 predecessor missing")
    quota = read_personal_quota()
    if quota.limit_bytes - quota.used_bytes < 200_000_000_000 or quota.limit_files - quota.used_files < 100_000:
        raise ValueError("personal scratch headroom below BMVP work reserve")
    operations = root / "operations/bmvp-report-preprocess" / source.parent.name
    if dry_run:
        return {"dry_run": True, "scope": plan["scope"], "qualification": True,
                "prepare_runs": 13, "serial_participants": ["191", "223", "238"],
                "commands": list(commands(root, source, operations))}
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "dispatch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        jobs: dict[str, str] = {}
        for stage in ("QUALIFY", "PREPARE", "PREPROCESS-191", "PREPROCESS-223", "PREPROCESS-238"):
            command = commands(root, source, operations, jobs)[stage]
            jobs[stage] = submit_one(operations / f"{stage}.json", command)
        result = {
            "status": "SUBMITTED", "source_release": str(source),
            "plan_sha256": hash_file(source / "conf/bmvp_report_preprocess.yaml"),
            "jobs": jobs, "max_simultaneous_fmriprep_subjects": 1,
            "p08_ready": False, "scientific_gate": None,
        }
        atomic_write_json(operations / "dispatch.json", result)
        return result


def main() -> int:
    """Run on verified Rorqual login; submit compute work through Slurm only."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(dispatch(args.root, Path(__file__).resolve().parents[2], dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
