"""Explicit finite-family estimands and precision-weighted sensitivity summaries."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True, slots=True)
class RandomEffectsSummary:
    """Normal approximation to a precision-weighted random-effects model."""

    mean: float
    standard_error: float
    ci_low: float
    ci_high: float
    tau2: float
    prediction_low: float
    prediction_high: float
    family_count: int


def random_effects_normal(effects: ArrayLike, standard_errors: ArrayLike) -> RandomEffectsSummary:
    """Estimate a DerSimonian-Laird random-effects summary across families.

    One effect and uncertainty must be supplied per experimental family, preventing
    trial-rich families from entering multiple likelihood terms.
    """

    y = np.asarray(effects, dtype=float)
    se = np.asarray(standard_errors, dtype=float)
    if y.ndim != 1 or se.shape != y.shape or len(y) < 2:
        raise ValueError("effects and standard_errors must be equal one-dimensional arrays")
    if not np.isfinite(y).all() or not np.isfinite(se).all() or np.any(se <= 0):
        raise ValueError("effects must be finite and standard errors positive")
    fixed_w = 1.0 / np.square(se)
    fixed_mean = float(np.sum(fixed_w * y) / np.sum(fixed_w))
    q = float(np.sum(fixed_w * np.square(y - fixed_mean)))
    c = float(np.sum(fixed_w) - np.sum(np.square(fixed_w)) / np.sum(fixed_w))
    tau2 = max(0.0, (q - (len(y) - 1)) / c) if c > 0 else 0.0
    weights = 1.0 / (np.square(se) + tau2)
    mean = float(np.sum(weights * y) / np.sum(weights))
    mean_se = float(np.sqrt(1.0 / np.sum(weights)))
    z = 1.959963984540054
    prediction_se = float(np.sqrt(tau2 + mean_se**2))
    return RandomEffectsSummary(
        mean=mean,
        standard_error=mean_se,
        ci_low=mean - z * mean_se,
        ci_high=mean + z * mean_se,
        tau2=tau2,
        prediction_low=mean - z * prediction_se,
        prediction_high=mean + z * prediction_se,
        family_count=len(y),
    )


def equal_family_summary(
    effects: ArrayLike, standard_errors: list[float | None]
) -> dict[str, object]:
    """Summarize the finite set of available families with exactly 1/F weight.

    Effects and SEs have common score units (nats/pair for canonical RDMs). The
    normal interval is conditional on fitted training models, fixed conditions,
    independent families, and their supplied test-group SEs; it is not a posterior
    or a prediction interval for new paradigms. Missing SEs remain unavailable.
    """
    y = np.asarray(effects, dtype=float)
    if y.ndim != 1 or not len(y) or len(y) != len(standard_errors) or not np.isfinite(y).all():
        raise ValueError("one finite effect and one SE entry required per family")
    if any(se is not None and (not np.isfinite(se) or se < 0) for se in standard_errors):
        raise ValueError("SEs must be nonnegative finite numbers or None")
    mean = float(y.mean())
    se = (
        float(np.sqrt(sum(value**2 for value in standard_errors if value is not None)) / len(y))
        if all(value is not None for value in standard_errors)
        else None
    )
    return {
        "mean": mean,
        "standard_error": se,
        "conditional_normal_ci_95": (
            [mean - 1.959963984540054 * se, mean + 1.959963984540054 * se]
            if se is not None
            else None
        ),
        "family_count": len(y),
        "weights": [1.0 / len(y)] * len(y),
        "estimand": "finite_available_family_mean",
        "uncertainty_scope": "test_groups_only_conditional_on_training_and_fixed_conditions",
        "generalizes_to_new_families": False,
    }
