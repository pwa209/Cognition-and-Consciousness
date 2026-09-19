"""Generative P07-P10 execution, bootstrap shards and lossless score reporting."""

from __future__ import annotations

import csv
import io
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.models.generative import PatternData
from factorcon.models.pattern_cv import evaluate_patterns, validate_collection
from factorcon.stats.pattern_bootstrap import paired_pattern_summary
from factorcon.util import atomic_write_json, atomic_write_text


def validate_downstream_plan(plan: dict[str, Any]) -> None:
    """Validate outcome-independent computation settings; no neural data are consulted."""
    if (
        plan.get("schema_version") != 1
        or plan.get("scientific_gates") is not False
        or plan.get("raw_preprocessing_included") is not False
        or type(plan.get("bootstrap_replicates")) is not int
        or plan["bootstrap_replicates"] < 2
        or type(plan.get("bootstrap_array_concurrency")) is not int
        or plan["bootstrap_array_concurrency"] < 1
        or type(plan.get("seed")) is not int
        or plan["seed"] < 0
        or not 0 < plan.get("ridge_fraction", 0) <= 1
    ):
        raise ValueError("invalid downstream configuration or unsupported scientific gate")


def evaluation_options(spec: dict[str, Any], *, mode: str, seed: int) -> dict[str, Any]:
    """Build declared generative fitting options; all tuning stays inside training folds."""
    if mode not in {"within", "lofo"}:
        raise ValueError("within or lofo mode required")
    settings = spec["pattern_evaluation"]
    if settings["implementation"] != "generative_pattern_v1":
        raise ValueError("legacy RDM prototype is not the generative empirical engine")
    return dict(
        mode=mode,
        penalties=tuple(settings["penalties"]),
        interactions=tuple(tuple(i.split(":")) for i in spec["interactions"]),
        shape_options={k: settings[k] for k in ("unitary_rank", "gate_floor", "report_leak")},
        fit_options={
            "starts": settings["optimizer_starts"],
            "max_iter": settings["max_iter"],
            "seed": seed,
        },
    )


