"""Archive the failed MRI work tree and requeue the unchanged masked-fMRI lane."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from inode_recovery import terminal, verify_source
from masked_lane_phase import proof
from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.pipeline.downstream import validate_downstream_plan
from factorcon.pipeline.masked_features import validate_feature_plan
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now

PLAN = "mri_quota_recovery_plan.yaml"


def _require_release(root: Path, commit: str) -> Path:
    """Return one intact authorized source release; no data or result files are read."""
    source = root / "releases" / commit / "source"
    verify_source(root, source)
    return source


def validate_recovery(
    root: Path, repair: Path, analysis: Path, batch: Path, plan: dict[str, Any]
) -> dict[str, list[str]]:
    """Prove exact failed/cancelled predecessors and immutable successful inputs.

    Validation uses technical status, source hashes and the fixed cohort only. Neural
    values and model scores never determine retry eligibility.
    """
    if (
        plan["scientific_changes"] is not False
        or plan["scientific_gates"] is not False
        or plan["mri_subject_indices"] != [4, 5, 6]
        or plan["archive_attempts"] != ["21500396-4"]
        or plan["archive_failed_work_before_retry"] is not True
        or plan["archive_successful_work_after_each_mri"] is not True
    ):
        raise ValueError("fixed technical recovery scope required")
    states = {
        job: terminal(job)
        for job in [
            *plan["previous_jobs"].values(),
            plan["failed_bundle_job"],
            plan["failed_p10_job"],
        ]
    }
    expected = {"4": "FAILED", "5": "CANCELLED", "6": "CANCELLED"}
    for index, state in expected.items():
        if states[plan["previous_jobs"][index]] != [state]:
            raise ValueError("MRI predecessor state changed; reconcile before retry")
    if states[plan["failed_bundle_job"]] != ["CANCELLED"]:
        raise ValueError("cancelled bundle predecessor required")
    if states[plan["failed_p10_job"]] != ["FAILED"]:
        raise ValueError("failed premature P10 predecessor required")
    failed = load_structured(
        root / "analysis/masked-neural/PREPROCESS" / plan["archive_attempts"][0] / "status.json"
    )
    if (
        failed.get("status") != "FAILED"
        or failed.get("phase") != "PREPROCESS"
        or failed.get("subject") != "sub-05"
        or not str(failed.get("error", "")).startswith(
            "CapacityError: personal quota service unavailable"
        )
    ):
        raise ValueError("exact transient-quota MRI failure required")
    for index in plan["mri_subject_indices"]:
        for marker in (root / "analysis/masked-neural/PREPROCESS").glob(
            f"*-{index}/status.json"
        ):
            if load_structured(marker).get("status") == "SUCCESS":
                raise ValueError("completed MRI participant must not be resubmitted")
    proof(root, plan["auxiliary"], phase="AUX", source=analysis)
    proof(root, plan["reports"], phase="REPORT", source=analysis)
    for relative in plan["existing_extractions"].values():
        proof(root, relative, phase="EXTRACT", source=analysis)
    qualification = load_structured(
        root / "qualification" / plan["analysis_qualification_job"] / "status.json"
    )
    if (
        qualification.get("status") != "SUCCESS"
        or qualification.get("source_release") != str(analysis)
    ):
        raise ValueError("qualified analysis release required")
    for source in (repair, analysis, batch):
        verify_source(root, source)
    return states


def dispatch(
    root: Path,
    repair: Path,
    analysis: Path,
    batch: Path,
    operations: Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Submit archive, serial MRI retries, feature stages and all P06-P10 jobs.

    All commands use the original scientific/analysis releases. The repair release
    changes quota monitoring and scheduling only. Work trees are checksum-archived
    before or immediately after MRI attempts to bound inode usage.
    """
    deployment = load_structured(analysis / "conf/masked_lane_deployment.yaml")
    features = load_structured(analysis / "conf/masked_feature_plan.yaml")
    downstream = load_structured(analysis / "conf/downstream_plan.yaml")
    validate_feature_plan(features)
    validate_downstream_plan(downstream)
    if downstream["bootstrap_replicates"] != 1000:
        raise ValueError("unchanged 1,000-replicate plan required")
    science = root / "releases" / plan["mri_source"] / "source"
    jobs: dict[str, str] = {}

    def recovery_job(
        name: str,
        mode: str,
        *,
        dependency: str | None = None,
        subject_index: int | None = None,
    ) -> str:
        """Submit one qualified operational recovery job with immutable inputs."""
        environment_name = (
            plan["mri_environment"] if mode == "mri" else plan["qualification_environment"]
        )
        source = science if mode == "mri" else repair
        export = (
            f"ALL,FACTORCON_RELEASE={repair},FACTORCON_MODE={mode},"
            f"FACTORCON_ENVIRONMENT={environment_name},FACTORCON_SCIENCE_SOURCE={source},"
            f"FACTORCON_RECOVERY_PLAN={PLAN}"
        )
        if subject_index is not None:
            export += f",FACTORCON_SUBJECT_INDEX={subject_index}"
        resources = (
            ["--cpus-per-task=8", "--mem=64G", "--time=5-00:00:00"]
            if mode == "mri"
            else ["--cpus-per-task=2", "--mem=8G", "--time=12:00:00"]
            if mode == "archive"
            else ["--cpus-per-task=4", "--mem=16G", "--time=01:00:00"]
        )
        return submit_one(
            operations / f"{name}.json",
            [
                "sbatch",
                "--parsable",
                "--account=def-ptewarie_cpu",
                f"--job-name=fc-qfix-{name}",
                f"--output={operations}/{name}-%A_%a.log",
                "--kill-on-invalid-dep=yes",
                *resources,
                f"--export={export}",
                *([f"--dependency={dependency}"] if dependency else []),
                str(repair / "scripts/alliance/inode_recovery.sbatch"),
            ],
        )

    jobs["qualification"] = recovery_job("qualification", "qualify")
    jobs["archive-failed-work"] = recovery_job(
        "archive-failed-work", "archive", dependency=f"afterok:{jobs['qualification']}"
    )
    previous = jobs["archive-failed-work"]
    for index in plan["mri_subject_indices"]:
        subject = f"sub-0{index + 1}"
        jobs["mri-" + subject] = recovery_job(
            "mri-" + subject,
            "mri",
            dependency=f"afterok:{previous}",
            subject_index=index,
        )
        previous = jobs["mri-" + subject]

    analysis_common = (
        f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={analysis},"
        f"FACTORCON_QUALIFICATION_JOB={plan['analysis_qualification_job']}"
    )

    def lane_job(
        name: str,
        stage: str,
        config: dict[str, Any],
        dependency: str,
        extra: list[str] | None = None,
    ) -> str:
        """Submit one original analysis stage with a hashed future-input graph."""
        value = {**config, "stage": stage}
        input_path = operations / f"{name}-input.json"
        if input_path.exists() and load_structured(input_path) != value:
            raise ValueError("recovery input changed; fresh dispatch required")
        if not input_path.exists():
            atomic_write_json(input_path, value)
        export = (
            f"{analysis_common},FACTORCON_STAGE={stage},FACTORCON_INPUT={input_path},"
            f"FACTORCON_INPUT_SHA256={hash_file(input_path)}"
        )
        return submit_one(
            operations / f"{name}.json",
            [
                "sbatch",
                "--parsable",
                f"--job-name=fc-qfix-{name}",
                f"--output={operations}/{name}-%A_%a.log",
                f"--export={export}",
                f"--dependency={dependency}",
                *(extra or []),
                str(analysis / "scripts/alliance/masked_lane.sbatch"),
            ],
        )

    extraction_status = dict(plan["existing_extractions"])
    for index in plan["mri_subject_indices"]:
        subject = f"sub-0{index + 1}"
        name = "extract-" + subject
        config = {k: deployment[k] for k in ("prepared", "p03", "p03_source")}
        config.update(
            subject=subject,
            auxiliary=plan["auxiliary"],
            preprocessing=(
                f"analysis/masked-neural/PREPROCESS/{jobs['mri-' + subject]}-{index}/status.json"
            ),
        )
        jobs[name] = lane_job(
            name, "EXTRACT", config, f"afterok:{jobs['mri-' + subject]}"
        )
        extraction_status[subject] = (
            f"analysis/masked-lane/EXTRACT/{jobs[name]}/status.json"
        )

    jobs["noise"] = lane_job(
        "noise",
        "NOISE",
        {
            "prepared": deployment["prepared"],
            "extractions": {
                "sub-02": extraction_status["sub-02"],
                "sub-07": extraction_status["sub-07"],
            },
        },
        f"afterok:{jobs['extract-sub-07']}",
    )
    evaluation = ["sub-01", "sub-03", "sub-04", "sub-05", "sub-06"]
    jobs["bundle"] = lane_job(
        "bundle",
        "BUNDLE",
        {
            "prepared": deployment["prepared"],
            "reports": plan["reports"],
            "noise": f"analysis/masked-lane/NOISE/{jobs['noise']}/status.json",
            "extractions": {subject: extraction_status[subject] for subject in evaluation},
        },
        "afterok:"
        + ":".join(
            [jobs["noise"], jobs["extract-sub-05"], jobs["extract-sub-06"]]
        ),
    )
    bundle = f"analysis/masked-lane/BUNDLE/{jobs['bundle']}/status.json"
    jobs["P06"] = lane_job("P06", "P06", {"bundle": bundle}, f"afterok:{jobs['bundle']}")
    p06 = f"analysis/downstream/P06/{jobs['P06']}/status.json"
    for phase in ("P07", "P08"):
        jobs[phase] = lane_job(
            phase,
            phase,
            {"bundle": bundle, "p06": p06},
            f"afterok:{jobs['P06']}",
            ["--time=48:00:00"],
        )

    p09_config = {"stage": "P09", "bundle": bundle, "p06": p06}
    p09_input = operations / "P09-input.json"
    if p09_input.exists() and load_structured(p09_input) != p09_config:
        raise ValueError("P09 recovery input changed; fresh dispatch required")
    if not p09_input.exists():
        atomic_write_json(p09_input, p09_config)
    p09_export = (
        f"{analysis_common},FACTORCON_STAGE=P09,FACTORCON_BATCH_RELEASE={batch},"
        f"FACTORCON_INPUT={p09_input},FACTORCON_INPUT_SHA256={hash_file(p09_input)}"
    )
    jobs["P09"] = submit_one(
        operations / "P09.json",
        [
            "sbatch",
            "--parsable",
            "--job-name=fc-qfix-P09-packed",
            f"--output={operations}/P09-%A_%a.log",
            f"--export={p09_export}",
            f"--dependency=afterok:{jobs['P06']}",
            f"--array=0-{plan['bootstrap_scheduler_tasks'] - 1}%{plan['bootstrap_concurrency']}",
            "--no-requeue",
            str(batch / "scripts/alliance/masked_bootstrap_batch.sbatch"),
        ],
    )
    results = [
        {"phase": phase, "status": f"analysis/downstream/{phase}/{jobs[phase]}/status.json"}
        for phase in ("P07", "P08")
    ]
    results.extend(
        {
            "phase": "P09",
            "replicate": replicate,
            "status": f"analysis/downstream/P09/{jobs['P09']}-{replicate}/status.json",
        }
        for replicate in range(downstream["bootstrap_replicates"])
    )
    jobs["P10"] = lane_job(
        "P10",
        "P10",
        {"bundle": bundle, "results": results},
        f"afterok:{jobs['bundle']},afterany:"
        + ":".join(jobs[phase] for phase in ("P07", "P08", "P09")),
    )
    value = {
        "jobs": jobs,
        "created_utc": utc_now(),
        "repair_source": str(repair),
        "analysis_source": str(analysis),
        "batch_source": str(batch),
        "scientific_changes": False,
        "scientific_gate": None,
        "failed_work_archived_before_retry": True,
        "successful_work_archived_serially": True,
        "P09_replicates": downstream["bootstrap_replicates"],
        "P09_scheduler_tasks": plan["bootstrap_scheduler_tasks"],
        "P08": "not_applicable_single_family",
    }
    atomic_write_json(operations / "dispatch.json", value)
    return value


