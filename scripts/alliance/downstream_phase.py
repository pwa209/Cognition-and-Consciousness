"""Immutable P06-P10 Slurm attempts; all paths stay on study-owned personal scratch."""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path
from typing import Any

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.config import load_analysis_spec
from factorcon.errors import ConfigError
from factorcon.models.pattern_cv import evaluate_patterns
from factorcon.pipeline.downstream import (
    bootstrap_shard,
    evaluation_options,
    report_results,
    validate_downstream_plan,
)
from factorcon.pipeline.neural_bundle import load_campaign, write_pattern_file
from factorcon.pipeline.lofo_contract import (
    audit_exploratory_er_transfer,
    nonestimable_lofo_rows,
)
from factorcon.pipeline.patterns import validate_pattern_inputs
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now


def read_predecessor(
    root: Path,
    status: Path,
    source: Path,
    campaign_hash: str,
    phase: str,
) -> dict[str, Any]:
    """Verify immutable upstream output bytes and campaign identity; no effect-size gate."""
    ensure_within(root / "analysis/downstream", status)
    value = load_structured(status)
    if (
        value.get("status") != "SUCCESS"
        or value.get("phase") != phase
        or value.get("source_release") != str(source)
        or value.get("campaign_sha256") != campaign_hash
    ):
        raise ValueError("upstream phase/source/campaign/status mismatch")
    if "result.json" not in value["outputs"]:
        raise ValueError("upstream result is not hash-bound")
    if phase == "P06" and (
        not value.get("pattern_files") or not set(value["pattern_files"]) <= value["outputs"].keys()
    ):
        raise ValueError("P06 pattern artifacts are not hash-bound")
    for name, digest in value["outputs"].items():
        path = ensure_within(status.parent, status.parent / name)
        if hash_file(path) != digest:
            raise ValueError("upstream output bytes changed")
    return value


