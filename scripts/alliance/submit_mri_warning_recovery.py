"""Queue only four unfinished MRI participants behind container regression qualification."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from inode_recovery import terminal, verify_source
from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, validate_fresh_root
from factorcon.util import atomic_write_json, load_structured, utc_now

PLAN = "mri_warning_recovery_plan.yaml"


def check_targets(root: Path, plan: dict[str, Any]) -> None:
    """Reject completed targets and nonterminal prior writers; subjects are zero-based indices.

    Eligibility uses technical state only, never scientific results or scores.
    """
    if plan["mri_subject_indices"] != [3, 4, 5, 6]:
        raise ValueError("only the four unfinished MRI participants are authorized here")
    for index in plan["mri_subject_indices"]:
        expected = "FAILED" if index == 3 else "CANCELLED"
        if terminal(plan["previous_jobs"][str(index)]) != [expected]:
            raise ValueError("prior job state changed; reconcile before retry")
        for marker in (root / "analysis/masked-neural/PREPROCESS").glob(f"*-{index}/status.json"):
            if load_structured(marker).get("status") == "SUCCESS":
                raise ValueError("completed MRI participant must not be resubmitted")


def command_for(
    root: Path,
    repair: Path,
    plan: dict[str, Any],
    mode: str,
    index: int | None = None,
    dependency: str | None = None,
) -> tuple[str, list[str]]:
    """Build bounded Slurm resources/dependencies, without dispatch; no analysis inputs read."""
    if mode not in {"qualify", "mri"}:
        raise ValueError("unknown warning-recovery mode")
    if mode == "mri" and (index not in plan["mri_subject_indices"] or not dependency):
        raise ValueError("MRI requires eligible index and technical predecessor")
    source = root / "releases" / plan["mri_source"] / "source" if mode == "mri" else repair
    environment = plan["mri_environment" if mode == "mri" else "qualification_environment"]
    if not (root / "environments" / environment / "bin/python").is_file():
        raise ValueError("protected study runtime unavailable")
    label = f"mri-{index}" if mode == "mri" else "qualification"
    operations = root / "operations/inode-recovery" / repair.parent.name
    export = (
        f"ALL,FACTORCON_RELEASE={repair},FACTORCON_MODE={mode},"
        f"FACTORCON_ENVIRONMENT={environment},FACTORCON_SCIENCE_SOURCE={source},"
        f"FACTORCON_RECOVERY_PLAN={PLAN}"
    )
    if mode == "mri":
        export += f",FACTORCON_SUBJECT_INDEX={index}"
    command = [
        "sbatch",
        "--parsable",
        "--account=def-ptewarie_cpu",
        f"--job-name=fc-plotfix-{label}",
        f"--output={operations}/{label}-%A_%a.log",
        "--kill-on-invalid-dep=yes",
        *(
            ["--cpus-per-task=8", "--mem=64G", "--time=5-00:00:00"]
            if mode == "mri"
            else ["--cpus-per-task=4", "--mem=16G", "--time=01:00:00"]
        ),
        f"--export={export}",
    ]
    if dependency:
        if not dependency.isdigit():
            raise ValueError("numeric scheduler dependency required")
        command.append(f"--dependency=afterok:{dependency}")
    command.append(str(repair / "scripts/alliance/inode_recovery.sbatch"))
    return label, command


def main() -> int:
    """Validate ownership, source, quota and inactivity; submit with lock and durable receipts."""
    import fcntl

    repair = Path(__file__).resolve().parents[2]
    plan = load_structured(repair / "conf" / PLAN)
    root = validate_fresh_root(Path(plan["root"]))
    verify_source(root, repair)
    verify_source(root, root / "releases" / plan["mri_source"] / "source")
    os.umask(0o077)
    operations = root / "operations/inode-recovery" / repair.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    # Shared lock across warning-repair releases, not just this release's receipt folder.
    with (operations.parent / "mri-warning-submit.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check_targets(root, plan)
        live = subprocess.run(
            ["squeue", "-h", "-u", "pwa209", "-o", "%i|%j"],
            capture_output=True,
            text=True,
            check=True,
            timeout=45,
        ).stdout
        for line in live.splitlines():
            name = line.partition("|")[2]
            if name.startswith(("fc-recover-mri", "fc-plotfix-", "fc-masked-")):
                raise ValueError("active MRI/recovery job requires reconciliation; no duplicate")
        ScratchQuotaGuard(
            operations / "submission-quota.json",
            reserve_files=plan["mri_start_free_files"],
            reserve_bytes=plan["live_reserve_bytes"],
        )(0)
        jobs: dict[str, str] = {}
        label, command = command_for(root, repair, plan, "qualify")
        previous = jobs[label] = submit_one(operations / f"{label}.json", command)
        for index in plan["mri_subject_indices"]:
            label, command = command_for(root, repair, plan, "mri", index, previous)
            previous = jobs[label] = submit_one(operations / f"{label}.json", command)
        atomic_write_json(
            operations / "campaign.json",
            {
                "jobs": jobs,
                "source": str(repair),
                "created_utc": utc_now(),
                "scientific_changes": False,
                "mri_concurrency": 1,
                "old_failures_preserved": True,
                "completed_subjects_repeated": False,
            },
        )
        print(json.dumps(jobs), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
