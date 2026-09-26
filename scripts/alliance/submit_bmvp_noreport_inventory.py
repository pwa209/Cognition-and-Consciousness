"""Submit one low-priority, metadata-only BMVP no-report MRI inventory."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from scripts.alliance.submit_empirical import submit_one
from scripts.alliance.bmvp_noreport_inventory import archive_rows, validate_plan

from factorcon.alliance import read_personal_quota, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured


def command(root: Path, source: Path, operations: Path) -> list[str]:
    """Build one bounded Slurm command; no TAR scanning on the login node."""
    python = root / "environments/qualification-21417196/bin/python"
    shell = (
        f"export PYTHONPATH={shlex.quote(str(source))}:{shlex.quote(str(source / 'src'))}; "
        f"{shlex.quote(str(python))} "
        f"{shlex.quote(str(source / 'scripts/alliance/bmvp_noreport_inventory.py'))} "
        f"--root {shlex.quote(str(root))} --job $SLURM_JOB_ID"
    )
    return [
        "sbatch", "--parsable", "--account=def-ptewarie_cpu", "--no-requeue",
        "--job-name=fc-bmvp-nrp-inventory", "--time=08:00:00",
        "--cpus-per-task=1", "--mem=8G", "--nice=10000",
        f"--output={operations}/inventory-%j.log", "--wrap", shell,
    ]


def dispatch(root: Path, source: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Validate P03/source/quota and durably submit exactly one inventory job."""
    import fcntl

    root = validate_fresh_root(root)
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("authorized intact Rorqual release required")
    plan = load_structured(source / "conf/bmvp_noreport_inventory.yaml")
    validate_plan(plan)
    archive_rows(root / "analysis/P03/bmvp/21409966/verified-files.jsonl", plan)
    p03 = load_structured(root / "analysis/P03/bmvp/21409966/status.json")
    if p03.get("status") != "SUCCESS" or p03.get("family") != "bmvp":
        raise ValueError("successful BMVP P03 predecessor required")
    quota = read_personal_quota()
    if quota.limit_bytes - quota.used_bytes < 100_000_000_000 or quota.limit_files - quota.used_files < 50_000:
        raise ValueError("personal scratch reserve below inventory floor")
    operations = root / "operations/bmvp-noreport-inventory" / f"dispatch-{source.parent.name}"
    if dry_run:
        return {"dry_run": True, "archives": 67, "scope": plan["scope"], "command": command(root, source, operations)}
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "dispatch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = operations / "inventory-submission.json"
        if receipt.exists():
            raise ValueError("inventory already submitted or uncertain; reconcile before retry")
        job = submit_one(receipt, command(root, source, operations))
        result = {
            "status": "SUBMITTED", "job": job, "source_release": str(source),
            "plan_sha256": hash_file(source / "conf/bmvp_noreport_inventory.yaml"),
            "scope": plan["scope"], "p08_ready": False, "scientific_gate": None,
        }
        atomic_write_json(operations / "dispatch.json", result)
        return result


def main() -> int:
    """Submit the fixed metadata audit from the verified Rorqual login node."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(dispatch(args.root, Path(__file__).resolve().parents[2], dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
