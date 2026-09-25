"""Durably submit bounded BMVP report-MRI conversion pilots, never neural fitting."""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Any

from submit_empirical import submit_one

from factorcon.alliance import read_personal_quota, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured


def validate_plan(plan: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Validate the fixed nine-series, two-lane pilot; counts are DICOM files."""
    pending = plan.get("pending")
    if (
        plan.get("schema_version") != 1
        or plan.get("scope") != "technical_report_mri_conversion_pilot_not_p08_fit"
        or plan.get("max_parallel_conversions") != 2
        or plan.get("selection_basis") != "first_three_report_mri_archives_with_complete_log_csv_and_720_trigger_task_runs_before_neural_outcomes"
        or plan.get("already_converted") != [f"191_RP_MRI_{i:04d}" for i in range(6, 10)]
        or not isinstance(pending, list)
        or len(pending) != 9
        or plan.get("scratch_reserve_bytes") != 500_000_000_000
        or plan.get("scratch_reserve_files") != 50_000
    ):
        raise ValueError("fixed BMVP conversion plan identity/limits mismatch")
    expected = [("223", i) for i in range(6, 11)] + [("238", i) for i in range(6, 10)]
    for item, (subject, index) in zip(pending, expected, strict=True):
        if item != {
            "archive": f"report/{subject}_RP_MRI.tar",
            "series": f"{subject}_RP_MRI_{index:04d}",
            "dicom_count": 720,
        }:
            raise ValueError("BMVP series plan differs from fixed non-neural inventory")
    return tuple(pending)


def commands(
    root: Path, source: Path, jobs_by_lane: tuple[str | None, str | None], item: dict[str, Any],
    lane: int, logs: Path,
) -> list[str]:
    """Create one 2-CPU Slurm command with a per-lane afterany dependency."""
    if lane not in {0, 1} or any(j is not None and not re.fullmatch(r"\d+", j) for j in jobs_by_lane):
        raise ValueError("invalid bounded dispatch lane")
    series = item["series"]
    release = source.parent.name
    command = (
        "set -euo pipefail; module load StdEnv/2023 python/3.12.4 dcm2niix; "
        f"export PYTHONPATH={source / 'src'}; "
        f"python {source / 'scripts/alliance/bmvp_mri_pilot.py'} "
        f"--root {root} --archive {item['archive']} --series {series} "
        f"--expected-count {item['dicom_count']} --job $SLURM_JOB_ID"
    )
    wrap = f"exec bash -l -c {shlex.quote(command)}"
    result = [
        "sbatch", "--parsable", "--account=def-ptewarie_cpu",
        f"--job-name=fc-bmvp-{series}", "--time=01:30:00",
        "--cpus-per-task=2", "--mem=8G",
        f"--output={logs}/{series}-%j.log",
    ]
    if jobs_by_lane[lane] is not None:
        result.append(f"--dependency=afterany:{jobs_by_lane[lane]}")
    result.extend(["--wrap", wrap])
    if not re.fullmatch(r"[0-9a-f]{40}", release):
        raise ValueError("immutable release identifier required")
    return result


def dispatch(root: Path, source: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Submit fixed DICOM conversions on personal scratch; no outcome-dependent selection.

    Slurm receipts are immutable per series. A disconnection after an uncertain
    submission requires scheduler reconciliation; no duplicate is auto-issued.
    Scientific P04/P06/P08 validity is not inferred from conversion success.
    """
    import fcntl

    root = validate_fresh_root(root)
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("authorized, hash-verified source required")
    plan_path = source / "conf/bmvp_report_cohort_pilot.yaml"
    plan = load_structured(plan_path)
    pending = validate_plan(plan)
    p03 = load_structured(root / "analysis/P03/bmvp/21409966/status.json")
    if p03.get("status") != "SUCCESS" or p03.get("family") != "bmvp":
        raise ValueError("BMVP P03 inventory must succeed before conversion")
    quota = read_personal_quota()
    if (
        quota.limit_bytes - quota.used_bytes <= plan["scratch_reserve_bytes"]
        or quota.limit_files - quota.used_files <= plan["scratch_reserve_files"]
    ):
        raise ValueError("personal scratch reserve insufficient")
    operations = root / "operations/bmvp-report-cohort" / source.parent.name
    logs = operations / "slurm"
    lanes: tuple[str | None, str | None] = (None, None)
    proposed = []
    for index, item in enumerate(pending):
        lane = index % 2
        command = commands(root, source, lanes, item, lane, logs)
        proposed.append({"series": item["series"], "lane": lane, "command": command})
        # Dry run deliberately does not assign fabricated job IDs.
    if dry_run:
        return {"dry_run": True, "series": [x["series"] for x in proposed], "parallel": 2}
    operations.mkdir(parents=True, exist_ok=True)
    logs.mkdir(exist_ok=True)
    with (operations / "dispatch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing: dict[str, dict[str, Any]] = {}
        for status in (root / "operations/bmvp-mri-pilot").glob("*/status.json"):
            value = load_structured(status)
            if value.get("series") in {item["series"] for item in pending}:
                if value["series"] in existing:
                    raise ValueError(f"duplicate existing series conversion: {value['series']}")
                existing[value["series"]] = value
        for series, state in existing.items():
            receipt = operations / f"{series}.json"
            if not receipt.is_file():
                raise ValueError(f"unrelated existing series conversion: {series}")
            submitted = load_structured(receipt)
            if submitted.get("status") != "SUBMITTED":
                raise ValueError(f"uncertain existing series submission: {series}")
            if state.get("job") != submitted.get("job_id"):
                raise ValueError(f"series conversion/receipt job mismatch: {series}")
        jobs: dict[str, str] = {}
        lanes = (None, None)
        for index, item in enumerate(pending):
            lane = index % 2
            command = commands(root, source, lanes, item, lane, logs)
            job = submit_one(operations / f"{item['series']}.json", command)
            jobs[item["series"]] = job
            mutable = list(lanes)
            mutable[lane] = job
            lanes = (mutable[0], mutable[1])
        result = {
            "status": "SUBMITTED",
            "scope": plan["scope"],
            "source_release": str(source),
            "plan_sha256": hash_file(plan_path),
            "jobs": jobs,
            "max_parallel_conversions": 2,
            "p08_ready": False,
        }
        atomic_write_json(operations / "dispatch.json", result)
        return result


def main() -> int:
    """Dispatch on Rorqual login with bounded Slurm jobs, or perform a dry run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(dispatch(args.root, Path(__file__).resolve().parents[2], dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
