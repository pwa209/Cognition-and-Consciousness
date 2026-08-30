"""Canonical cross-dataset RDM contract and M0-M5 runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.models.architectures import ARCHITECTURES
from factorcon.models.fit import evaluate_architecture
from factorcon.util import atomic_write_json, hash_file, utc_now

REQUIRED_ARRAYS = {
    "train_rdms",
    "test_rdms",
    "design_names",
    "design_values",
    "condition_labels",
}


def load_canonical_rdm(path: str | Path) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Load and validate the modality-neutral RDM exchange contract."""

    source = Path(path)
    with np.load(source, allow_pickle=False) as archive:
        missing = REQUIRED_ARRAYS - set(archive.files)
        if missing:
            raise ValueError(f"Canonical RDM archive missing arrays: {sorted(missing)}")
        train = np.asarray(archive["train_rdms"], dtype=float)
        test = np.asarray(archive["test_rdms"], dtype=float)
        names = [str(value) for value in archive["design_names"]]
        values = np.asarray(archive["design_values"], dtype=float)
        conditions = np.asarray(archive["condition_labels"])
    if train.ndim != 2 or test.ndim != 2 or train.shape[1] != test.shape[1]:
        raise ValueError("train/test RDM arrays must be replicates-by-identical-pairs")
    if values.ndim != 2 or values.shape != (len(names), len(conditions)):
        raise ValueError("design_values must be design_names-by-condition_labels")
    expected_pairs = len(conditions) * (len(conditions) - 1) // 2
    if train.shape[1] != expected_pairs:
        raise ValueError(f"RDM pair count {train.shape[1]} != expected {expected_pairs}")
    if not np.isfinite(train).all() or not np.isfinite(test).all() or not np.isfinite(values).all():
        raise ValueError("canonical arrays must be finite; missingness is resolved upstream")
    design = {name: values[index] for index, name in enumerate(names)}
    return {"train": train, "test": test, "conditions": conditions}, design


def score_canonical_rdm(
    path: str | Path,
    output: str | Path,
    *,
    family: str,
) -> dict[str, Any]:
    """Run every candidate on identical partitions and retain replicate-level scores."""

    arrays, design = load_canonical_rdm(path)
    scores: dict[str, Any] = {}
    for model in ARCHITECTURES:
        aggregate = evaluate_architecture(model, design, arrays["train"], arrays["test"])
        replicate_scores = [
            evaluate_architecture(model, design, arrays["train"], row[None, :]).log_score
            for row in arrays["test"]
        ]
        scores[model] = {
            "name": ARCHITECTURES[model],
            "log_score": aggregate.log_score,
            "replicate_log_scores": replicate_scores,
            "mse": aggregate.mean_squared_error,
            "effective_df": aggregate.effective_df,
            "alpha": aggregate.alpha,
            "weights": aggregate.weights,
            "residual_variance": aggregate.residual_variance,
        }
    report = {
        "family": family,
        "created_utc": utc_now(),
        "input": str(Path(path)),
        "input_sha256": hash_file(path),
        "conditions": [str(value) for value in arrays["conditions"]],
        "train_replicates": len(arrays["train"]),
        "test_replicates": len(arrays["test"]),
        "scores": scores,
        "scientific_gate": None,
        "all_models_retained": True,
    }
    atomic_write_json(output, report)
    return report


def synthesize_scores(paths: list[str | Path], output: str | Path) -> dict[str, Any]:
    """Synthesize M4 versus the strongest nonfactorized alternative with equal family rows."""

    from factorcon.stats.meta import random_effects_normal

    families: list[dict[str, Any]] = []
    for path in paths:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        scores = record["scores"]
        alternative = max(("M0", "M1", "M2", "M3"), key=lambda model: scores[model]["log_score"])
        factorized = np.asarray(scores["M4"]["replicate_log_scores"], dtype=float)
        comparator = np.asarray(scores[alternative]["replicate_log_scores"], dtype=float)
        differences = factorized - comparator
        standard_error = (
            float(differences.std(ddof=1) / np.sqrt(len(differences)))
            if len(differences) > 1
            else 1.0
        )
        standard_error = max(standard_error, 1e-6)
        families.append(
            {
                "family": record["family"],
                "alternative": alternative,
                "delta": float(differences.mean()),
                "standard_error": standard_error,
                "replicates": len(differences),
            }
        )
    if len(families) < 2:
        summary: dict[str, Any] | None = None
    else:
        result = random_effects_normal(
            [item["delta"] for item in families],
            [item["standard_error"] for item in families],
        )
        summary = {
            "mean": result.mean,
            "standard_error": result.standard_error,
            "ci_95": [result.ci_low, result.ci_high],
            "tau2": result.tau2,
            "prediction_95": [result.prediction_low, result.prediction_high],
        }
    report = {
        "created_utc": utc_now(),
        "family_count": len(families),
        "families": families,
        "random_effects": summary,
        "interpretation_gate": None,
        "note": "All technically available family rows are retained regardless of direction.",
    }
    atomic_write_json(output, report)
    return report
