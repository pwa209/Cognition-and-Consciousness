"""Queue a fresh masked-fMRI NOISE-to-P10 graph over immutable prior extractions."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from inode_recovery import terminal, verify_source
from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now

PLAN = "masked_noise_recovery_20260924.yaml"


def dispatch(root: Path, source: Path, operations: Path, qualification_job: str) -> dict[str, Any]:
    """Submit immutable, restart-safe Slurm dependencies; no participant outcomes read.

    Paths are personal-scratch receipts. Each stage gets a hashed input and its own
    scheduler job; P09 retains 1,000 replicate identities in 50 packed tasks.
    """
    plan = load_structured(source / "conf" / PLAN)
    if str(root) != plan["root"] or plan["scientific_gates"] is not False:
        raise ValueError("recovery root or no-gate contract mismatch")
    if not qualification_job.isdigit():
        raise ValueError("numeric qualification job required")
    qualified = load_structured(root / "qualification" / qualification_job / "status.json")
    if qualified.get("status") != "SUCCESS" or qualified.get("source_release") != str(source):
        raise ValueError("matching successful release qualification required")
    verify_source(root, source)
    producer = root / plan["extraction_source"]
    batch = root / "releases" / plan["batch_source"] / "source"
    verify_source(root, producer)
    verify_source(root, batch)
    if terminal(plan["failed_noise_job"]) != ["FAILED"]:
        raise ValueError("prior failed NOISE attempt must be terminal")
    previous = load_structured(root / "analysis/masked-lane/NOISE" / plan["failed_noise_job"] / "status.json")
    if previous.get("status") != "FAILED" or "insufficient residual degrees" not in previous.get("error", ""):
        raise ValueError("failed NOISE cause changed; reconcile before retry")
    for subject, relative in (plan["calibration_extractions"] | plan["evaluation_extractions"]).items():
        receipt = load_structured(root / relative)
        if (receipt.get("status"), receipt.get("phase"), receipt.get("configuration", {}).get("subject"), receipt.get("source_release")) != ("SUCCESS", "EXTRACT", subject, str(producer)):
            raise ValueError(f"extraction receipt mismatch: {subject}")
    operations.mkdir(parents=True, exist_ok=True)
    ScratchQuotaGuard(operations / "personal-quota.json")(0)
    common = (
        f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source},"
        f"FACTORCON_QUALIFICATION_JOB={qualification_job}"
    )
    jobs: dict[str, str] = {}

    def lane(name: str, stage: str, config: dict[str, Any], dependency: str | None = None) -> str:
        value = {"stage": stage, **config}
        input_path = operations / f"{name}-input.json"
        if input_path.exists():
            if load_structured(input_path) != value:
                raise ValueError("existing stage input changed; reconcile")
        else:
            atomic_write_json(input_path, value)
        command = [
            "sbatch", "--parsable", f"--job-name=fc-noisefix-{name}",
            f"--output={operations}/{name}-%A_%a.log",
            f"--export={common},FACTORCON_STAGE={stage},FACTORCON_INPUT={input_path},FACTORCON_INPUT_SHA256={hash_file(input_path)}",
        ]
        if dependency:
            command.append(f"--dependency={dependency}")
        if stage in {"P07", "P08"}:
            command.append("--time=48:00:00")
        command.append(str(source / "scripts/alliance/masked_lane.sbatch"))
        return submit_one(operations / f"{name}.json", command)

    jobs["noise"] = lane("noise", "NOISE", {
        "prepared": plan["prepared"], "extraction_source": plan["extraction_source"],
        "extractions": plan["calibration_extractions"],
    })
    jobs["bundle"] = lane("bundle", "BUNDLE", {
        "prepared": plan["prepared"], "reports": plan["reports"],
        "extraction_source": plan["extraction_source"],
        "noise": f"analysis/masked-lane/NOISE/{jobs['noise']}/status.json",
        "extractions": plan["evaluation_extractions"],
    }, f"afterok:{jobs['noise']}")
    bundle = f"analysis/masked-lane/BUNDLE/{jobs['bundle']}/status.json"
    jobs["P06"] = lane("P06", "P06", {"bundle": bundle}, f"afterok:{jobs['bundle']}")
    p06 = f"analysis/downstream/P06/{jobs['P06']}/status.json"
    for phase in ("P07", "P08"):
        jobs[phase] = lane(phase, phase, {"bundle": bundle, "p06": p06}, f"afterok:{jobs['P06']}")
    p09_input = operations / "P09-input.json"
    p09_value = {"stage": "P09", "bundle": bundle, "p06": p06}
    if p09_input.exists():
        if load_structured(p09_input) != p09_value:
            raise ValueError("existing P09 input changed; reconcile")
    else:
        atomic_write_json(p09_input, p09_value)
    jobs["P09"] = submit_one(operations / "P09.json", [
        "sbatch", "--parsable", "--job-name=fc-noisefix-P09-packed",
        f"--output={operations}/P09-%A_%a.log",
        f"--export={common},FACTORCON_STAGE=P09,FACTORCON_BATCH_RELEASE={batch},FACTORCON_INPUT={p09_input},FACTORCON_INPUT_SHA256={hash_file(p09_input)}",
        f"--dependency=afterok:{jobs['P06']}",
        f"--array=0-{plan['bootstrap_scheduler_tasks'] - 1}%{plan['bootstrap_concurrency']}",
        "--no-requeue", str(batch / "scripts/alliance/masked_bootstrap_batch.sbatch"),
    ])
    results = [
        {"phase": phase, "status": f"analysis/downstream/{phase}/{jobs[phase]}/status.json"}
        for phase in ("P07", "P08")
    ]
    results.extend({
        "phase": "P09", "replicate": i,
        "status": f"analysis/downstream/P09/{jobs['P09']}-{i}/status.json",
    } for i in range(plan["bootstrap_replicates"]))
    jobs["P10"] = lane("P10", "P10", {"bundle": bundle, "results": results},
        f"afterok:{jobs['bundle']},afterany:{jobs['P07']}:{jobs['P08']}:{jobs['P09']}")
    result = {"created_utc": utc_now(), "source_release": str(source),
              "extraction_source_release": str(producer), "jobs": jobs,
              "P09_replicates": plan["bootstrap_replicates"],
              "P09_scheduler_tasks": plan["bootstrap_scheduler_tasks"],
              "scientific_gate": None}
    atomic_write_json(operations / "dispatch.json", result)
    return result


def main() -> int:
    """Guard one dispatch with an exclusive personal-scratch operations lock."""
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qualification-job", required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    operations = root / "operations/noise-recovery" / source.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "dispatch.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        print(dispatch(root, source, operations, args.qualification_job))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
