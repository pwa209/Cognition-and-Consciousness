"""Execute one deterministic P05 replicate across all scenarios in its original plan.

Sharding changes scheduling only. Each shard uses base_seed + original replicate ID;
all outcomes and diagnostics remain present. No participant data are read here.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.simulation_stress import run_stress_plan, validate_stress_plan
from factorcon.util import atomic_write_json, hash_file, utc_now


def main() -> int:
    """Run a Slurm array shard with immutable input hashes and distinct attempt outputs."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--suite", choices=["reports", "patterns"], required=True)
    parser.add_argument("--replicate", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    marker = read_source_record(root, source)
    if (
        marker.get("release") != str(source)
        or marker.get("analysis_execution_authorized") is not True
    ):
        raise ValueError("source/authorization mismatch")
    name = "report_stress.yaml" if args.suite == "reports" else "pattern_stress.yaml"
    plan_path = source / "conf" / name
    plan = validate_stress_plan(plan_path)
    if not 0 <= args.replicate < plan["replicates"]:
        raise ValueError("replicate outside the versioned simulation plan")
    spec = source / "conf/analysis_spec.yaml"
    for path in (plan_path, spec):
        if hash_file(path) != marker["files"][path.relative_to(source).as_posix()]:
            raise ValueError("versioned simulation input changed")
    details = {
        "suite": args.suite,
        "original_replicate": args.replicate,
        "seed": 260830 + args.replicate,
        "source_plan_sha256": hash_file(plan_path),
        "analysis_spec_sha256": hash_file(spec),
        "scientific_gate": None,
        "participant_data_analyzed": False,
        "created_utc": utc_now(),
    }
    if args.dry_run:
        print(json.dumps({**details, "dry_run": True}))
        return 0
    job = os.environ["SLURM_ARRAY_JOB_ID"]
    task = os.environ["SLURM_ARRAY_TASK_ID"]
    if not job.isdigit() or task != str(args.replicate):
        raise ValueError("Slurm identity differs from requested replicate")
    attempt = root / "analysis/P05" / args.suite / f"replicate-{args.replicate:03d}" / job
    attempt.mkdir(parents=True, exist_ok=False)
    atomic_write_json(attempt / "provenance.json", details)
    status = {"status": "RUNNING", "updated_utc": utc_now(), **details}
    atomic_write_json(attempt / "status.json", status)

    def interrupted(signum: int, frame: object) -> None:
        raise InterruptedError(f"scheduler/user signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        shard = {**plan, "replicates": 1}
        atomic_write_json(attempt / "plan.json", shard)
        # The result uses local replicate zero; aggregate by original identity above.
        run_stress_plan(
            attempt / "plan.json", attempt / "result.json", analysis_spec=spec, seed=details["seed"]
        )
    except BaseException as exc:
        status.update(status="FAILED", error=f"{type(exc).__name__}: {exc}", updated_utc=utc_now())
        atomic_write_json(attempt / "status.json", status)
        raise
    else:
        status.update(status="SUCCESS", updated_utc=utc_now())
        atomic_write_json(attempt / "status.json", status)
    print(json.dumps({"status": "SHARD_COMPLETED", "output": str(attempt / "result.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
