"""Retry only six quota-service-stopped P09 batches with immutable replicate IDs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from downstream_phase import read_predecessor
from submit_empirical import submit_one

from factorcon.alliance import read_personal_quota, read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured

PLAN = "conf/masked_p09_quota_recovery_20260926.yaml"
OLD_OPERATIONS = "operations/noise-recovery/27ce5d1d4c565b5e5506fb4dce5e0843cd3b8dbe"


def expected_retry_ids(plan: dict[str, Any]) -> tuple[int, ...]:
    """Derive the original global replicate IDs from six fixed technical failures."""
    prefixes = plan.get("failed_batch_completed_prefixes")
    expected_lengths = {4: 3, 6: 6, 7: 4, 8: 4, 23: 4, 24: 4}
    if (
        plan.get("schema_version") != 1
        or plan.get("scope") != "retry_only_technically_missing_p09_replicates"
        or plan.get("scientific_gates") is not False
        or plan.get("original_p09_job") != "21744877"
        or plan.get("retry_concurrency") != 4
        or not isinstance(prefixes, dict)
        or set(prefixes) != {str(i) for i in expected_lengths}
    ):
        raise ValueError("fixed quota-recovery plan identity changed")
    pending: list[int] = []
    for batch, length in expected_lengths.items():
        first = batch * 20
        if prefixes[str(batch)] != list(range(first, first + length)):
            raise ValueError("completed prefix differs from observed technical receipts")
        pending.extend(range(first + length, first + 20))
    if len(pending) != 95 or len(set(pending)) != 95:
        raise ValueError("95 original replicate IDs required")
    return tuple(pending)


def verify_source(root: Path, source: Path) -> None:
    """Check that an executable source is an authorized, immutable personal release."""
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("source release is not authorized and hash-verified")


def audit_old_attempts(root: Path, analysis: Path, batch_source: Path, plan: dict[str, Any]) -> tuple[int, ...]:
    """Prove old successes and quota-only failures; never select by model score."""
    pending = expected_retry_ids(plan)
    p09_input = root / OLD_OPERATIONS / "P09-input.json"
    if hash_file(p09_input) != plan["original_p09_input_sha256"]:
        raise ValueError("original P09 input bytes changed")
    p06 = load_structured(root / "analysis/downstream/P06/21744874/status.json")
    if p06.get("status") != "SUCCESS" or p06.get("source_release") != str(analysis):
        raise ValueError("original P06 predecessor changed")
    campaign_hash = p06["campaign_sha256"]
    for batch_str, completed in plan["failed_batch_completed_prefixes"].items():
        batch = int(batch_str)
        status = root / "analysis/masked-lane/BOOTSTRAP_BATCH" / f"21744877-{batch}" / "status.json"
        value = load_structured(status)
        if (
            value.get("status") != "FAILED"
            or value.get("phase") != "P09_BATCH"
            or value.get("source_release") != str(batch_source)
            or value.get("analysis_source_release") != str(analysis)
            or value.get("completed") != completed
            or value.get("input_sha256") != plan["original_p09_input_sha256"]
        ):
            raise ValueError(f"batch {batch} no longer matches recorded technical failure")
        for replicate in range(batch * 20, (batch + 1) * 20):
            old = root / "analysis/downstream/P09" / f"21744877-{replicate}" / "status.json"
            if replicate in completed:
                observed = read_predecessor(root, old, analysis, campaign_hash, "P09")
                if observed.get("replicate") != replicate:
                    raise ValueError(f"replicate {replicate} success identity mismatch")
            elif replicate == completed[-1] + 1:
                observed = load_structured(old)
                if (
                    observed.get("status") != "FAILED"
                    or observed.get("phase") != "P09"
                    or observed.get("replicate") != replicate
                    or observed.get("source_release") != str(analysis)
                    or not str(observed.get("error", "")).startswith("CapacityError: personal quota service unavailable")
                ):
                    raise ValueError(f"replicate {replicate} was not a quota-service failure")
            elif old.exists():
                raise ValueError(f"replicate {replicate} has unexpected old attempt")
    return pending


def terminal_failed_batches(job: str, batches: tuple[int, ...]) -> None:
    """Confirm all six original array indices are scheduler-terminal FAILED."""
    ids = ",".join(f"{job}_{batch}" for batch in batches)
    result = subprocess.run(
        ["sacct", "-j", ids, "-X", "-n", "-P", "-o", "JobID,State"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    states = dict(line.split("|", 1) for line in result.stdout.splitlines() if "|" in line)
    if states != {f"{job}_{batch}": "FAILED" for batch in batches}:
        raise ValueError("original failed batches are not exactly scheduler-terminal FAILED")


def build_reconciled_p10(original: dict[str, Any], pending: tuple[int, ...], retry_job: str) -> dict[str, Any]:
    """Keep all original P07/P08 and successful P09 links; redirect only 95 retry IDs."""
    if original.get("stage") != "P10" or not retry_job.isdigit():
        raise ValueError("original P10 graph or retry job invalid")
    rows = original.get("results")
    if not isinstance(rows, list) or len(rows) != 1002:
        raise ValueError("original P10 graph must list P07/P08 and 1000 replicates")
    seen = set()
    result = {**original, "results": []}
    for row in rows:
        replacement = dict(row)
        if row["phase"] == "P09":
            replicate = row["replicate"]
            if replicate in seen or replicate not in range(1000):
                raise ValueError("P09 graph has duplicate/invalid replicate")
            seen.add(replicate)
            if row["status"] != f"analysis/downstream/P09/21744877-{replicate}/status.json":
                raise ValueError("original P09 graph identity changed")
            if replicate in pending:
                replacement["status"] = f"analysis/downstream/P09/{retry_job}-{replicate}/status.json"
        result["results"].append(replacement)
    if seen != set(range(1000)) or {row["phase"] for row in rows[:2]} != {"P07", "P08"}:
        raise ValueError("P10 graph coverage changed")
    result["recovery"] = {
        "reason": "quota_service_timeout_only",
        "original_p09_job": "21744877",
        "retry_p09_job": retry_job,
        "retry_replicates": list(pending),
        "scientific_gate": None,
    }
    return result


def dispatch(root: Path, source: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Submit 95 original seeds in fresh Slurm attempts, then a complete P10 graph."""
    import fcntl

    root = validate_fresh_root(root)
    verify_source(root, source)
    plan = load_structured(source / PLAN)
    if str(root) != plan["root"]:
        raise ValueError("personal fresh-run root mismatch")
    analysis = root / "releases" / plan["analysis_source"] / "source"
    batch_source = root / "releases" / plan["batch_source"] / "source"
    verify_source(root, analysis)
    verify_source(root, batch_source)
    pending = audit_old_attempts(root, analysis, batch_source, plan)
    batches = tuple(int(k) for k in plan["failed_batch_completed_prefixes"])
    terminal_failed_batches(plan["original_p09_job"], batches)
    qualification = load_structured(root / "qualification" / plan["qualification_job"] / "status.json")
    if qualification.get("status") != "SUCCESS" or qualification.get("source_release") != str(analysis):
        raise ValueError("original analysis qualification changed")
    quota = read_personal_quota()
    if (
        quota.limit_bytes - quota.used_bytes <= plan["scratch_reserve_bytes"]
        or quota.limit_files - quota.used_files <= plan["scratch_reserve_files"]
    ):
        raise ValueError("personal scratch reserve insufficient")
    if dry_run:
        return {"dry_run": True, "replicate_count": len(pending), "retry_ids": list(pending), "parallel": 4}
    operations = root / "operations/p09-quota-recovery" / source.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "dispatch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        common = (
            f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={analysis},"
            f"FACTORCON_QUALIFICATION_JOB={plan['qualification_job']}"
        )
        p09_input = root / OLD_OPERATIONS / "P09-input.json"
        p09_command = [
            "sbatch", "--parsable", "--job-name=fc-P09-quota-retry",
            f"--output={operations}/P09-%A_%a.log",
            f"--export={common},FACTORCON_STAGE=P09,FACTORCON_INPUT={p09_input},FACTORCON_INPUT_SHA256={hash_file(p09_input)}",
            f"--array={','.join(map(str, pending))}%{plan['retry_concurrency']}",
            "--no-requeue", str(analysis / "scripts/alliance/masked_lane.sbatch"),
        ]
        retry_job = submit_one(operations / "P09-retry.json", p09_command)
        original_p10 = load_structured(root / OLD_OPERATIONS / "P10-input.json")
        p10_input = operations / "P10-input.json"
        reconciled = build_reconciled_p10(original_p10, pending, retry_job)
        if p10_input.exists():
            if load_structured(p10_input) != reconciled:
                raise ValueError("reconciled P10 graph changed")
        else:
            atomic_write_json(p10_input, reconciled)
        dependency = (
            "afterok:21744873,afterany:21744875:21744876:"
            f"{plan['original_p09_job']}:{retry_job}"
        )
        p10_command = [
            "sbatch", "--parsable", "--job-name=fc-P10-quota-reconciled",
            f"--output={operations}/P10-%j.log", f"--dependency={dependency}",
            f"--export={common},FACTORCON_STAGE=P10,FACTORCON_INPUT={p10_input},FACTORCON_INPUT_SHA256={hash_file(p10_input)}",
            str(analysis / "scripts/alliance/masked_lane.sbatch"),
        ]
        p10_job = submit_one(operations / "P10-reconciled.json", p10_command)
        receipt = {
            "status": "SUBMITTED", "source_release": str(source),
            "analysis_release": str(analysis), "plan_sha256": hash_file(source / PLAN),
            "old_p09_job": plan["original_p09_job"], "retry_p09_job": retry_job,
            "original_p10_job": plan["original_p10_job"], "reconciled_p10_job": p10_job,
            "retry_replicates": list(pending), "scientific_gate": None,
        }
        atomic_write_json(operations / "dispatch.json", receipt)
        return receipt


def main() -> int:
    """Run a read-only dry run or dispatch within the verified personal run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(dispatch(args.root, Path(__file__).resolve().parents[2], dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
