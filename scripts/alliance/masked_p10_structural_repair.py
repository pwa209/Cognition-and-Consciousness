"""Preserve the original P09/P10 and repair only structurally invalid bootstrap draws.

The replacement percentile distribution is conditional on at least three distinct
participant groups per family. No model score, direction, or numerical fit outcome
determines which original draws are retried.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from downstream_phase import read_predecessor
from submit_empirical import submit_one

from factorcon.alliance import (
    ScratchQuotaGuard,
    read_personal_quota,
    read_source_record,
    validate_fresh_root,
)
from factorcon.config import load_analysis_spec
from factorcon.pipeline.downstream import (
    evaluation_options,
    report_results,
    retry_structurally_invalid_bootstrap,
)
from factorcon.pipeline.patterns import validate_pattern_inputs
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now

PLAN = "conf/masked_p10_structural_repair_20260928.yaml"
OLD_INPUT = "operations/p09-quota-recovery/2535a9a26423129234e733ba7ae41c0315f6e758/P10-input.json"
POLICY = "conditional_min_three_unique_groups_per_family_v1"
FIRST_RETRY_RELEASE = "42b52abb743b09d1e168843d098bae6a6cbe260c"
FIRST_RETRY_JOB = "21943233"
QUOTA_FAILED_REPLICATE = 914


def checked_plan(root: Path, source: Path) -> dict[str, Any]:
    """Validate the fixed 1,000-ID participant-bootstrap repair, without reading outcomes."""
    plan = load_structured(source / PLAN)
    if (
        plan.get("schema_version") != 1
        or plan.get("root") != str(root)
        or plan.get("analysis_release") != "27ce5d1d4c565b5e5506fb4dce5e0843cd3b8dbe"
        or plan.get("reconciled_input_release") != "2535a9a26423129234e733ba7ae41c0315f6e758"
        or plan.get("original_p10_job") != "21842472"
        or plan.get("original_p06_job") != "21744874"
        or plan.get("seed") != 260830
        or plan.get("requested_replicates") != 1000
        or plan.get("expected_structural_failures") != 113
        or plan.get("retry_concurrency") != 8
        or plan.get("max_redraws_per_replicate") != 1000
        or plan.get("structural_failure_reason")
        != "ValueError: nested evaluation requires >=3 independent groups per family"
        or plan.get("sampling_policy") != POLICY
        or plan.get("scientific_gates") is not False
    ):
        raise ValueError("fixed structural-repair plan identity changed")
    return plan


def verify_release(root: Path, source: Path) -> None:
    """Require a hash-bound authorized source release on personal Rorqual scratch."""
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("source release is not authorized and hash-verified")


def verify_model_compatibility(original: Path, current: Path) -> None:
    """Reject scientific changes while tolerating source-only LF/CRLF conversion.

    Both releases must first pass their independent raw-byte manifest checks. The
    compatibility comparison below covers only Python/YAML text and does not
    relax either release's SHA-256 provenance.
    """
    fixed = (
        "conf/analysis_spec.yaml",
        "conf/downstream_plan.yaml",
        "src/factorcon/config.py",
        "src/factorcon/util.py",
        "src/factorcon/pipeline/patterns.py",
    )
    modules = (
        "src/factorcon/models",
        "src/factorcon/stats",
    )
    files = list(fixed)
    for directory in modules:
        files.extend(
            str(path.relative_to(current)).replace("\\", "/")
            for path in sorted((current / directory).glob("*.py"))
        )
    for name in files:
        before, after = original / name, current / name
        if not before.is_file() or not after.is_file():
            raise ValueError(f"model/score source missing from a verified release: {name}")
        if hash_file(before) == hash_file(after):
            continue
        if before.read_bytes().replace(b"\r\n", b"\n") != after.read_bytes().replace(
            b"\r\n", b"\n"
        ):
            raise ValueError(
                f"model/score code or scientific configuration differs from original P09: {name}"
            )


def scheduler_script(source: Path, operations: Path) -> Path:
    """Use a verified source batch script with the LF line endings Slurm requires."""
    original = source / "scripts/alliance/masked_p10_structural_repair.sbatch"
    if not original.is_file():
        raise ValueError("verified source is missing the P10 batch script")
    normalized = original.read_bytes().replace(b"\r\n", b"\n")
    path = operations / "masked_p10_structural_repair.sbatch"
    if path.exists():
        if path.read_bytes() != normalized:
            raise ValueError("existing P10 scheduler script differs from verified source")
    else:
        with path.open("xb") as handle:
            handle.write(normalized)
    return path


def original_evidence(
    root: Path, plan: dict[str, Any]
) -> tuple[Path, str, dict[str, Any], tuple[int, ...]]:
    """Identify structural failures from the hash-bound original report, never scores.

    IDs are bootstrap replicate indices. The independent unit is a participant;
    this audit does not reinterpret model scores or exclude unfavorable results.
    """
    original = root / "releases" / plan["analysis_release"] / "source"
    graph_path = root / OLD_INPUT
    graph = load_structured(graph_path)
    if graph.get("stage") != "P10" or len(graph.get("results", [])) != 1002:
        raise ValueError("original reconciled graph identity changed")
    p06 = read_predecessor(
        root,
        root / "analysis/downstream/P06" / plan["original_p06_job"] / "status.json",
        original,
        load_structured(
            root / "analysis/downstream/P06" / plan["original_p06_job"] / "status.json"
        )["campaign_sha256"],
        "P06",
    )
    campaign_hash = p06["campaign_sha256"]
    old_report = root / "analysis/downstream/P10" / plan["original_p10_job"] / "status.json"
    read_predecessor(root, old_report, original, campaign_hash, "P10")
    report = load_structured(old_report.parent / "result.json")
    rows = report.get("bootstrap_coverage")
    if not isinstance(rows, list) or len(rows) != 1000:
        raise ValueError("original report lacks all 1,000 bootstrap statuses")
    by_id = {row.get("replicate"): row for row in rows}
    if set(by_id) != set(range(1000)) or len(by_id) != len(rows):
        raise ValueError("original report has duplicate or missing replicate IDs")
    failed = tuple(sorted(i for i, row in by_id.items() if row.get("status") == "failed"))
    if (
        len(failed) != plan["expected_structural_failures"]
        or any(by_id[i].get("reason") != plan["structural_failure_reason"] for i in failed)
        or any(row.get("status") != "completed" for i, row in by_id.items() if i not in failed)
    ):
        raise ValueError("nonstructural or changed original bootstrap failures")
    p09_rows = [row for row in graph["results"] if row.get("phase") == "P09"]
    if len(p09_rows) != 1000 or {row.get("replicate") for row in p09_rows} != set(range(1000)):
        raise ValueError("original graph does not cover unique 1,000 replicate IDs")
    return original, campaign_hash, graph, failed


def repaired_graph(
    original: dict[str, Any],
    failed: tuple[int, ...],
    retry_job: str,
    old_source: Path,
    new_source: Path,
) -> dict[str, Any]:
    """Redirect only structural-failure IDs to new attempts; preserve all other paths."""
    if not retry_job.isdigit() or len(failed) != 113 or len(set(failed)) != 113:
        raise ValueError("113 unique structural IDs and numeric Slurm job required")
    rows = []
    for row in original["results"]:
        updated = {**row, "source_release": str(old_source)}
        if row["phase"] == "P09" and row["replicate"] in failed:
            updated["original_status"] = row["status"]
            updated["status"] = (
                f"analysis/downstream/P09/{retry_job}-{row['replicate']}/status.json"
            )
            updated["source_release"] = str(new_source)
        rows.append(updated)
    return {
        "schema_version": 1,
        "stage": "P10_STRUCTURAL_REPAIR",
        "families": ["masked_content_fmri"],
        "results": rows,
        "structural_retry_ids": list(failed),
        "sampling_policy": POLICY,
        "original_p10_job": "21842472",
        "scientific_gate": None,
    }


def technically_completed_graph(
    original: dict[str, Any],
    failed: tuple[int, ...],
    original_source: Path,
    first_retry_source: Path,
    replacement_job: str,
) -> dict[str, Any]:
    """Replace only the quota-failed attempt, never the original bootstrap draw."""
    if not replacement_job.isdigit() or replacement_job == FIRST_RETRY_JOB:
        raise ValueError("a new numeric technical-retry job is required")
    graph = repaired_graph(
        original, failed, FIRST_RETRY_JOB, original_source, first_retry_source
    )
    matches = [
        row for row in graph["results"]
        if row.get("phase") == "P09" and row.get("replicate") == QUOTA_FAILED_REPLICATE
    ]
    if len(matches) != 1 or QUOTA_FAILED_REPLICATE not in failed:
        raise ValueError("quota-failed replicate is not a unique structural retry")
    matches[0]["status"] = (
        f"analysis/downstream/P09/{replacement_job}-{QUOTA_FAILED_REPLICATE}/status.json"
    )
    graph["retry_job"] = FIRST_RETRY_JOB
    graph["technical_retry_overrides"] = {str(QUOTA_FAILED_REPLICATE): replacement_job}
    return graph


def run_retry(
    root: Path, source: Path, input_path: Path, replicate: int, job: str
) -> dict[str, Any]:
    """Write one fresh P09 attempt for an originally invalid participant bootstrap draw."""
    plan = checked_plan(root, source)
    info = load_structured(input_path)
    if info.get("stage") != "P09_STRUCTURAL_RETRY" or replicate not in info["failed_ids"]:
        raise ValueError("replicate is not one of the recorded structural failures")
    original, campaign_hash, graph, failed = original_evidence(root, plan)
    verify_model_compatibility(original, source)
    if tuple(info["failed_ids"]) != failed or info["original_graph_sha256"] != hash_file(
        root / OLD_INPUT
    ):
        raise ValueError("repair input differs from original graph or failed-ID audit")
    old_row = next(
        row
        for row in graph["results"]
        if row.get("phase") == "P09" and row.get("replicate") == replicate
    )
    old_status = root / old_row["status"]
    read_predecessor(root, old_status, original, campaign_hash, "P09")
    old_result = load_structured(old_status.parent / "result.json")
    if (
        old_result.get("replicate") != replicate
        or old_result.get("seed") != plan["seed"]
        or old_result.get("status") != "failed"
        or old_result.get("reason") != plan["structural_failure_reason"]
    ):
        raise ValueError("original per-replicate failure identity changed")
    p06_status = root / "analysis/downstream/P06" / plan["original_p06_job"] / "status.json"
    p06 = read_predecessor(root, p06_status, original, campaign_hash, "P06")
    files = [p06_status.parent / name for name in p06["pattern_files"]]
    datasets, _ = validate_pattern_inputs(
        files, original / "conf/analysis_spec.yaml", mode="within"
    )
    spec = load_analysis_spec(original / "conf/analysis_spec.yaml")
    attempt = root / "analysis/downstream/P09" / f"{job}-{replicate}"
    attempt.mkdir(parents=True, exist_ok=False)
    details: dict[str, Any] = {
        "phase": "P09",
        "status": "RUNNING",
        "source_release": str(source),
        "original_source_release": str(original),
        "campaign_sha256": campaign_hash,
        "replicate": replicate,
        "original_status": str(old_status),
        "original_result_sha256": hash_file(old_status.parent / "result.json"),
        "sampling_policy": POLICY,
        "started_utc": utc_now(),
        "scientific_gate": None,
    }

    def state() -> None:
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)

    state()
    previous = signal.getsignal(signal.SIGTERM)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler/user signal {signum}")

    signal.signal(signal.SIGTERM, stop)
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        result = retry_structurally_invalid_bootstrap(
            datasets,
            replicate=replicate,
            seed=plan["seed"],
            options=evaluation_options(spec, mode="within", seed=plan["seed"]),
            original_multiplicities=old_result["multiplicities"],
            max_redraws=plan["max_redraws_per_replicate"],
        )
        atomic_write_json(attempt / "result.json", result)
        details.update(
            status="SUCCESS",
            ended_utc=utc_now(),
            outputs={"result.json": hash_file(attempt / "result.json")},
            draw_attempt=result.get("draw_attempt"),
            result_status=result["status"],
        )
        state()
        return {"status": "SUCCESS", "replicate": replicate, "result_status": result["status"]}
    except BaseException as exc:
        details.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        state()
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)


def run_report(root: Path, source: Path, input_path: Path, job: str) -> dict[str, Any]:
    """Report all 1,000 participant draws, including original structural failures.

    Scores are paired nats per scored dimension. Old and new release identities
    are checked independently; no model direction selects a result path. The
    percentile interval is explicitly conditional on the nested estimator being
    structurally defined for each resampled family.
    """
    plan = checked_plan(root, source)
    original, campaign_hash, original_graph, failed = original_evidence(root, plan)
    graph = load_structured(input_path)
    retry_job = graph.get("retry_job")
    if "technical_retry_overrides" in graph:
        first_retry_source = root / "releases" / FIRST_RETRY_RELEASE / "source"
        verify_release(root, first_retry_source)
        verify_model_compatibility(original, source)
        if retry_job != FIRST_RETRY_JOB or set(graph["technical_retry_overrides"]) != {
            str(QUOTA_FAILED_REPLICATE)
        }:
            raise ValueError("unexpected technical-retry mapping")
        replacement_job = graph["technical_retry_overrides"][str(QUOTA_FAILED_REPLICATE)]
        expected = technically_completed_graph(
            original_graph, failed, original, first_retry_source, replacement_job
        )
    else:
        expected = repaired_graph(original_graph, failed, retry_job, original, source)
        expected["retry_job"] = retry_job
    expected["original_graph_sha256"] = hash_file(root / OLD_INPUT)
    if graph != expected:
        raise ValueError("new P10 input differs from fixed source/ID mapping")
    attempt = root / "analysis/downstream/P10" / job
    attempt.mkdir(parents=True, exist_ok=False)
    details: dict[str, Any] = {
        "phase": "P10",
        "status": "RUNNING",
        "source_release": str(source),
        "original_source_release": str(original),
        "campaign_sha256": campaign_hash,
        "sampling_policy": POLICY,
        "original_p10_job": plan["original_p10_job"],
        "submission_graph_sha256": hash_file(input_path),
        "started_utc": utc_now(),
        "scientific_gate": None,
    }

    def state() -> None:
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)

    state()
    previous = signal.getsignal(signal.SIGTERM)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler/user signal {signum}")

    signal.signal(signal.SIGTERM, stop)
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        evaluations: dict[str, dict[str, Any]] = {}
        bootstraps: list[dict[str, Any]] = []
        coverage: list[dict[str, Any]] = []
        for entry in graph["results"]:
            producer = Path(entry["source_release"])
            status = ensure_within(root / "analysis/downstream", root / entry["status"])
            row: dict[str, Any] = {"phase": entry["phase"], "status_file": entry["status"]}
            try:
                read_predecessor(root, status, producer, campaign_hash, entry["phase"])
                result_path = status.parent / "result.json"
                payload = load_structured(result_path)
                row.update(status="SUCCESS", result_sha256=hash_file(result_path))
                if entry["phase"] in {"P07", "P08"}:
                    if payload.get("status") == "not_applicable":
                        row.update(status="NOT_APPLICABLE", reason=payload["reason"])
                    else:
                        evaluations[payload["mode"]] = payload
                else:
                    if payload["replicate"] != entry["replicate"]:
                        raise ValueError("bootstrap replicate identity mismatch")
                    if entry["replicate"] in failed:
                        if (
                            payload.get("sampling_policy") != POLICY
                            or payload.get("draw_attempt", 0) < 1
                            or payload.get("original_multiplicities") is None
                        ):
                            raise ValueError("structural redraw provenance missing")
                        old_status = root / entry["original_status"]
                        read_predecessor(root, old_status, original, campaign_hash, "P09")
                        old_payload = load_structured(old_status.parent / "result.json")
                        if payload["original_multiplicities"] != old_payload["multiplicities"]:
                            raise ValueError("structural redraw changed the original draw identity")
                    elif payload.get("status") != "completed":
                        raise ValueError("an original completed draw is no longer completed")
                    bootstraps.append(
                        {
                            k: payload[k]
                            for k in ("replicate", "status", "scores", "reason")
                            if k in payload
                        }
                    )
            except (OSError, ValueError, KeyError, TypeError) as exc:
                row.update(status="UNAVAILABLE", reason=f"{type(exc).__name__}: {exc}")
            coverage.append(row)
        design = {
            "name": POLICY,
            "conditioning_event": "at_least_three_distinct_participant_groups_per_family",
            "original_draws": 1000,
            "original_structural_failures_preserved": len(failed),
            "initially_estimable_draws_preserved": 1000 - len(failed),
            "redrawn_replicate_ids": list(failed),
            "unconditional_interval": False,
            "small_group_coverage_validated": False,
            "original_p10_job": plan["original_p10_job"],
        }
        if "technical_retry_overrides" in graph:
            design["technical_retry_overrides"] = graph["technical_retry_overrides"]
            design["first_retry_job"] = FIRST_RETRY_JOB
        result = report_results(
            attempt,
            families=tuple(graph["families"]),
            evaluations=evaluations,
            bootstrap=bootstraps,
            requested_replicates=plan["requested_replicates"],
            coverage=coverage,
            bootstrap_design=design,
        )
        atomic_write_json(attempt / "result.json", result)
        names = ("result.json", "summary.json", "scores.tsv", "candidate-audits.json")
        details.update(
            status="SUCCESS",
            ended_utc=utc_now(),
            outputs={name: hash_file(attempt / name) for name in names},
            complete_replicates={
                contrast: entry["complete_replicates"]
                for contrast, entry in result["intervals"].items()
            },
        )
        state()
        return {"status": "SUCCESS", "attempt": str(attempt), "coverage": len(coverage)}
    except BaseException as exc:
        details.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        state()
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)


def dispatch(root: Path, source: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Submit only 113 structural redraws and their new conditional P10 report.

    This is a scheduler/provenance repair, not a result-direction stopping rule.
    The original 1,000 attempts, P10 report, and scientific specifications remain.
    """
    import fcntl

    root = validate_fresh_root(root)
    verify_release(root, source)
    plan = checked_plan(root, source)
    original, _, graph, failed = original_evidence(root, plan)
    verify_release(root, original)
    verify_model_compatibility(original, source)
    for replicate in failed:
        row = next(
            item
            for item in graph["results"]
            if item.get("phase") == "P09" and item.get("replicate") == replicate
        )
        status = root / row["status"]
        old = load_structured(status.parent / "result.json")
        if (
            old.get("replicate") != replicate
            or old.get("seed") != plan["seed"]
            or old.get("status") != "failed"
            or old.get("reason") != plan["structural_failure_reason"]
        ):
            raise ValueError("original failed P09 result identity changed")
    quota = read_personal_quota()
    if (
        quota.limit_bytes - quota.used_bytes <= 500_000_000_000
        or quota.limit_files - quota.used_files <= 50_000
    ):
        raise ValueError("personal scratch reserve insufficient")
    if dry_run:
        return {
            "dry_run": True,
            "replicate_count": len(failed),
            "parallel": plan["retry_concurrency"],
        }
    operations = root / "operations/p10-structural-repair" / source.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "dispatch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        repair_input = operations / "P09-input.json"
        value = {
            "stage": "P09_STRUCTURAL_RETRY",
            "failed_ids": list(failed),
            "original_graph_sha256": hash_file(root / OLD_INPUT),
            "sampling_policy": POLICY,
            "scientific_gate": None,
        }
        if repair_input.exists():
            if load_structured(repair_input) != value:
                raise ValueError("existing P09 repair input changed")
        else:
            atomic_write_json(repair_input, value)
        common = f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source}"
        script = scheduler_script(source, operations)
        p09 = [
            "sbatch",
            "--parsable",
            "--job-name=fc-P09-structural-redraw",
            f"--output={operations}/P09-%A_%a.log",
            f"--export={common},FACTORCON_REPAIR_STAGE=P09,FACTORCON_REPAIR_INPUT={repair_input},FACTORCON_REPAIR_INPUT_SHA256={hash_file(repair_input)}",
            f"--array={','.join(map(str, failed))}%{plan['retry_concurrency']}",
            "--no-requeue",
            str(script),
        ]
        test = subprocess.run(
            ["sbatch", "--test-only", *p09[1:]], capture_output=True, text=True, timeout=30
        )
        if test.returncode:
            raise ValueError(f"P09 retry scheduler test failed: {test.stderr.strip()}")
        retry_job = submit_one(operations / "P09.json", p09)
        p10_input = operations / "P10-input.json"
        repaired = repaired_graph(graph, failed, retry_job, original, source)
        repaired["retry_job"] = retry_job
        repaired["original_graph_sha256"] = hash_file(root / OLD_INPUT)
        if p10_input.exists():
            if load_structured(p10_input) != repaired:
                raise ValueError("existing P10 repair graph changed")
        else:
            atomic_write_json(p10_input, repaired)
        p10 = [
            "sbatch",
            "--parsable",
            "--job-name=fc-P10-structural-report",
            f"--output={operations}/P10-%j.log",
            f"--dependency=afterany:{retry_job}",
            f"--export={common},FACTORCON_REPAIR_STAGE=P10,FACTORCON_REPAIR_INPUT={p10_input},FACTORCON_REPAIR_INPUT_SHA256={hash_file(p10_input)}",
            str(script),
        ]
        test = subprocess.run(
            ["sbatch", "--test-only", *p10[1:]], capture_output=True, text=True, timeout=30
        )
        if test.returncode:
            raise ValueError(f"P10 report scheduler test failed: {test.stderr.strip()}")
        report_job = submit_one(operations / "P10.json", p10)
        receipt = {
            "status": "SUBMITTED",
            "source_release": str(source),
            "old_p10_job": plan["original_p10_job"],
            "retry_p09_job": retry_job,
            "new_p10_job": report_job,
            "structural_retry_ids": list(failed),
            "sampling_policy": POLICY,
            "scientific_gate": None,
        }
        atomic_write_json(operations / "dispatch.json", receipt)
        return receipt


