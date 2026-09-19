"""Qualify downstream code; dispatch empirical jobs only for verified neural bundles."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from submit_empirical import submit_one

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.pipeline.downstream import validate_downstream_plan
from factorcon.pipeline.neural_bundle import load_campaign
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now


def dispatch(
    root: Path,
    source: Path,
    operations: Path,
    *,
    campaign: Path | None = None,
) -> dict[str, Any]:
    """Submit qualification/readiness, or P06 -> P07/P08/P09 -> P10 with durable receipts.

    Caller holds a campaign-level lock. Qualification checks only technical integrity.
    P10 uses afterany so numerical failures remain reportable; scientific scores never
    determine dependency satisfaction. No private campaign means no pretend analyses.
    """
    plan = load_structured(source / "conf/downstream_plan.yaml")
    validate_downstream_plan(plan)
    families: list[str] = []
    if campaign is not None:
        ensure_within(root, campaign)
        data, _ = load_campaign(root, campaign, ridge_fraction=plan["ridge_fraction"])
        families = [d.family for d in data]
        # Preserve the campaign as private immutable submission input, not tracked data.
        snapshot = operations / "campaign-input.json"
        value = load_structured(campaign)
        if snapshot.exists() and load_structured(snapshot) != value:
            raise ValueError("campaign changed; use a new submission identity")
        if not snapshot.exists():
            atomic_write_json(snapshot, value)
        campaign = snapshot
    common = f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source}"
    qualify = submit_one(
        operations / "qualification.json",
        [
            "sbatch",
            "--parsable",
            f"--job-name=fc-downstream-qual-{source.parent.name[:7]}",
            f"--output={operations}/qualification-%j.log",
            f"--export={common},FACTORCON_PYTHON_MODULE=python/3.12.4",
            str(source / "scripts/alliance/qualify.sbatch"),
        ],
    )
    jobs = {"qualification": qualify}
    environment = f"{common},FACTORCON_QUALIFICATION_JOB={qualify}"
    if campaign is None:
        jobs["neural_input_readiness_audit"] = submit_one(
            operations / "readiness.json",
            [
                "sbatch",
                "--parsable",
                "--job-name=fc-neural-input-audit",
                f"--dependency=afterok:{qualify}",
                f"--output={operations}/readiness-%j.log",
                f"--export={environment}",
                str(source / "scripts/alliance/neural_readiness.sbatch"),
            ],
        )
        result = {
            "jobs": jobs,
            "empirical_jobs_submitted": False,
            "reason": "no_verified_empirical_neural_bundle_campaign",
        }
        atomic_write_json(operations / "dispatch.json", result)
        return result
    environment += f",FACTORCON_CAMPAIGN={campaign},FACTORCON_CAMPAIGN_SHA256={hash_file(campaign)}"
    results = []
    graph = operations / "graph.json"

    def submit(phase: str, dependency: str, extra: list[str] | None = None) -> str:
        env = f"{environment},FACTORCON_PHASE={phase}"
        if phase in {"P07", "P08", "P09"}:
            env += f",FACTORCON_P06_STATUS={root}/analysis/downstream/P06/{jobs['P06']}/status.json"
        if phase == "P10":
            env += f",FACTORCON_GRAPH={graph},FACTORCON_GRAPH_SHA256={hash_file(graph)}"
        return submit_one(
            operations / f"{phase}.json",
            [
                "sbatch",
                "--parsable",
                f"--job-name=fc-{phase}-generative",
                f"--dependency={dependency}",
                f"--output={operations}/{phase}-%A_%a.log",
                f"--export={env}",
                *(extra or []),
                str(source / "scripts/alliance/downstream_phase.sbatch"),
            ],
        )

    jobs["P06"] = submit("P06", f"afterok:{qualify}")
    for phase in ("P07", "P08", "P09"):
        extra = (
            [f"--array=0-{plan['bootstrap_replicates'] - 1}%{plan['bootstrap_array_concurrency']}"]
            if phase == "P09"
            else []
        )
        jobs[phase] = submit(phase, f"afterok:{jobs['P06']}", extra)
        if phase == "P09":
            results.extend(
                {
                    "phase": phase,
                    "replicate": i,
                    "status": f"analysis/downstream/{phase}/{jobs[phase]}-{i}/status.json",
                }
                for i in range(plan["bootstrap_replicates"])
            )
        else:
            results.append(
                {"phase": phase, "status": f"analysis/downstream/{phase}/{jobs[phase]}/status.json"}
            )
    graph_data = {
        "schema_version": 1,
        "campaign_sha256": hash_file(campaign),
        "source_release": str(source),
        "families": families,
        "results": results,
    }
    if graph.exists() and load_structured(graph) != graph_data:
        raise ValueError("submission graph changed; reconcile receipts")
    if not graph.exists():
        atomic_write_json(graph, graph_data)
    jobs["P10"] = submit("P10", "afterany:" + ":".join(jobs[p] for p in ("P07", "P08", "P09")))
    result = {
        "jobs": jobs,
        "empirical_jobs_submitted": True,
        "families": families,
        "created_utc": utc_now(),
        "scientific_gate": None,
    }
    atomic_write_json(operations / "dispatch.json", result)
    return result


def main() -> int:
    """Check personal ownership/quota/release; lock durable dispatch, never use /project."""
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--campaign", type=Path)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True:
        raise ValueError("analysis authorization required")
    if any(hash_file(source / p) != h for p, h in record["files"].items()):
        raise ValueError("immutable source release changed")
    identity = hash_file(ensure_within(root, args.campaign)) if args.campaign else "qualification"
    operations = root / "operations/downstream-deployment" / source.parent.name / identity
    os.umask(0o077)
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "submission.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ScratchQuotaGuard(operations / "personal-quota.json")(0)
        print(json.dumps(dispatch(root, source, operations, campaign=args.campaign)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
