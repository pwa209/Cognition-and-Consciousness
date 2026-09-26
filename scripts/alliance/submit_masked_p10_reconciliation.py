"""Resolve one rejected P10 dependency without touching the running P09 retry."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from downstream_phase import read_predecessor
from submit_empirical import submit_one

from factorcon.alliance import read_personal_quota, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured

RETRY_RELEASE = "2535a9a26423129234e733ba7ae41c0315f6e758"
ANALYSIS_RELEASE = "27ce5d1d4c565b5e5506fb4dce5e0843cd3b8dbe"
OLD_P09 = "21744877"


def p10_command(root: Path, analysis: Path, operations: Path, retry_job: str, input_path: Path) -> list[str]:
    """Depend only on live P09 jobs; completed predecessors are verified separately."""
    if not retry_job.isdigit() or not input_path.is_file():
        raise ValueError("numeric retry job and existing immutable P10 input required")
    common = (
        f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={analysis},"
        "FACTORCON_QUALIFICATION_JOB=21744804"
    )
    return [
        "sbatch", "--parsable", "--job-name=fc-P10-quota-reconciled-v2",
        f"--output={operations}/P10-v2-%j.log",
        f"--dependency=afterany:{OLD_P09}:{retry_job}",
        f"--export={common},FACTORCON_STAGE=P10,FACTORCON_INPUT={input_path},FACTORCON_INPUT_SHA256={hash_file(input_path)}",
        str(analysis / "scripts/alliance/masked_lane.sbatch"),
    ]


def reconcile(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Prove no first P10 job exists, then submit one durable replacement receipt."""
    import fcntl

    root = validate_fresh_root(root)
    current = Path(__file__).resolve().parents[2]
    current_record = read_source_record(root, current)
    if current_record.get("analysis_execution_authorized") is not True or any(
        hash_file(current / name) != digest for name, digest in current_record["files"].items()
    ):
        raise ValueError("reconciliation source changed")
    operations = root / "operations/p09-quota-recovery" / RETRY_RELEASE
    original = load_structured(operations / "P10-reconciled.json")
    retry = load_structured(operations / "P09-retry.json")
    if (
        original.get("status") != "UNCERTAIN"
        or original.get("job_id") is not None
        or "CalledProcessError" not in original.get("error", "")
        or retry.get("status") != "SUBMITTED"
        or not str(retry.get("job_id", "")).isdigit()
    ):
        raise ValueError("original rejection or retry job differs; reconcile manually")
    retry_job = retry["job_id"]
    command = original.get("command", [])
    if not any(arg == "--job-name=fc-P10-quota-reconciled" for arg in command):
        raise ValueError("uncertain receipt is not the known rejected P10 submission")
    analysis = root / "releases" / ANALYSIS_RELEASE / "source"
    record = read_source_record(root, analysis)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(analysis / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("original analysis source changed")
    p06 = load_structured(root / "analysis/downstream/P06/21744874/status.json")
    if p06.get("status") != "SUCCESS":
        raise ValueError("original P06 status changed")
    for phase, job in (("P07", "21744875"), ("P08", "21744876")):
        read_predecessor(
            root, root / "analysis/downstream" / phase / job / "status.json",
            analysis, p06["campaign_sha256"], phase,
        )
    bundle = load_structured(root / "analysis/masked-lane/BUNDLE/21744873/status.json")
    if bundle.get("status") != "SUCCESS" or bundle.get("source_release") != str(analysis):
        raise ValueError("original neural bundle changed")
    input_path = operations / "P10-input.json"
    graph = load_structured(input_path)
    if graph.get("stage") != "P10" or graph.get("recovery", {}).get("retry_p09_job") != retry_job:
        raise ValueError("reconciled graph does not bind the retry job")
    first = subprocess.run(
        ["squeue", "-h", "-u", "pwa209", "-n", "fc-P10-quota-reconciled", "-o", "%i"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    second = subprocess.run(
        ["sacct", "-S", "2026-09-26", "-u", "pwa209", "-n", "-X", "-P", "-o", "JobID,JobName%40"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    if first.stdout.strip() or any(
        line.split("|", 1)[-1].strip() == "fc-P10-quota-reconciled"
        for line in second.stdout.splitlines() if "|" in line
    ):
        raise ValueError("a first P10 job exists; do not duplicate")
    quota = read_personal_quota()
    if quota.limit_bytes - quota.used_bytes <= 500_000_000_000 or quota.limit_files - quota.used_files <= 50_000:
        raise ValueError("personal scratch reserve insufficient")
    new_command = p10_command(root, analysis, operations, retry_job, input_path)
    test = subprocess.run(
        [new_command[0], "--test-only", *new_command[1:]],
        capture_output=True, text=True, timeout=30,
    )
    if test.returncode:
        raise ValueError(f"replacement P10 dependency rejected by Slurm: {test.stderr.strip()}")
    if dry_run:
        return {"dry_run": True, "retry_job": retry_job, "dependency": new_command[4]}
    with (operations / "dispatch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        job = submit_one(operations / "P10-reconciled-v2.json", new_command)
        receipt = {
            "status": "SUBMITTED", "rejected_first_receipt": str(operations / "P10-reconciled.json"),
            "first_rejection": "Slurm allocation failure: Job dependency problem; no job found in queue/accounting",
            "retry_p09_job": retry_job, "reconciled_p10_job": job,
            "p10_input_sha256": hash_file(input_path), "scientific_gate": None,
        }
        atomic_write_json(operations / "P10-reconciliation.json", receipt)
        return receipt


def main() -> int:
    """Reconcile the known P10 rejection and print only non-sensitive receipts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(reconcile(args.root, dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
