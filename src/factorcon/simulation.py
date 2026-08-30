"""Synthetic architecture generation and recovery benchmarks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from factorcon.features.rdm import design_rdm, vectorize_rdm
from factorcon.models.architectures import ARCHITECTURES, component_design
from factorcon.models.fit import evaluate_architecture
from factorcon.util import atomic_write_json, utc_now


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    """One synthetic truth scenario and its held-out candidate ranking."""

    truth: str
    seed: int
    theory_winner: str
    scores: dict[str, float]
    mse: dict[str, float]
    effective_df: dict[str, float]
    saturated_ceiling_score: float


def factorial_design(condition_count: int, seed: int) -> dict[str, NDArray[np.float64]]:
    """Create non-collinear synthetic E/K/A/R/S condition values."""

    if condition_count < 24:
        raise ValueError("condition_count must be at least 24")
    rng = np.random.default_rng(seed)
    design = {
        "E": rng.normal(size=condition_count),
        "A": rng.normal(size=condition_count),
        "R": rng.choice([-1.0, 1.0], size=condition_count),
        "K_content": rng.choice([-1.0, 1.0], size=condition_count),
        "K_memory": rng.normal(size=condition_count),
        "K_task": rng.choice([-1.0, 1.0], size=condition_count),
        "K_volition": rng.normal(size=condition_count),
        "S": rng.normal(size=condition_count),
    }
    return design


def simulate_rdms(
    truth: str,
    *,
    seed: int,
    condition_count: int = 36,
    train_replicates: int = 12,
    test_replicates: int = 12,
    noise_sd: float = 0.12,
) -> tuple[dict[str, NDArray[np.float64]], NDArray[np.float64], NDArray[np.float64]]:
    """Generate independent noisy RDM replicates under one candidate architecture."""

    if truth not in {"M0", "M1", "M2", "M3", "M4"}:
        raise ValueError("truth must be a theoretical architecture M0-M4")
    rng = np.random.default_rng(seed)
    design = factorial_design(condition_count, seed + 17)
    components = component_design(truth, design)
    matrix = np.column_stack([vectorize_rdm(design_rdm(value)) for value in components.values()])
    norms = np.linalg.norm(matrix, axis=0)
    matrix = matrix / np.where(norms > 0, norms, 1.0)
    weights = rng.uniform(0.5, 1.5, size=matrix.shape[1])
    truth_vector = matrix @ weights
    truth_vector = (truth_vector - truth_vector.mean()) / max(truth_vector.std(), 1e-12)
    train = truth_vector + rng.normal(scale=noise_sd, size=(train_replicates, len(truth_vector)))
    test = truth_vector + rng.normal(scale=noise_sd, size=(test_replicates, len(truth_vector)))
    return design, train, test


def recover_architecture(truth: str, *, seed: int = 260830) -> RecoveryResult:
    """Fit M0-M5 to independent synthetic train/test RDMs and rank M0-M4."""

    design, train, test = simulate_rdms(truth, seed=seed)
    scores = {
        model: evaluate_architecture(model, design, train, test)
        for model in ARCHITECTURES
    }
    theory_winner = max((model for model in ARCHITECTURES if model != "M5"), key=lambda model: scores[model].log_score)
    return RecoveryResult(
        truth=truth,
        seed=seed,
        theory_winner=theory_winner,
        scores={model: value.log_score for model, value in scores.items()},
        mse={model: value.mean_squared_error for model, value in scores.items()},
        effective_df={model: value.effective_df for model, value in scores.items()},
        saturated_ceiling_score=scores["M5"].log_score,
    )


def run_recovery_suite(
    architectures: list[str], *, seed: int, output: str | Path
) -> dict[str, Any]:
    """Run deterministic recovery cases and write a machine-readable report."""

    results = [recover_architecture(model, seed=seed + index * 1009) for index, model in enumerate(architectures)]
    report = {
        "generated_utc": utc_now(),
        "seed": seed,
        "results": [asdict(result) for result in results],
        "all_truths_recovered": all(result.truth == result.theory_winner for result in results),
        "note": "M5 is a predictable ceiling and is not ranked as a theoretical winner.",
    }
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target / "architecture_recovery.json", report)
    return report

