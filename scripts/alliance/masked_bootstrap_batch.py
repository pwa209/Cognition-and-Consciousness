"""Pack unchanged P09 replicates into fewer scheduler tasks; no scientific aggregation."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now


def batch_indices(index: int, *, total: int = 1000, size: int = 20) -> tuple[int, ...]:
    """Map scheduler index to fixed global replicate/seed indices; no observations read."""
    if total != 1000 or size != 20 or index not in range(50):
        raise ValueError("expected one of 50 fixed batches of 20 replicates")
    return tuple(range(index * size, min(total, (index + 1) * size)))


def run_batch(
    root: Path,
    source: Path,
    analysis: Path,
    input_path: Path,
    digest: str,
    attempt: Path,
    index: int,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run original P09 commands sequentially in one batch; atomic failure and immutable restart.

    Numerical/not-estimable results retain their original per-replicate status.
    A technical exception stops only this batch. Retries use a new job/attempt and
    never overwrite completed old replicates. The 1,000 requested seeds are unchanged.
    """
    indices = batch_indices(index)
    ensure_within(root, input_path)
    ensure_within(root / "analysis/masked-lane/BOOTSTRAP_BATCH", attempt)
    if hash_file(input_path) != digest or load_structured(input_path)["stage"] != "P09":
        raise ValueError("immutable P09 input required")
    if dry_run:
        return {"dry_run": True, "replicates": list(indices), "writes": False}
    attempt.mkdir(parents=True, exist_ok=False)
    value = {
        "phase": "P09_BATCH",
        "status": "RUNNING",
        "source_release": str(source),
        "analysis_source_release": str(analysis),
        "started_utc": utc_now(),
        "scientific_gate": None,
        "replicates": list(indices),
        "completed": [],
        "input_sha256": digest,
    }

    def state() -> None:
        for name in ("status.json", "provenance.json"):
            atomic_write_json(attempt / name, value)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    old = signal.signal(signal.SIGTERM, stop)
    state()
    try:
        for replicate in indices:
            env = dict(
                os.environ, SLURM_ARRAY_TASK_ID=str(replicate), PYTHONPATH=str(analysis / "src")
            )
            subprocess.run(
                [
                    sys.executable,
                    "-u",
                    str(analysis / "scripts/alliance/masked_lane_downstream.py"),
                    "--root",
                    str(root),
                    "--input",
                    str(input_path),
                    "--input-sha256",
                    digest,
                ],
                env=env,
                check=True,
            )
            value["completed"].append(replicate)
            state()
        value.update(status="SUCCESS", ended_utc=utc_now())
        state()
        return value
    except BaseException as exc:
        value.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        state()
        raise
    finally:
        signal.signal(signal.SIGTERM, old)


def main() -> int:
    """Verify both immutable releases and the existing analysis qualification before batching."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--qualification-job", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    for release in (source, args.analysis):
        record = read_source_record(root, release)
        if record.get("analysis_execution_authorized") is not True or any(
            hash_file(release / p) != h for p, h in record["files"].items()
        ):
            raise ValueError("authorized immutable batch/analysis releases required")
    if not args.qualification_job.isdigit():
        raise ValueError("numeric qualification job required")
    qualified = load_structured(root / "qualification" / args.qualification_job / "status.json")
    if qualified["status"] != "SUCCESS" or qualified["source_release"] != str(args.analysis):
        raise ValueError("matching successful analysis qualification required")
    job = os.environ["SLURM_ARRAY_JOB_ID"]
    index = int(os.environ["SLURM_ARRAY_TASK_ID"])
    if not job.isdigit():
        raise ValueError("numeric scheduler parent job required")
    os.umask(0o077)
    run_batch(
        root,
        source,
        args.analysis,
        args.input,
        args.input_sha256,
        root / "analysis/masked-lane/BOOTSTRAP_BATCH" / f"{job}-{index}",
        index,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
