"""Lossless consolidation of explicitly retired study environments, never active runtimes."""

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
from factorcon.work_archive import environment_target, pack, retire


def check_consumers(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Reject unknown live study jobs and any explicit reference to targeted environment names.

    Protect original simulation/MRI and PyMC runtimes; inspect scheduler consumers,
    not scientific results. Targets are fixed in the reviewed plan, never discovered
    dynamically for deletion. No jobs are canceled or modified here.
    """
    campaign = load_structured(
        root / "operations/inode-recovery" / plan["active_campaign_source"] / "campaign.json"
    )
    expected = {str(j) for j in campaign["jobs"].values()} | {os.environ["SLURM_JOB_ID"]}
    queue = subprocess.run(
        ["squeue", "-h", "-u", "pwa209", "-o", "%A|%Z|%o"],
        capture_output=True,
        text=True,
        check=True,
        timeout=45,
    ).stdout
    study_jobs = set()
    for line in queue.splitlines():
        if any(name in line for name in plan["targets"]):
            raise ValueError("a queued/running command references a target environment")
        if str(root) not in line:
            continue
        job = line.split("|", 1)[0].split("_", 1)[0]
        if not job.isdigit() or job not in expected:
            raise ValueError("unknown live study consumer; retain environments")
        study_jobs.add(job)
    for job in sorted(study_jobs):
        details = subprocess.run(
            ["scontrol", "show", "job", "-o", job],
            capture_output=True,
            text=True,
            check=True,
            timeout=45,
        ).stdout
        if any(name in details for name in plan["targets"]):
            raise ValueError("scheduler export references a target environment")
        if job != os.environ["SLURM_JOB_ID"] and "FACTORCON_ENVIRONMENT=" not in details:
            raise ValueError("study consumer runtime cannot be verified")
    if os.environ["SLURM_JOB_ID"] not in study_jobs:
        raise ValueError("scheduler census does not contain this study archive job")
    return {
        "checked_utc": utc_now(),
        "study_job_ids": sorted(study_jobs),
        "protected": plan["protected"],
        "campaign_sha256": hash_file(
            root / "operations/inode-recovery" / plan["active_campaign_source"] / "campaign.json"
        ),
    }


def main() -> int:
    """Archive terminal qualification environments with checksums and restart state.

    Byte units are decimal. Each tar is reconstructable at the exact original venv
    path; absolute interpreter symlinks are preserved as metadata, never followed.
    Removing loose copies never changes active environments or research artifacts.
    """
    source = Path(__file__).resolve().parents[2]
    plan = load_structured(source / "conf/environment_archive_plan.yaml")
    root = validate_fresh_root(Path(plan["root"]))
    verify_source(root, source)
    job = os.environ["SLURM_JOB_ID"]
    if not job.isdigit() or set(plan["targets"]) & set(plan["protected"]):
        raise ValueError("invalid scheduler identity or protected target")
    os.umask(0o077)
    operations = root / "operations/environment-consolidation" / source.parent.name
    attempt = operations / job
    attempt.mkdir(parents=True, exist_ok=False)
    state = {
        "status": "RUNNING",
        "source_release": str(source),
        "job": job,
        "plan_sha256": hash_file(source / "conf/environment_archive_plan.yaml"),
        "started_utc": utc_now(),
        "scientific_changes": False,
        "completed": [],
    }

    def record() -> None:
        atomic_write_json(attempt / "status.json", state)
        atomic_write_json(attempt / "provenance.json", state)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    signal.signal(signal.SIGTERM, stop)
    record()
    try:
        state["consumers"] = check_consumers(root, plan)
        state["qualification_states"] = {
            name: terminal(name.split("-")[1]) for name in plan["targets"]
        }
        for protected in plan["protected"]:
            if not (root / "environments" / protected / "bin/python").is_file():
                raise ValueError("protected active runtime missing")
        record()
        subprocess.run(
            [
                os.sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(attempt / "tests"),
                "tests/unit/test_work_archive.py",
                "tests/integration/test_environment_archive.py",
            ],
            cwd=source,
            check=True,
        )
        for name in plan["targets"]:
            environment = environment_target(root, root / "environments" / name)
            destination = root / "archives/environments" / name
            if not destination.exists():
                census = pack(root, environment, destination, category="environments", dry_run=True)
                if census["members"] != plan["expected_members_each"]:
                    raise ValueError("environment inventory changed; do not retire")
                quota = read_personal_quota()
                if (
                    quota.limit_files - quota.used_files < 100
                    or quota.limit_bytes - quota.used_bytes
                    < census["source_bytes"] + census["members"] * 8192 + plan["reserve_bytes"]
                ):
                    raise ValueError("insufficient personal quota for verified environment archive")
                print("ENVIRONMENT_ARCHIVE_BEGIN", json.dumps(census), flush=True)
                pack(root, environment, destination, category="environments")
            # Re-check that no new consumer appeared while copying the environment.
            state["consumers"] = check_consumers(root, plan)
            result = retire(root, environment, destination, category="environments")
            state["completed"].append(
                {
                    "environment": name,
                    "archive": str(destination),
                    "members": result["members"],
                    "archive_sha256": result["archive_sha256"],
                }
            )
            record()
            print("ENVIRONMENT_RETIRED", json.dumps(state["completed"][-1]), flush=True)
        state.update(status="SUCCESS", ended_utc=utc_now())
    except BaseException as exc:
        state.update(status="FAILED", error=f"{type(exc).__name__}: {exc}", ended_utc=utc_now())
        raise
    finally:
        record()
    print(json.dumps(state), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
