"""Queue the approved initial masked-fMRI lane, binding future artifacts to producer job IDs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from masked_lane_phase import proof
from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.pipeline.downstream import validate_downstream_plan
from factorcon.pipeline.masked_features import validate_feature_plan
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def dispatch(root: Path, source: Path, operations: Path, auxiliary: str) -> dict[str, Any]:
    """Queue qualification, seven extractions, independent noise, bundle and real P06-P10 commands.

    Caller holds an exclusive campaign lock. Dependencies express technical inputs,
    never favorable findings. Future campaigns are verified against BUNDLE job/source
    and output hashes before use. No synthetic input or readiness-only substitute.
    """
    plan = load_structured(source / "conf/masked_lane_deployment.yaml")
    features = load_structured(source / "conf/masked_feature_plan.yaml")
    downstream = load_structured(source / "conf/downstream_plan.yaml")
    validate_feature_plan(features)
    validate_downstream_plan(downstream)
    if plan["scientific_gates"] is not False:
        raise ValueError("no scientific gates allowed")
    prepared = proof(root, plan["prepared"], phase="PREPARE")
    partition = load_structured(prepared / "partition.json")
    if set(plan["preprocessing"]) != set(
        partition["calibration_subjects"] + partition["evaluation_subjects"]
    ):
        raise ValueError("deployment cohort mismatch")
    proof(root, auxiliary, phase="AUX", source=source)
    proof(root, plan["reports"])
    for item in plan["preprocessing"].values():
        if item["pending_job"] is None:
            proof(root, item["status"], phase="PREPROCESS")
        elif not item["pending_job"].isdigit():
            raise ValueError("numeric MRI predecessor job required")
    common = f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source}"
    jobs: dict[str, str] = {}

    def submit(
        name: str,
        stage: str,
        config: dict[str, Any],
        dependency: str | None,
        extra: list[str] | None = None,
    ) -> str:
        input_path = operations / f"{name}-input.json"
        value = {**config, "stage": stage}
        if input_path.exists() and load_structured(input_path) != value:
            raise ValueError("input changed: fresh dispatch identity required")
        if not input_path.exists():
            atomic_write_json(input_path, value)
        environment = (
            f"{common},FACTORCON_STAGE={stage},FACTORCON_INPUT={input_path}"
            f",FACTORCON_INPUT_SHA256={hash_file(input_path)}"
        )
        if stage != "QUALIFY":
            environment += f",FACTORCON_QUALIFICATION_JOB={jobs['qualification']}"
        return submit_one(
            operations / f"{name}.json",
            [
                "sbatch",
                "--parsable",
                f"--job-name=fc-masked-{name}",
                f"--output={operations}/{name}-%A_%a.log",
                f"--export={environment}",
                *([f"--dependency={dependency}"] if dependency else []),
                *(extra or []),
                str(source / "scripts/alliance/masked_lane.sbatch"),
            ],
        )

    jobs["qualification"] = submit("qualification", "QUALIFY", {}, None, ["--time=00:45:00"])
    jobs["reports"] = submit(
        "reports",
        "REPORT",
        {"prepared": plan["prepared"], "auxiliary": auxiliary, "previous_reports": plan["reports"]},
        "afterok:" + jobs["qualification"],
        ["--time=08:00:00"],
    )
    extract_status = {}
    for subject, item in plan["preprocessing"].items():
        name = "extract-" + subject
        config = {k: plan[k] for k in ("prepared", "p03", "p03_source")}
        config.update(subject=subject, auxiliary=auxiliary, preprocessing=item["status"])
        dependency = (
            "afterok:"
            + jobs["qualification"]
            + (":" + item["pending_job"] if item["pending_job"] else "")
        )
        jobs[name] = submit(name, "EXTRACT", config, dependency)
        extract_status[subject] = f"analysis/masked-lane/EXTRACT/{jobs[name]}/status.json"
    calibration = partition["calibration_subjects"]
    jobs["noise"] = submit(
        "noise",
        "NOISE",
        {"prepared": plan["prepared"], "extractions": {s: extract_status[s] for s in calibration}},
        "afterok:" + ":".join(jobs["extract-" + s] for s in calibration),
    )
    jobs["bundle"] = submit(
        "bundle",
        "BUNDLE",
        {
            "prepared": plan["prepared"],
            "reports": f"analysis/masked-lane/REPORT/{jobs['reports']}/status.json",
            "noise": f"analysis/masked-lane/NOISE/{jobs['noise']}/status.json",
            "extractions": {s: extract_status[s] for s in partition["evaluation_subjects"]},
        },
        "afterok:"
        + ":".join(
            [
                jobs["noise"],
                jobs["reports"],
                *[jobs["extract-" + s] for s in partition["evaluation_subjects"]],
            ]
        ),
    )
    bundle = f"analysis/masked-lane/BUNDLE/{jobs['bundle']}/status.json"
    jobs["P06"] = submit("P06", "P06", {"bundle": bundle}, "afterok:" + jobs["bundle"])
    results = []
    for phase in ("P07", "P08", "P09"):
        extra = ["--time=48:00:00"]
        if phase == "P09":
            extra.append(
                f"--array=0-{downstream['bootstrap_replicates'] - 1}"
                f"%{downstream['bootstrap_array_concurrency']}"
            )
        jobs[phase] = submit(
            phase,
            phase,
            {"bundle": bundle, "p06": f"analysis/downstream/P06/{jobs['P06']}/status.json"},
            "afterok:" + jobs["P06"],
            extra,
        )
        if phase == "P09":
            results.extend(
                {
                    "phase": phase,
                    "replicate": i,
                    "status": f"analysis/downstream/{phase}/{jobs[phase]}-{i}/status.json",
                }
                for i in range(downstream["bootstrap_replicates"])
            )
        else:
            results.append(
                {"phase": phase, "status": f"analysis/downstream/{phase}/{jobs[phase]}/status.json"}
            )
    jobs["P10"] = submit(
        "P10",
        "P10",
        {"bundle": bundle, "results": results},
        "afterany:" + ":".join(jobs[p] for p in ("P07", "P08", "P09")),
    )
    result = {
        "jobs": jobs,
        "created_utc": utc_now(),
        "scientific_gate": None,
        "families": ["masked_content_fmri"],
        "P08": "queued_applicability_record_only_single_family",
        "future_campaign_producer": bundle,
        "scope": features["scope"],
        "limitations": features["limitations"],
    }
    atomic_write_json(operations / "dispatch.json", result)
    return result


def main() -> int:
    """Verify live personal quota/ownership/source and serialize idempotent Slurm dispatch."""
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--auxiliary", required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / p) != h for p, h in record["files"].items()
    ):
        raise ValueError("immutable authorized release required")
    operations = root / "operations/masked-lane" / source.parent.name
    os.umask(0o077)
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "submission.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ScratchQuotaGuard(operations / "personal-quota.json")(0)
        print(json.dumps(dispatch(root, source, operations, args.auxiliary)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
