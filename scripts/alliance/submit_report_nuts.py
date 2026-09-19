"""Durable same-model sampler-repair submission; never touches MRI jobs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from repair_masked_report import run, verify_release
from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, validate_fresh_root
from factorcon.util import atomic_write_json, utc_now


def submit_graph(
    root: Path, source: Path, operations: Path, producer: Path, prepared: Path
) -> dict[str, Any]:
    """Technical qualification precedes a fixed sampling budget, regardless of scientific effect."""
    env = (
        f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source},"
        f"FACTORCON_PREPARED_SOURCE={producer},FACTORCON_PREPARED={prepared}"
    )
    jobs = {}
    for phase in ("QUALIFY_NUTS", "CALIBRATE_NUTS"):
        dependency = (
            []
            if not jobs
            else [f"--dependency=afterok:{jobs['QUALIFY_NUTS']}", "--kill-on-invalid-dep=yes"]
        )
        extraenv = "" if not jobs else f",FACTORCON_QUALIFICATION_JOB={jobs['QUALIFY_NUTS']}"
        jobs[phase] = submit_one(
            operations / (phase + ".json"),
            [
                "sbatch",
                "--parsable",
                f"--job-name=fc-{phase.lower()}",
                f"--output={operations}/{phase}-%j.log",
                *dependency,
                f"--export={env},FACTORCON_PHASE={phase}{extraenv}",
                str(source / "scripts/alliance/repair_masked_report.sbatch"),
            ],
        )
    result = {
        "jobs": jobs,
        "source_release": str(source),
        "created_utc": utc_now(),
        "scientific_gates": False,
        "MRI_jobs_changed": False,
    }
    atomic_write_json(operations / "campaign.json", result)
    return result


def main() -> int:
    """Verify owner, personal quota, immutable inputs and dry run before scheduler writes."""
    import fcntl

    parser = argparse.ArgumentParser()
    for name in ("root", "producer", "prepared"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    root, source = validate_fresh_root(args.root), Path(__file__).resolve().parents[2]
    for release in (source, args.producer):
        verify_release(root, release)
    run(
        root,
        source,
        args.producer,
        args.prepared,
        root / "analysis/masked-neural/CALIBRATE_NUTS/dry-run",
        "CALIBRATE_NUTS",
        dry_run=True,
    )
    os.umask(0o077)
    operations = root / "operations/report-nuts" / source.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "submission.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ScratchQuotaGuard(operations / "personal-quota.json")(2_000_000_000)
        print(json.dumps(submit_graph(root, source, operations, args.producer, args.prepared)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