def run_phase(
    root: Path,
    source: Path,
    campaign: Path,
    attempt: Path,
    phase: str,
    *,
    p06: Path | None = None,
    graph: Path | None = None,
    replicate: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a versioned empirical stage or read-only dry-run; no data acquisition.

    Retries require new attempt directories and preserve earlier failures. P10 records
    missing/failed upstream artifacts rather than suppressing unfavorable results.
    SIGTERM writes FAILED; SIGKILL must be reconciled against Slurm before retry.
    """
    if phase not in {"P06", "P07", "P08", "P09", "P10"}:
        raise ValueError("unknown downstream phase")
    ensure_within(root, campaign)
    ensure_within(root / "analysis/downstream", attempt)
    plan = load_structured(source / "conf/downstream_plan.yaml")
    validate_downstream_plan(plan)
    spec = load_analysis_spec(source / "conf/analysis_spec.yaml")
    if plan["scientific_gates"] is not False:
        raise ValueError("scientific gates forbidden")
    if phase == "P09" and (
        replicate is None or replicate not in range(plan["bootstrap_replicates"])
    ):
        raise ValueError("P09 replicate outside configured range")
    digest = hash_file(campaign)

    def inputs() -> tuple[Any, Any]:
        if phase == "P06":
            return load_campaign(root, campaign, ridge_fraction=plan["ridge_fraction"])
        if phase == "P10":
            if graph is None:
                raise ValueError("P10 requires immutable submission graph")
            ensure_within(root, graph)
            jobs = load_structured(graph)
            if jobs["campaign_sha256"] != digest or jobs["source_release"] != str(source):
                raise ValueError("graph/campaign/source mismatch")
            return jobs, None
        if p06 is None:
            raise ValueError("P06 predecessor required")
        previous = read_predecessor(root, p06, source, digest, "P06")
        files = [p06.parent / p for p in previous["pattern_files"]]
        datasets, _ = validate_pattern_inputs(
            files, source / "conf/analysis_spec.yaml", mode="within"
        )
        return datasets, tuple(files)

    if dry_run:
        data, _ = inputs()
        return {
            "dry_run": True,
            "phase": phase,
            "campaign_sha256": digest,
            "families": data["families"] if phase == "P10" else [d.family for d in data],
        }
    attempt.mkdir(parents=True, exist_ok=False)
    details: dict[str, Any] = dict(
        status="RUNNING",
        phase=phase,
        source_release=str(source),
        campaign_sha256=digest,
        started_utc=utc_now(),
        scientific_gate=None,
        raw_preprocessing_included=False,
        configuration_sha256={
            p: hash_file(source / "conf" / p)
            for p in ("analysis_spec.yaml", "downstream_plan.yaml")
        },
        replicate=replicate,
    )

    def state() -> None:
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)

    state()
    old = signal.getsignal(signal.SIGTERM)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler/user signal {signum}")

    signal.signal(signal.SIGTERM, stop)
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        data, metadata = inputs()
        if phase == "P06":
            details["pattern_files"] = []
            details["families"] = [d.family for d in data]
            for index, (dataset, meta) in enumerate(zip(data, metadata, strict=True)):
                filename = f"family-{index:02d}.npz"
                write_pattern_file(attempt / filename, dataset, meta)
                details["pattern_files"].append(filename)
            result = {"families": details["families"], "patterns": details["pattern_files"]}
        elif phase == "P10":
            evaluations, bootstraps, coverage = {}, [], []
            details["submission_graph_sha256"] = hash_file(graph)
            for entry in data["results"]:
                status = ensure_within(root / "analysis/downstream", root / entry["status"])
                row = {"phase": entry["phase"], "status_file": entry["status"]}
                try:
                    read_predecessor(root, status, source, digest, entry["phase"])
                    result_file = status.parent / "result.json"
                    payload = load_structured(result_file)
                    row.update(status="SUCCESS", result_sha256=hash_file(result_file))
                    if entry["phase"] in {"P07", "P08"}:
                        if payload.get("status") == "not_applicable":
                            row.update(status="NOT_APPLICABLE", reason=payload["reason"])
                        else:
                            evaluations[payload["mode"]] = payload
                    else:
                        if payload["replicate"] != entry["replicate"]:
                            raise ValueError("bootstrap index mismatch")
                        bootstraps.append(
                            {
                                k: payload[k]
                                for k in ("replicate", "status", "scores", "reason")
                                if k in payload
                            }
                        )
                except (OSError, ValueError, KeyError, ConfigError) as exc:
                    row.update(status="UNAVAILABLE", reason=f"{type(exc).__name__}: {exc}")
                coverage.append(row)
            result = report_results(
                attempt,
                families=tuple(data["families"]),
                evaluations=evaluations,
                bootstrap=bootstraps,
                requested_replicates=plan["bootstrap_replicates"],
                coverage=coverage,
            )
        else:
            details["p06_status"] = str(p06)
            details["p06_status_sha256"] = hash_file(p06)
            options = evaluation_options(
                spec, mode="lofo" if phase == "P08" else "within", seed=plan["seed"]
            )
            if phase == "P09":
                result = bootstrap_shard(
                    data, replicate=replicate, seed=plan["seed"], options=options
                )
            elif phase == "P08" and len(data) < 2:
                result = {"status": "not_applicable", "reason": "LOFO requires >=2 families"}
            elif phase == "P08":
                issues = (
                    audit_exploratory_er_transfer(metadata, data)
                    if all(set(d.names) == {"E", "R"} for d in data)
                    else (
                        "full or mixed-construct cross-family measurement bridge is not independently validated",
                    )
                )
                result = (
                    nonestimable_lofo_rows(data, issues)
                    if issues
                    else evaluate_patterns(data, **options)
                )
                result["estimand"] = (
                    "exploratory_report_evidence_E_R"
                    if all(set(d.names) == {"E", "R"} for d in data)
                    else "full_construct_transfer_not_validated"
                )
            else:
                result = evaluate_patterns(data, **options)
        atomic_write_json(attempt / "result.json", result)
        details.update(
            status="SUCCESS",
            ended_utc=utc_now(),
            outputs={
                p.name: hash_file(p)
                for p in attempt.iterdir()
                if p.is_file()
                and p.name not in {"status.json", "provenance.json", "personal-quota.json"}
            },
        )
        state()
        return {"phase": phase, "status": "SUCCESS", "attempt": str(attempt)}
    except BaseException as exc:
        details.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        state()
        raise
    finally:
        signal.signal(signal.SIGTERM, old)


def main() -> int:
    """Verify personal root/release/Slurm identity then run one immutable stage."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--campaign-sha256", required=True)
    parser.add_argument("--phase", choices=[f"P{i:02d}" for i in range(6, 11)], required=True)
    parser.add_argument("--p06", type=Path)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--graph-sha256")
    parser.add_argument("--replicate", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    ensure_within(root, args.campaign)
    if hash_file(args.campaign) != args.campaign_sha256:
        raise ValueError("submitted campaign bytes changed")
    if args.graph is not None:
        ensure_within(root, args.graph)
        if hash_file(args.graph) != args.graph_sha256:
            raise ValueError("submitted reporting graph bytes changed")
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True:
        raise ValueError("analysis execution authorization required")
    if any(hash_file(source / p) != h for p, h in record["files"].items()):
        raise ValueError("immutable release changed")
    job = os.environ.get("SLURM_ARRAY_JOB_ID", os.environ.get("SLURM_JOB_ID", ""))
    if not args.dry_run and not job.isdigit():
        raise ValueError("numeric Slurm job ID required")
    suffix = f"{job}-{args.replicate}" if args.phase == "P09" else (job or "dry-run")
    os.umask(0o077)
    print(
        json.dumps(
            run_phase(
                root,
                source,
                args.campaign,
                root / "analysis/downstream" / args.phase / suffix,
                args.phase,
                p06=args.p06,
                graph=args.graph,
                replicate=args.replicate,
                dry_run=args.dry_run,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
