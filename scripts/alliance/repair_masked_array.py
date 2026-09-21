"""Finish a reconciled scheduler-limit interruption without resubmitting existing lane jobs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def dispatch(root: Path, batch_source: Path, analysis: Path, operations: Path) -> dict[str, Any]:
    """Keep submitted P06-P08; pack all 1,000 original P09 seeds into 50 tasks and queue P10."""
    reconciliation = load_structured(operations / "P09-reconciliation.json")
    failed = load_structured(operations / "P09.json")
    if (
        reconciliation.get("submission_reconciled_no_job") is not True
        or reconciliation.get("matching_original_jobs")
        or reconciliation.get("matching_live_jobs")
        or failed.get("status") != "UNCERTAIN"
        or failed.get("job_id")
    ):
        raise ValueError(
            "reconciled rejected original array required; never duplicate uncertain jobs"
        )
    live = subprocess.check_output(["squeue", "-u", "pwa209", "-h", "-o", "%i %j"], text=True)
    if any(line.split()[-1] == "fc-masked-P09" for line in live.splitlines() if line.split()):
        raise ValueError("original P09 job exists; reconcile before further submission")
    names = (
        "qualification",
        "reports",
        "noise",
        "bundle",
        "P06",
        "P07",
        "P08",
        *[f"extract-sub-0{i}" for i in range(1, 8)],
    )
    jobs = {}
    for name in names:
        record = load_structured(operations / (name + ".json"))
        if record["status"] != "SUBMITTED" or not record["job_id"].isdigit():
            raise ValueError("existing immutable job receipt required")
        jobs[name] = record["job_id"]
    repair = operations / ("scheduler-repair-" + batch_source.parent.name)
    repair.mkdir(parents=True, exist_ok=True)
    common = (
        f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={analysis}"
        f",FACTORCON_QUALIFICATION_JOB={jobs['qualification']}"
    )
    input_path = operations / "P09-input.json"
    env = (
        f"{common},FACTORCON_STAGE=P09,FACTORCON_BATCH_RELEASE={batch_source}"
        f",FACTORCON_INPUT={input_path},FACTORCON_INPUT_SHA256={hash_file(input_path)}"
    )
    jobs["P09"] = submit_one(
        repair / "P09-packed.json",
        [
            "sbatch",
            "--parsable",
            "--job-name=fc-masked-P09-packed",
            f"--output={repair}/P09-%A_%a.log",
            f"--export={env}",
            f"--dependency=afterok:{jobs['P06']}",
            "--array=0-49%2",
            "--no-requeue",
            str(batch_source / "scripts/alliance/masked_bootstrap_batch.sbatch"),
        ],
    )
    results = [
        {"phase": phase, "status": f"analysis/downstream/{phase}/{jobs[phase]}/status.json"}
        for phase in ("P07", "P08")
    ]
    results.extend(
        {
            "phase": "P09",
            "replicate": i,
            "status": f"analysis/downstream/P09/{jobs['P09']}-{i}/status.json",
        }
        for i in range(1000)
    )
    config = {
        "stage": "P10",
        "bundle": f"analysis/masked-lane/BUNDLE/{jobs['bundle']}/status.json",
        "results": results,
    }
    graph = repair / "P10-input.json"
    if graph.exists() and load_structured(graph) != config:
        raise ValueError("report graph changed; do not overwrite")
    if not graph.exists():
        atomic_write_json(graph, config)
    env = (
        f"{common},FACTORCON_STAGE=P10,FACTORCON_INPUT={graph}"
        f",FACTORCON_INPUT_SHA256={hash_file(graph)}"
    )
    jobs["P10"] = submit_one(
        repair / "P10.json",
        [
            "sbatch",
            "--parsable",
            "--job-name=fc-masked-P10",
            f"--output={repair}/P10-%A_%a.log",
            f"--export={env}",
            "--dependency=afterany:" + ":".join(jobs[p] for p in ("P07", "P08", "P09")),
            str(analysis / "scripts/alliance/masked_lane.sbatch"),
        ],
    )
    value = {
        "jobs": jobs,
        "created_utc": utc_now(),
        "scientific_gate": None,
        "analysis_source": str(analysis),
        "batch_source": str(batch_source),
        "P09_replicates": 1000,
        "P09_scheduler_tasks": 50,
        "P09_replicates_per_task": 20,
        "P09_concurrent_workers": 2,
        "P08": "not_applicable_single_family",
        "reconciliation_sha256": hash_file(operations / "P09-reconciliation.json"),
    }
    atomic_write_json(repair / "dispatch.json", value)
    return value


def main() -> int:
    """Verify personal root/quota and both releases, then serialize scheduler repair receipts."""
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    for release in (source, args.analysis):
        record = read_source_record(root, release)
        if record.get("analysis_execution_authorized") is not True or any(
            hash_file(release / p) != h for p, h in record["files"].items()
        ):
            raise ValueError("authorized immutable analysis/batch source required")
    operations = root / "operations/masked-lane" / args.analysis.parent.name
    os.umask(0o077)
    with (operations / "submission.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ScratchQuotaGuard(operations / "scheduler-repair-quota.json")(0)
        print(json.dumps(dispatch(root, source, args.analysis, operations)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
