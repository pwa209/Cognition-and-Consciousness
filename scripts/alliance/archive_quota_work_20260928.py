"""Losslessly consolidate one quiescent MRI work tree to restore inode headroom.

Only the historical 21450700-3/work scratch workspace is eligible. Raw data,
completed derivatives, status/provenance, logs and model outputs remain in place.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from inode_recovery import terminal, verify_source

from factorcon.alliance import read_personal_quota, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now
from factorcon.work_archive import pack, retire, work_target

ATTEMPT = "21450700-3"
HISTORICAL_SOURCE = "5c3cb879099efd4b59b210d6fc109af218a74447"
EXPECTED_MEMBERS = 86162
MIN_FREE_FILES_FOR_ARCHIVE = 50
BYTE_RESERVE = 500_000_000_000


def check_quiescence(root: Path, job: str) -> dict[str, Any]:
    """Refuse archiving while any other job uses this study root."""
    states = terminal(ATTEMPT.split("-", 1)[0])
    if not states or any(state != "FAILED" for state in states):
        raise ValueError("exact historical MRI job must remain terminal FAILED")
    queue = subprocess.run(
        ["squeue", "-h", "-u", "pwa209", "-o", "%A|%Z|%o"],
        capture_output=True,
        text=True,
        check=True,
        timeout=45,
    ).stdout
    study_jobs = []
    for line in queue.splitlines():
        if str(root) not in line:
            continue
        active = line.split("|", 1)[0].split("_", 1)[0]
        if active != job:
            raise ValueError(f"another live study job may use MRI work: {active}")
        study_jobs.append(active)
    if job not in study_jobs:
        raise ValueError("archive job absent from live scheduler census")
    return {"source_job_states": states, "checked_utc": utc_now()}


def historical_work(root: Path) -> tuple[Path, Path]:
    """Bind the exact failed receipt to its unredirected workspace."""
    attempt = root / "analysis/masked-neural/PREPROCESS" / ATTEMPT
    work = work_target(root, attempt / "work")
    historical_source = root / "releases" / HISTORICAL_SOURCE / "source"
    verify_source(root, historical_source)
    status = load_structured(attempt / "status.json")
    if (
        status.get("phase") != "PREPROCESS"
        or status.get("status") != "FAILED"
        or status.get("source_release") != str(historical_source)
        or not status.get("ended_utc")
        or status != load_structured(attempt / "provenance.json")
    ):
        raise ValueError("historical MRI attempt identity changed")
    return attempt, work


def run(root: Path, source: Path, job: str) -> dict[str, Any]:
    """Verify full tar before retiring only exact duplicate workspace members."""
    root = validate_fresh_root(root)
    verify_source(root, source)
    if not job.isdigit():
        raise ValueError("numeric Slurm job identity required")
    attempt, work = historical_work(root)
    destination = root / "archives/mri-work" / ATTEMPT
    if destination.exists():
        raise ValueError("archive destination already exists; reconcile before restart")
    operations = root / "operations/mri-work-quota-relief" / source.parent.name
    task = operations / job
    task.mkdir(parents=True, exist_ok=False)
    details: dict[str, Any] = {
        "status": "RUNNING",
        "source_release": str(source),
        "job": job,
        "target": str(work),
        "target_status_sha256": hash_file(attempt / "status.json"),
        "expected_members": EXPECTED_MEMBERS,
        "started_utc": utc_now(),
        "scientific_changes": False,
    }

    def record() -> None:
        atomic_write_json(task / "status.json", details)
        atomic_write_json(task / "provenance.json", details)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    signal.signal(signal.SIGTERM, stop)
    record()
    try:
        details["quiescence_before"] = check_quiescence(root, job)
        survey = pack(root, work, destination, dry_run=True)
        if survey["members"] != EXPECTED_MEMBERS:
            raise ValueError("MRI work member count changed from independent census")
        before = read_personal_quota()
        free_files = before.limit_files - before.used_files
        free_bytes = before.limit_bytes - before.used_bytes
        budget = survey["source_bytes"] + survey["members"] * 8192 + 10240
        if free_files < MIN_FREE_FILES_FOR_ARCHIVE or free_bytes < budget + BYTE_RESERVE:
            raise ValueError("insufficient personal scratch quota for verified tar")
        details["survey"] = survey
        details["free_files_before"] = free_files
        record()
        print("ARCHIVE_BEGIN", json.dumps(survey), flush=True)
        packed = pack(root, work, destination)
        details["quiescence_after_copy"] = check_quiescence(root, job)
        retired = retire(root, work, destination)
        after = read_personal_quota()
        details.update(
            status="SUCCESS",
            archive_sha256=retired["archive_sha256"],
            archive_manifest_sha256=retired["manifest_sha256"],
            members=retired["members"],
            source_removed=retired["source_removed"],
            free_files_after=after.limit_files - after.used_files,
            ended_utc=utc_now(),
        )
        if packed["archive_sha256"] != retired["archive_sha256"]:
            raise ValueError("archive identity changed during retirement")
    except BaseException as exc:
        details.update(status="FAILED", error=f"{type(exc).__name__}: {exc}", ended_utc=utc_now())
        raise
    finally:
        record()
    print("ARCHIVE_RETIRED", json.dumps(details), flush=True)
    return details


def main() -> int:
    os.umask(0o077)
    root = Path(os.environ["FACTORCON_ALLIANCE_ROOT"])
    source = Path(__file__).resolve().parents[2]
    job = os.environ["SLURM_JOB_ID"]
    run(root, source, job)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
