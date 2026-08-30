"""Equal-family random-effects evidence synthesis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True, slots=True)
class RandomEffectsSummary:
    """Normal approximation to an equal-family random-effects model."""

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