def dispatch_technical_completion(
    root: Path, source: Path, *, dry_run: bool = False
) -> dict[str, Any]:
    """Recompute only quota-failed ID 914, then report the fixed 1,000-ID graph.

    The first 112 structural redraws and all 887 original scored draws stay at
    their existing, independently verified paths. No observed score selects an
    attempt. A new Slurm identity preserves the failed first retry and its log.
    """
    import fcntl

    root = validate_fresh_root(root)
    verify_release(root, source)
    plan = checked_plan(root, source)
    original, campaign_hash, original_graph, failed = original_evidence(root, plan)
    verify_release(root, original)
    verify_model_compatibility(original, source)
    first_source = root / "releases" / FIRST_RETRY_RELEASE / "source"
    verify_release(root, first_source)
    verify_model_compatibility(original, first_source)
    first_operations = root / "operations/p10-structural-repair" / FIRST_RETRY_RELEASE
    first_p09_input = first_operations / "P09-input.json"
    p09_info = load_structured(first_p09_input)
    if (
        p09_info.get("stage") != "P09_STRUCTURAL_RETRY"
        or tuple(p09_info.get("failed_ids", ())) != failed
        or p09_info.get("original_graph_sha256") != hash_file(root / OLD_INPUT)
    ):
        raise ValueError("first structural-redraw input changed")
    expected_first = repaired_graph(
        original_graph, failed, FIRST_RETRY_JOB, original, first_source
    )
    expected_first["retry_job"] = FIRST_RETRY_JOB
    expected_first["original_graph_sha256"] = hash_file(root / OLD_INPUT)
    if load_structured(first_operations / "P10-input.json") != expected_first:
        raise ValueError("first structural-report mapping changed")
    for replicate in failed:
        status = root / "analysis/downstream/P09" / f"{FIRST_RETRY_JOB}-{replicate}" / "status.json"
        if replicate == QUOTA_FAILED_REPLICATE:
            stale = load_structured(status)
            if stale.get("status") not in {"RUNNING", "FAILED"} or (
                status.parent / "result.json"
            ).exists():
                raise ValueError("quota-failed attempt unexpectedly has a result")
            continue
        read_predecessor(root, status, first_source, campaign_hash, "P09")
        if load_structured(status.parent / "result.json").get("status") != "completed":
            raise ValueError(f"structural redraw {replicate} is not scored")
    old_log = first_operations / f"P09-{FIRST_RETRY_JOB}_{QUOTA_FAILED_REPLICATE}.log"
    if "[Errno 122] Disk quota exceeded" not in old_log.read_text(errors="replace"):
        raise ValueError("exact quota-failure evidence missing")
    states = subprocess.run(
        [
            "sacct", "-n", "-P", "-j", f"{FIRST_RETRY_JOB}_{QUOTA_FAILED_REPLICATE}",
            "--format=State",
        ], capture_output=True, text=True, check=True, timeout=30,
    ).stdout.splitlines()
    if not states or states[0].split("|")[0].split()[0] != "FAILED":
        raise ValueError("first technical-failure task is not terminal FAILED")
    quota = read_personal_quota()
    free_files = quota.limit_files - quota.used_files
    free_bytes = quota.limit_bytes - quota.used_bytes
    if dry_run:
        return {
            "dry_run": True,
            "completed_structural_redraws": len(failed) - 1,
            "technical_retry_replicate": QUOTA_FAILED_REPLICATE,
            "free_files": free_files,
            "free_bytes": free_bytes,
        }
    if free_files <= 50_000 or free_bytes <= 500_000_000_000:
        raise ValueError("personal scratch reserve insufficient for technical completion")
    operations = root / "operations/p10-technical-completion" / source.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "dispatch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        first_script = first_operations / "masked_p10_structural_repair.sbatch"
        if first_script.read_bytes() != (
            first_source / "scripts/alliance/masked_p10_structural_repair.sbatch"
        ).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError("first retry batch script differs from verified source")
        new_script = scheduler_script(source, operations)
        first_common = f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={first_source}"
        p09 = [
            "sbatch", "--parsable", "--job-name=fc-P09-quota-failed-914",
            f"--output={operations}/P09-%A_%a.log",
            f"--export={first_common},FACTORCON_REPAIR_STAGE=P09,"
            f"FACTORCON_REPAIR_INPUT={first_p09_input},"
            f"FACTORCON_REPAIR_INPUT_SHA256={hash_file(first_p09_input)}",
            f"--array={QUOTA_FAILED_REPLICATE}", "--no-requeue", str(first_script),
        ]
        test = subprocess.run(
            ["sbatch", "--test-only", *p09[1:]], capture_output=True, text=True, timeout=30
        )
        if test.returncode:
            raise ValueError(f"P09 technical retry scheduler test failed: {test.stderr.strip()}")
        replacement_job = submit_one(operations / "P09.json", p09)
        p10_input = operations / "P10-input.json"
        graph = technically_completed_graph(
            original_graph, failed, original, first_source, replacement_job
        )
        graph["original_graph_sha256"] = hash_file(root / OLD_INPUT)
        if p10_input.exists():
            if load_structured(p10_input) != graph:
                raise ValueError("existing technical-completion graph changed")
        else:
            atomic_write_json(p10_input, graph)
        common = f"ALL,FACTORCON_ALLIANCE_ROOT={root},FACTORCON_RELEASE={source}"
        p10 = [
            "sbatch", "--parsable", "--job-name=fc-P10-conditional-completion",
            f"--output={operations}/P10-%j.log",
            f"--dependency=afterany:{replacement_job}",
            f"--export={common},FACTORCON_REPAIR_STAGE=P10,"
            f"FACTORCON_REPAIR_INPUT={p10_input},"
            f"FACTORCON_REPAIR_INPUT_SHA256={hash_file(p10_input)}",
            str(new_script),
        ]
        test = subprocess.run(
            ["sbatch", "--test-only", *p10[1:]], capture_output=True, text=True, timeout=30
        )
        if test.returncode:
            raise ValueError(f"P10 completion scheduler test failed: {test.stderr.strip()}")
        report_job = submit_one(operations / "P10.json", p10)
        receipt = {
            "status": "SUBMITTED",
            "source_release": str(source),
            "first_retry_job": FIRST_RETRY_JOB,
            "quota_failed_replicate": QUOTA_FAILED_REPLICATE,
            "replacement_p09_job": replacement_job,
            "conditional_p10_job": report_job,
            "sampling_policy": POLICY,
            "scientific_gate": None,
        }
        atomic_write_json(operations / "dispatch.json", receipt)
        return receipt


def main() -> int:
    """Run one immutable cluster attempt or submit the fixed repair graph."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=("retry", "report", "dispatch", "dispatch-technical"), required=True
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    if args.mode == "dispatch":
        result = dispatch(root, source, dry_run=args.dry_run)
    elif args.mode == "dispatch-technical":
        result = dispatch_technical_completion(root, source, dry_run=args.dry_run)
    else:
        verify_release(root, source)
        if args.input is None or args.input_sha256 is None:
            raise ValueError("immutable input and SHA-256 required")
        ensure_within(root, args.input)
        if hash_file(args.input) != args.input_sha256:
            raise ValueError("repair input bytes changed")
        job = os.environ.get("SLURM_ARRAY_JOB_ID", os.environ.get("SLURM_JOB_ID", ""))
        if not job.isdigit():
            raise ValueError("numeric Slurm job identity required")
        if args.mode == "retry":
            replicate = int(os.environ["SLURM_ARRAY_TASK_ID"])
            result = run_retry(root, source, args.input, replicate, job)
        else:
            result = run_report(root, source, args.input, job)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
