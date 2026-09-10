"""Nested group prediction and source-only leave-one-family-out transfer.

Inputs use external calibration; empirically calibrated overlapping neural subjects
are rejected. This deliberately does not pretend a precomputed all-subject design is
fold-safe. No test outcome selects penalties, scales, signs, or architecture variants.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from factorcon.models.architectures import CONSTRUCT_ORDER, unavailable_reason
from factorcon.models.generative import (
    ModelShape,
    PatternData,
    fit_generative,
    predictive_scores,
)


def validate_collection(datasets: tuple[PatternData, ...]) -> None:
    """Validate globally unique independent IDs and external calibration separation."""
    if not datasets or len({d.family for d in datasets}) != len(datasets):
        raise ValueError("one nonempty input per unique family required")
    for data in datasets:
        data.validate()
    ids = [g for d in datasets for g in d.group_ids]
    if len(ids) != len(set(ids)):
        raise ValueError("neural groups overlap across families")
    if set(ids) & {g for d in datasets for g in d.calibration_ids}:
        raise ValueError("calibration overlaps neural groups across families")


def _shape(
    datasets: tuple[PatternData, ...],
    architecture: str,
    interactions: tuple[tuple[str, str], ...],
    options: dict[str, Any],
) -> ModelShape:
    names = tuple(n for n in CONSTRUCT_ORDER if any(n in d.names for d in datasets))
    return ModelShape(
        architecture,
        names,
        tuple((a, b) for a, b in interactions if a in names and b in names),
        condition_count=datasets[0].patterns.shape[2],
        **options,
    )


def _tune(
    datasets: tuple[PatternData, ...],
    shape: ModelShape,
    penalties: tuple[float, ...],
    fit_options: dict[str, Any],
) -> tuple[float, list[dict[str, Any]]]:
    if any(len(d.group_ids) < 2 for d in datasets):
        raise ValueError("inner CV requires >=2 independent training groups per family")
    audit = []
    for penalty in penalties:
        family_scores = []
        for f, data in enumerate(datasets):
            scores = []
            for g in range(len(data.group_ids)):
                train = list(datasets)
                train[f] = data.subset(np.delete(np.arange(len(data.group_ids)), g))
                fit = fit_generative(tuple(train), shape, penalty=penalty, **fit_options)
                test = data.subset(np.asarray([g]))
                dimensions = np.prod(test.patterns.shape[1:]) - (
                    test.patterns.shape[1] * test.patterns.shape[3]
                )
                scores.append(float(predictive_scores(fit, test)[0] / dimensions))
            family_scores.append(float(np.average(scores, weights=data.group_weights)))
        audit.append(
            {
                "penalty": penalty,
                "family_scores": family_scores,
                "mean": float(np.mean(family_scores)),
            }
        )
    # Explicit deterministic first-listed tie policy, no test-dependent choice.
    return penalties[int(np.argmax([a["mean"] for a in audit]))], audit


def evaluate_patterns(
    datasets: tuple[PatternData, ...],
    *,
    mode: str,
    penalties: tuple[float, ...],
    interactions: tuple[tuple[str, str], ...] = (),
    shape_options: dict[str, Any] | None = None,
    fit_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return all M0-M5 group scores in nats, with source-only nested fitting audits.

    Within-family outer folds leave one independent group out; LOFO leaves the entire
    target family out. LOFO requires identical external scale/measurement anchors and
    source support for every target main effect and declared interaction. A failed
    numerical fit remains a row, not a zero score or a scientific stopping decision.
    This API supplies prediction, not bootstrap uncertainty for refitted training sets.
    """
    validate_collection(datasets)
    if mode not in {"within", "lofo"}:
        raise ValueError("mode must be within or lofo")
    if (
        not penalties
        or len(set(penalties)) != len(penalties)
        or any(not np.isfinite(p) or p < 0 for p in penalties)
    ):
        raise ValueError("unique nonnegative finite penalty grid required")
    if any(len(d.group_ids) < 3 for d in datasets):
        raise ValueError("nested evaluation requires >=3 independent groups per family")
    if mode == "lofo" and len(datasets) < 2:
        raise ValueError("LOFO requires >=2 families")
    rows: list[dict[str, Any]] = []
    for target in datasets:
        folds = range(len(target.group_ids)) if mode == "within" else [None]
        for group in folds:
            if group is None:
                sources = tuple(d for d in datasets if d.family != target.family)
                test = target
            else:
                sources = (target.subset(np.delete(np.arange(len(target.group_ids)), group)),)
                test = target.subset(np.asarray([group]))
            for architecture in (f"M{i}" for i in range(6)):
                row: dict[str, Any] = {
                    "family": target.family,
                    "model": architecture,
                    "test_groups": list(test.group_ids),
                    "test_group_weights": (
                        np.ones(len(test.group_ids))
                        if test.group_weights is None
                        else test.group_weights
                    ).tolist(),
                    "scored_dimensions_per_group": int(
                        test.patterns.shape[1]
                        * (test.patterns.shape[2] - 1)
                        * test.patterns.shape[3]
                    ),
                    "training_groups": [g for d in sources for g in d.group_ids],
                }
                reason = unavailable_reason(architecture, dict.fromkeys(test.names))
                if mode == "lofo":
                    source_names = {n for d in sources for n in d.names}
                    feature_support = [{n} for n in test.names] + [
                        {a, b} for a, b in interactions if a in test.names and b in test.names
                    ]
                    if architecture == "M5":
                        reason = "free condition covariance has no cross-family mapping"
                    elif len({d.anchor_id for d in (*sources, test)}) != 1:
                        reason = "external measurement/feature anchors differ"
                    elif set(test.names) - source_names:
                        reason = "target construct not represented in training families"
                    elif architecture == "M4" and any(
                        a in test.names
                        and b in test.names
                        and not any(a in d.names and b in d.names for d in sources)
                        for a, b in interactions
                    ):
                        reason = "target interaction lacks joint source-family support"
                    # Cross-covariance of jointly absent constructs cannot be learned.
                    elif architecture == "M4" and any(
                        not any((left | right) <= set(d.names) for d in sources)
                        for left in feature_support
                        for right in feature_support
                    ):
                        reason = "target feature cross-covariance lacks joint source support"
                if reason is None:
                    reason = next(
                        (
                            r
                            for d in sources
                            if (r := unavailable_reason(architecture, dict.fromkeys(d.names)))
                        ),
                        None,
                    )
                if reason:
                    rows.append({**row, "status": "not_estimable", "reason": reason})
                    continue
                try:
                    shape = _shape(sources, architecture, interactions, shape_options or {})
                    penalty, tuning = _tune(sources, shape, penalties, fit_options or {})
                    fit = fit_generative(sources, shape, penalty=penalty, **(fit_options or {}))
                    scores = predictive_scores(fit, test)
                    rows.append(
                        {
                            **row,
                            "status": "scored",
                            "scores_nats": scores.tolist(),
                            "penalty": penalty,
                            "inner_cv": tuning,
                            "shape": asdict(shape),
                            "parameters": fit.theta.tolist(),
                            "optimizer_starts": fit.starts,
                        }
                    )
                except (ValueError, np.linalg.LinAlgError) as exc:
                    rows.append(
                        {
                            **row,
                            "status": "numerical_or_design_failure",
                            "reason": str(exc),
                            "optimizer_starts": getattr(exc, "diagnostics", ()),
                        }
                    )
    return {
        "implementation": "generative_pattern_v1",
        "mode": mode,
        "rows": rows,
        "uncertainty_scope": "external_design_draws_conditional_on_fitted_parameters",
        "score_units": "joint_nats_per_independent_group",
        "comparison_rule": "paired_same_test_groups_same_feature_space_only",
        "all_candidates_retained": True,
        "scientific_gate": None,
    }
