"""Specification-curve and influence checks for canonical family RDMs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from factorcon.config import load_analysis_spec
from factorcon.pipeline.canonical import DEFAULT_SPEC, evaluate_candidates, load_canonical_rdm
from factorcon.provenance import analysis_artifact
from factorcon.util import atomic_write_json, hash_file, utc_now


@analysis_artifact("P09_component_rdm_robustness")
def robustness_canonical_rdm(
    path: str | Path,
    output: str | Path,
    *,
    family: str,
    seed: int = 260830,
    analysis_spec: str | Path = DEFAULT_SPEC,
) -> dict[str, Any]:
    """Evaluate configured branches and leave-one-independent-group influence.

    Scores are marginal nats/pair on fixed conditions. All paired comparisons are
    retained. A shared condition permutation preserves inter-construct correlation;
    this single shuffle is a descriptive diagnostic, not an exchangeability-valid test.
    """

    arrays, design = load_canonical_rdm(path)
    settings = load_analysis_spec(analysis_spec)["rdm_evaluation"]
    branches = settings["robustness_alphas"]
    specifications: list[dict[str, Any]] = []
    for branch, alphas in branches.items():
        scores = evaluate_candidates(arrays, design, alphas=alphas)
        specifications.append(
            {
                "branch": branch,
                "scores": scores,
                "paired_deltas": _paired_deltas(scores, settings["paired_contrasts"]),
            }
        )
    influence: list[dict[str, Any]] = []
    test_groups = list(dict.fromkeys(arrays["test_group_ids"].tolist()))
    if len(test_groups) > 1:
        base_scores = evaluate_candidates(arrays, design, alphas=settings["alphas"])
        for omitted, group in enumerate(test_groups):
            scores = {
                model: {
                    **score,
                    "log_score": float(np.delete(score["group_log_scores"], omitted).mean()),
                }
                if score["status"] == "scored"
                else score
                for model, score in base_scores.items()
            }
            influence.append(
                {
                    "omitted_test_group": group,
                    "paired_deltas": _paired_deltas(scores, settings["paired_contrasts"]),
                }
            )
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(len(arrays["conditions"]))
    permuted_design = {name: values[permutation] for name, values in design.items()}
    negative = evaluate_candidates(arrays, permuted_design, alphas=settings["alphas"])
    report = {
        "family": family,
        "created_utc": utc_now(),
        "input_sha256": hash_file(path),
        "specifications": specifications,
        "analysis_spec_sha256": hash_file(analysis_spec),
        "leave_one_group_out": influence,
        "random_construct_map_negative_control": negative,
        "permutation": permutation.tolist(),
        "permutation_scope": "joint_condition_shuffle_descriptive_only_no_p_value",
        "all_branches_retained": True,
        "scientific_gate": None,
    }
    atomic_write_json(output, report)
    return report


def _paired_deltas(scores: dict[str, Any], contrasts: list[list[str]]) -> dict[str, float | None]:
    return {
        f"{left}_minus_{right}": scores[left]["log_score"] - scores[right]["log_score"]
        if scores[left]["status"] == scores[right]["status"] == "scored"
        else None
        for left, right in contrasts
    }
