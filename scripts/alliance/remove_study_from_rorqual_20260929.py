"""One-time, exact-root Rorqual study removal after a GitHub results checkpoint.

Run --preflight on a login node. Run --execute only as a scheduled compute job
named fc-cognition-removal. The receipt lives outside the deleted study root.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import pwd
import shutil
import stat
import subprocess
import tempfile

ROOT = pathlib.Path("/scratch/pwa209/cognition-and-consciousness")
PARENT = pathlib.Path("/scratch/pwa209")
CHILD = "fresh-20260916"
OWNER = "pwa209"
JOB_NAME = "fc-cognition-removal"
RECEIPT = pathlib.Path("/home/pwa209/factorcon-study-removal-20260929.json")
CHECKPOINT_COMMIT = "6447e09"


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def command(args: list[str], *, timeout: int = 30) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=True)
    return proc.stdout.strip()


def validate_target() -> dict[str, object]:
    if os.geteuid() != pwd.getpwnam(OWNER).pw_uid:
        raise RuntimeError("wrong Unix user")
    if PARENT.resolve(strict=True) != PARENT or PARENT.is_symlink():
        raise RuntimeError("scratch parent identity changed")
    if ROOT.parent != PARENT or ROOT.is_symlink() or ROOT.resolve(strict=True) != ROOT:
        raise RuntimeError("study root identity changed")
    root_stat = ROOT.lstat()
    if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.geteuid():
        raise RuntimeError("study root is not an owned directory")
    children = sorted(p.name for p in ROOT.iterdir())
    if children != [CHILD]:
        raise RuntimeError(f"unexpected study-root children: {children}")
    fresh = ROOT / CHILD
    if fresh.is_symlink() or not stat.S_ISDIR(fresh.lstat().st_mode):
        raise RuntimeError("fresh run is not a real directory")
    marker = fresh / "FRESH_RUN.json"
    if not stat.S_ISREG(marker.lstat().st_mode):
        raise RuntimeError("fresh-run identity marker is missing")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError("platform lacks fd-safe recursive removal")
    return {"root": str(ROOT), "child": CHILD, "marker": str(marker)}


def check_quiescence() -> dict[str, object]:
    own_job = os.environ.get("SLURM_JOB_ID")
    # -r expands compressed Slurm array ranges into inspectable task IDs.
    lines = command(["squeue", "-r", "-h", "-u", OWNER, "-o", "%i|%j|%T"]).splitlines()
    seen = 0
    inspected_arrays: set[str] = set()
    for line in lines:
        job_id, name, _state = line.split("|", 2)
        if job_id == own_job:
            continue
        seen += 1
        if name.startswith("fc-") or "cogn" in name.lower() or "factorcon" in name.lower():
            raise RuntimeError(f"another study job is active: {job_id} {name}")
        array_id = job_id.split("_", 1)[0]
        if array_id in inspected_arrays:
            continue
        detail = command(["scontrol", "show", "job", "-o", job_id])
        if str(ROOT) in detail:
            raise RuntimeError(f"another job references the study root: {job_id}")
        inspected_arrays.add(array_id)
    return {"checked_utc": now(), "other_active_user_jobs_checked": seen}


def quota_report() -> str:
    try:
        return command(["diskusage_report"], timeout=45)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable: {type(exc).__name__}: {exc}"


def write_receipt(value: dict[str, object]) -> None:
    if RECEIPT.parent.resolve(strict=True) != pathlib.Path("/home/pwa209"):
        raise RuntimeError("receipt parent identity changed")
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=RECEIPT.parent, delete=False
    ) as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        temporary = pathlib.Path(handle.name)
    os.replace(temporary, RECEIPT)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    target = validate_target()
    quiescence = check_quiescence()
    if args.preflight:
        print(json.dumps({"status": "PREFLIGHT", **target, **quiescence}, sort_keys=True))
        return 0
    if not os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_JOB_NAME") != JOB_NAME:
        raise RuntimeError("deletion requires the exact scheduled compute job")
    if RECEIPT.exists():
        raise RuntimeError("existing removal receipt requires manual reconciliation")
    receipt: dict[str, object] = {
        "status": "RUNNING",
        "started_utc": now(),
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "checkpoint_commit": CHECKPOINT_COMMIT,
        **target,
        "quiescence": quiescence,
        "quota_before": quota_report(),
    }
    write_receipt(receipt)
    print("STUDY_DELETE_BEGIN", json.dumps(target, sort_keys=True), flush=True)
    try:
        shutil.rmtree(ROOT)
        if ROOT.exists() or ROOT.is_symlink():
            raise RuntimeError("study root still exists after recursive removal")
    except BaseException as exc:
        receipt.update(status="FAILED", ended_utc=now(), error=f"{type(exc).__name__}: {exc}")
        write_receipt(receipt)
        raise
    receipt.update(status="SUCCESS", ended_utc=now(), quota_after=quota_report())
    write_receipt(receipt)
    print("STUDY_DELETE_DONE", json.dumps({"root": str(ROOT), "receipt": str(RECEIPT)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
