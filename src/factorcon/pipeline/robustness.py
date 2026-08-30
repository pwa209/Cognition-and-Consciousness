"""Specification-curve and influence checks for canonical family RDMs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from factorcon.models.architectures import ARCHITECTURES
from factorcon.models.fit import evaluate_architecture
from factorcon.pipeline.canonical import load_canonical_rdm
from factorcon.util import atomic_write_json, hash_file, utc_now


def robustness_canonical_rdm(
    path: str | Path,
    output: str | Path,
    *,
    family: str,
    seed: int = 260830,
) -> dict[str, Any]:
    """Evaluate declared regularization branches and leave-one-replicate influence."""

    arrays, design = load_canonical_rdm(path)
    branches = {
        "weak_regularization": (0.0, 1e-5, 1e-4, 1e-3),
        "default": (0.0, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0),
        "strong_regularization": (1e-2, 1e-1, 1.0, 10.0, 100.0),
    }
    specifications: list[dict[str, Any]] = []
    for branch, alphas in branches.items():
        scores = {
            model: evaluate_architecture(model, design, arrays["train"], arrays["test"], alphas=alphas).log_score
            for model in ARCHITECTURES
        }
        alternative = max(("M0", "M1", "M2", "M3"), key=scores.__getitem__)
        specifications.append(
            {
                "branch": branch,
                "scores": scores,
                "best_nonfactorized": alternative,
                "delta_M4": scores["M4"] - scores[alternative],
            }
        )
    influence: list[dict[str, Any]] = []
    if len(arrays["test"]) > 1:
        for omitted in range(len(arrays["test"])):
            test = np.delete(arrays["test"], omitted, axis=0)
            scores = {
                model: evaluate_architecture(model, design, arrays["train"], test).log_score
                for model in ("M0", "M1", "M2", "M3", "M4")
            }
            alternative = max(("M0", "M1", "M2", "M3"), key=scores.__getitem__)
            influence.append(
                {"omitted_test_replicate": omitted, "best_nonfactorized": alternative, "delta_M4": scores["M4"] - scores[alternative]}
            )
    rng = np.random.default_rng(seed)
    permuted_design = {name: values[rng.permutation(len(values))] for name, values in design.items()}
    negative = {
        model: evaluate_architecture(model, permuted_design, arrays["train"], arrays["test"]).log_score
        for model in ("M0", "M1", "M2", "M3", "M4")
    }
    report = {
        "family": family,
        "created_utc": utc_now(),
        "input_sha256": hash_file(path),
        "specifications": specifications,
        "leave_one_replicate_out": influence,
        "random_construct_map_negative_control": negative,
        "all_branches_retained": True,
        "scientific_gate": None,
    }
    atomic_write_json(output, report)
    return report

