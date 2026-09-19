"""Submit actual raw preprocessing and disjoint report calibration, not P06 placeholders."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from masked_neural_phase import run_phase, runtime
from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.pipeline.masked_neural import validate_plan
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def submit_graph(
    root: Path, source: Path, operations: Path, p03: Path, producer: Path
) -> dict[str, Any]:
    """Submit a technical dependency graph using durable no-duplicate receipts.

    One subject is a technical pilot; its successful preprocessing allows remaining
    subjects. No effect size/report result is used in dependencies or continuation.
    """
    common = f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source}"
    jobs = {}
    jobs["qualification"] = submit_one(
        operations / "qualification.json",
        [
            "sbatch",
            "--parsable",
            f"--output={operations}/qualification-%j.log",
            f"--export={common},FACTORCON_PYTHON_MODULE=python/3.12.4",
            str(source / "scripts/alliance/qualify.sbatch"),
        ],
    )
    env = (
        f"{common},FACTORCON_QUALIFICATION_JOB={jobs['qualification']},"
        f"FACTORCON_P03={p03},FACTORCON_P03_SOURCE={producer}"
    )

    def submit(name: str, phase: str, dependency: str, extra: list[str], prepared: str = "") -> str:
        return submit_one(
            operations / (name + ".json"),
            [
                "sbatch",
                "--parsable",
                f"--job-name=fc-masked-{name}",
                f"--output={operations}/{name}-%A_%a.log",
                f"--dependency=afterok:{dependency}",
                "--kill-on-invalid-dep=yes",
                *extra,
                f"--export={env},FACTORCON_PHASE={phase}{prepared}",
                str(source / "scripts/alliance/masked_neural_phase.sbatch"),
            ],
        )

    jobs["prepare"] = submit("prepare", "PREPARE", jobs["qualification"], ["--time=01:00:00"])
    prepared = (
        f",FACTORCON_PREPARED={root}/analysis/masked-neural/PREPARE/{jobs['prepare']}/status.json"
    )
    jobs["calibrate"] = submit(
        "calibrate", "CALIBRATE", jobs["prepare"], ["--time=24:00:00"], prepared
    )
    resources = ["--cpus-per-task=8", "--mem=64G", "--time=5-00:00:00"]
    jobs["preprocess-pilot"] = submit(
        "preprocess-pilot", "PREPROCESS", jobs["prepare"], resources, prepared
    )
    jobs["preprocess-remaining"] = submit(
        "preprocess-remaining",
        "PREPROCESS",
        jobs["preprocess-pilot"],
        [*resources, "--array=1-6%2"],
        prepared,
    )
    graph = {
        "jobs": jobs,
        "created_utc": utc_now(),
        "source_release": str(source),
        "scientific_gates": False,
        "scope": "masked_7_subject_raw_fmriprep_and_2_subject_independent_report_calibration",
        "P06_P10_ready": False,
        "independent_neural_noise_calibration_ready": False,
    }
    atomic_write_json(operations / "campaign.json", graph)
    return graph


def main() -> int:
    """Verify owner, personal quota, immutable release and runtime before scheduler writes."""
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--p03", type=Path, required=True)
    parser.add_argument("--producer", type=Path, required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if not record.get("analysis_execution_authorized") or any(
        hash_file(source / p) != h for p, h in record["files"].items()
    ):
        raise ValueError("authorized intact release required")
    plan = load_structured(source / "conf/masked_neural_plan.yaml")
    validate_plan(plan)
    runtime(root, plan)
    run_phase(
        root,
        source,
        "PREPARE",
        root / "analysis/masked-neural/PREPARE/dry-run",
        p03=args.p03,
        producer=args.producer,
        dry_run=True,
    )
    os.umask(0o077)
    operations = root / "operations/masked-neural" / source.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "submission.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ScratchQuotaGuard(operations / "personal-quota.json")(2_000_000_000_000)
        print(json.dumps(submit_graph(root, source, operations, args.p03, args.producer)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