def bootstrap_shard(
    datasets: tuple[PatternData, ...],
    *,
    replicate: int,
    seed: int,
    options: dict[str, Any],
) -> dict[str, Any]:
    """Refit one independent-subject bootstrap with fixed conditions/calibration.

    Sampling uses SeedSequence([seed, replicate]); array scheduling order cannot
    change draws. Multiplicities are weights on original IDs, never leaking clones.
    Sparse/failed draws remain explicit; no interval is conditional on success.
    """
    validate_collection(datasets)
    if replicate < 0 or any(d.group_weights is not None for d in datasets):
        raise ValueError("nonnegative replicate and original unweighted groups required")
    rng = np.random.default_rng(np.random.SeedSequence([seed, replicate]))
    sampled, multiplicities = [], {}
    for data in datasets:
        n = len(data.group_ids)
        counts = np.bincount(rng.integers(0, n, n), minlength=n)
        keep = np.flatnonzero(counts)
        multiplicities[data.family] = dict(zip(data.group_ids, counts.tolist(), strict=True))
        sampled.append(replace(data.subset(keep), group_weights=counts[keep].astype(float)))
    result = {"replicate": replicate, "seed": seed, "multiplicities": multiplicities}
    try:
        evaluation = evaluate_patterns(tuple(sampled), **options)
        result.update(
            status="completed",
            evaluation=evaluation,
            scores=paired_pattern_summary(evaluation, tuple(d.family for d in datasets)),
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        result.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
    return result


def report_results(
    output: Path,
    *,
    families: tuple[str, ...],
    evaluations: dict[str, dict[str, Any]],
    bootstrap: list[dict[str, Any]],
    requested_replicates: int,
    coverage: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write auditable per-group nats and paired nats/dimension, retaining every failure.

    Percentile intervals are unadjusted subject-bootstrap intervals at fixed families,
    conditions and external calibration. No p-values/equivalence or manuscript claims
    are fabricated. A successful report may document unsuccessful upstream jobs.
    """
    if requested_replicates < 2 or not families or len(set(families)) != len(families):
        raise ValueError("unique declared families and >=2 requested replicates required")
    indices = [b["replicate"] for b in bootstrap]
    if len(set(indices)) != len(indices) or any(
        i not in range(requested_replicates) for i in indices
    ):
        raise ValueError("duplicate or out-of-range bootstrap replicate")
    rows, summaries = [], {}
    for mode, evaluation in evaluations.items():
        if (
            evaluation.get("implementation") != "generative_pattern_v1"
            or evaluation["mode"] != mode
        ):
            raise ValueError("report accepts only mode-matched generative results")
        seen: set[tuple[str, str, str]] = set()
        models: dict[tuple[str, str], set[str]] = {}
        for row in evaluation["rows"]:
            if row["family"] not in families or row["model"] not in {f"M{i}" for i in range(6)}:
                raise ValueError("undeclared family/model in result")
            status = row["status"]
            if status not in {"scored", "not_estimable", "numerical_or_design_failure"}:
                raise ValueError("unknown candidate result status")
            scores = row.get("scores_nats", [None] * len(row["test_groups"]))
            for group, weight, score in zip(
                row["test_groups"], row["test_group_weights"], scores, strict=True
            ):
                key = (row["family"], group, row["model"])
                if key in seen:
                    raise ValueError("duplicate family/group/model score")
                seen.add(key)
                models.setdefault(key[:2], set()).add(row["model"])
                dims = row["scored_dimensions_per_group"]
                if dims <= 0 or (status == "scored" and (score is None or not np.isfinite(score))):
                    raise ValueError("nonfinite score or invalid score dimension")
                rows.append(
                    dict(
                        mode=mode,
                        family=row["family"],
                        model=row["model"],
                        group=group,
                        status=status,
                        weight=weight,
                        dimensions=dims,
                        score_nats=score,
                        score_nats_per_dimension=score / dims if score is not None else None,
                        reason=row.get("reason", ""),
                    )
                )
        if not models or any(v != {f"M{i}" for i in range(6)} for v in models.values()):
            raise ValueError("all M0-M5 rows, including unavailable candidates, required")
        summaries[mode] = paired_pattern_summary(evaluation, families)
    point = summaries.get("within", {f"M4-M{i}": None for i in (0, 1, 2, 3, 5)})
    intervals = {}
    for contrast, estimate in point.items():
        values = [
            b["scores"][contrast]
            for b in bootstrap
            if b["status"] == "completed" and b["scores"].get(contrast) is not None
        ]
        if not all(np.isfinite(v) for v in values):
            raise ValueError("nonfinite bootstrap score")
        intervals[contrast] = dict(
            estimate=estimate,
            complete_replicates=len(values),
            requested_replicates=requested_replicates,
            percentile_95=np.quantile(values, [0.025, 0.975]).tolist()
            if estimate is not None and len(values) == requested_replicates
            else None,
        )
    result = dict(
        schema_version=1,
        implementation="generative_pattern_reporting_v1",
        families=families,
        summaries=summaries,
        intervals=intervals,
        coverage=coverage,
        bootstrap_coverage=[
            {k: b[k] for k in ("replicate", "status", "reason") if k in b} for b in bootstrap
        ],
        missing_bootstrap_replicates=sorted(set(range(requested_replicates)) - set(indices)),
        scope="fixed_conditions_fixed_families_external_calibration_fixed",
        multiplicity_adjusted=False,
        equivalence_tested=False,
        scientific_gate=None,
        raw_preprocessing_included=False,
    )
    columns = [
        "mode",
        "family",
        "model",
        "group",
        "status",
        "weight",
        "dimensions",
        "score_nats",
        "score_nats_per_dimension",
        "reason",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(output / "scores.tsv", stream.getvalue())
    atomic_write_json(output / "summary.json", result)
    atomic_write_json(output / "candidate-audits.json", evaluations)
    return result
