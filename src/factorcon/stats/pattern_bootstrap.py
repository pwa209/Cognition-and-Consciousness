"""Independent-group bootstrap that refits the complete nested pattern evaluator.

Subject multiplicities are weights, never cloned IDs that can leak across folds.
Intervals generalize over independent groups at fixed conditions and families only.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from factorcon.models.generative import PatternData
from factorcon.models.pattern_cv import evaluate_patterns, validate_collection


def paired_pattern_summary(
    evaluation: dict[str, Any], families: tuple[str, ...]
) -> dict[str, float | None]:
    """Equal-family M4-minus-comparator scores, in nats/scored dimension.

    Requires identical test groups/weights/dimensions for both models and every
    declared family. Missing scores do not silently change the comparison population.
    """
    result = {}
    for comparator in ("M0", "M1", "M2", "M3", "M5"):
        family_deltas = []
        for family in families:
            by_model = {}
            for model in ("M4", comparator):
                selected = [
                    r for r in evaluation["rows"] if r["family"] == family and r["model"] == model
                ]
                if not selected or any(r["status"] != "scored" for r in selected):
                    break
                mapping = {}
                for row in selected:
                    for group, score, weight in zip(
                        row["test_groups"],
                        row["scores_nats"],
                        row["test_group_weights"],
                        strict=True,
                    ):
                        if group in mapping:
                            raise ValueError("duplicate test group/model prediction")
                        mapping[group] = (score / row["scored_dimensions_per_group"], weight)
                by_model[model] = mapping
            if len(by_model) != 2:
                break
            left, right = by_model["M4"], by_model[comparator]
            if left.keys() != right.keys() or any(left[g][1] != right[g][1] for g in left):
                raise ValueError("unpaired independent groups/weights in contrast")
            family_deltas.append(
                float(
                    np.average(
                        [left[g][0] - right[g][0] for g in left], weights=[left[g][1] for g in left]
                    )
                )
            )
        result[f"M4-{comparator}"] = (
            float(np.mean(family_deltas)) if len(family_deltas) == len(families) else None
        )
    return result


def refit_pattern_bootstrap(
    datasets: tuple[PatternData, ...],
    *,
    replicates: int,
    evaluation_options: dict[str, Any],
    seed: int = 260830,
) -> dict[str, Any]:
    """Bootstrap groups within each fixed family, rerun outer/inner fits, retain failures.

    Percentile intervals are unadjusted, fixed-condition/fixed-family subject-bootstrap
    intervals. They do not establish new-condition generalization, simultaneous FWER,
    or coverage with sparse groups. External calibration draws remain fixed (integrated
    by the evaluator); their calibration sample itself is not bootstrap-refitted here.
    """
    validate_collection(datasets)
    if replicates < 2 or any(d.group_weights is not None for d in datasets):
        raise ValueError(">=2 replicates and original unweighted groups required")
    families = tuple(d.family for d in datasets)
    point_evaluation = evaluate_patterns(datasets, **evaluation_options)
    point = paired_pattern_summary(point_evaluation, families)
    rng = np.random.default_rng(seed)
    records = []
    for replicate in range(replicates):
        sampled = []
        multiplicities = {}
        for data in datasets:
            n = len(data.group_ids)
            counts = np.bincount(rng.integers(0, n, n), minlength=n)
            keep = np.flatnonzero(counts)
            multiplicities[data.family] = dict(zip(data.group_ids, counts.tolist(), strict=True))
            sampled.append(replace(data.subset(keep), group_weights=counts[keep].astype(float)))
        try:
            evaluation = evaluate_patterns(tuple(sampled), **evaluation_options)
            summary = paired_pattern_summary(evaluation, families)
            records.append(
                {
                    "replicate": replicate,
                    "status": "completed",
                    "scores": summary,
                    "multiplicities": multiplicities,
                    "evaluation": evaluation,
                }
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            records.append(
                {
                    "replicate": replicate,
                    "status": "failed",
                    "reason": str(exc),
                    "multiplicities": multiplicities,
                }
            )
    intervals = {}
    for contrast, estimate in point.items():
        values = [
            r["scores"][contrast]
            for r in records
            if r["status"] == "completed" and r["scores"][contrast] is not None
        ]
        # Never issue a conditional-on-success interval that hides failed replicates.
        intervals[contrast] = {
            "estimate": estimate,
            "complete_replicates": len(values),
            "requested_replicates": replicates,
            "percentile_95": np.quantile(values, [0.025, 0.975]).tolist()
            if estimate is not None and len(values) == replicates
            else None,
        }
    return {
        "intervals": intervals,
        "point_evaluation": point_evaluation,
        "replicates": records,
        "scope": "refitted_groups_fixed_conditions_fixed_families_external_calibration_fixed",
        "multiplicity_adjusted": False,
        "scientific_gate": None,
    }