def main() -> int:
    """Validate live identity, immutable evidence and quota, then dispatch once."""
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    repair = Path(__file__).resolve().parents[2]
    plan = load_structured(repair / "conf" / PLAN)
    record = read_source_record(root, repair)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(repair / relative) != digest for relative, digest in record["files"].items()
    ):
        raise ValueError("authorized immutable repair release required")
    analysis = _require_release(root, plan["analysis_source"])
    batch = _require_release(root, plan["batch_source"])
    operations = root / "operations/mri-quota-recovery" / repair.parent.name
    os.umask(0o077)
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "submission.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        states = validate_recovery(root, repair, analysis, batch, plan)
        live = subprocess.check_output(
            ["squeue", "-h", "-u", "pwa209", "-o", "%i|%j"], text=True, timeout=45
        )
        if any(
            line.partition("|")[2].startswith(("fc-qfix-", "fc-plotfix-", "fc-masked-"))
            for line in live.splitlines()
        ):
            raise ValueError("active related job requires reconciliation; no duplicate")
        ScratchQuotaGuard(
            operations / "submission-quota.json",
            reserve_bytes=plan["live_reserve_bytes"],
            reserve_files=50,
        )(0)
        result = dispatch(root, repair, analysis, batch, operations, plan)
        result["predecessor_states"] = states
        atomic_write_json(operations / "dispatch.json", result)
        print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
