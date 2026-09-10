"""Explicit multiplicity and independent-unit contrast utilities.

Do not feed dependent cross-validation fold scores to these tests as if independent.
Training-refit uncertainty and exchangeability must be justified by the calling design.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def holm_adjust(p_values: NDArray[np.float64]) -> NDArray[np.float64]:
    """Holm FWER adjustment of a complete declared finite p-value family (unitless)."""
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("complete finite p-value vector in [0,1] required")
    order = np.argsort(p, kind="stable")
    result = np.empty_like(p)
    result[order] = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    return result


def max_t_sign_flip(
    differences: NDArray[np.float64], *, permutations: int = 9999, seed: int = 260830
) -> dict[str, object]:
    """Two-sided max-|t| shared-sign null for independent symmetric group contrasts.

    Input independent units x predeclared endpoints in common score units. All
    endpoints share each unit's sign. Subset pivotality is an additional assumption
    for strong FWER control. No automated claim that these assumptions hold for CV.
    """
    x = np.asarray(differences, dtype=float)
    if x.ndim != 2 or x.shape[0] < 3 or not x.shape[1] or not np.isfinite(x).all():
        raise ValueError("finite >=3 independent units x endpoints required")
    if permutations < 1:
        raise ValueError("positive permutation count required")

    def statistic(values: NDArray[np.float64]) -> NDArray[np.float64]:
        se = values.std(axis=0, ddof=1) / np.sqrt(len(values))
        if np.any(se == 0):
            # Degenerate evidence is not converted into an arbitrary infinite score.
            raise ValueError("zero contrast variance; t statistic not estimable")
        return np.abs(values.mean(axis=0) / se)

    observed = statistic(x)
    rng = np.random.default_rng(seed)
    exceed = np.zeros(x.shape[1], dtype=int)
    for _ in range(permutations):
        null = statistic(x * rng.choice([-1, 1], size=(len(x), 1)))
        exceed += null.max() >= observed
    return {
        "adjusted_p": ((exceed + 1) / (permutations + 1)).tolist(),
        "abs_t": observed.tolist(),
        "permutations": permutations,
        "assumptions": "independent_symmetric_units_and_subset_pivotality",
    }


def tost_equivalence(
    differences: NDArray[np.float64], margin: float, alpha: float = 0.05
) -> dict[str, float | bool]:
    """Paired independent-unit t equivalence with an externally declared score margin.

    Margin and differences share units. Failure to reject difference is not equivalence;
    this test assumes independent approximately Gaussian unit-level differences.
    """
    from scipy.stats import t

    x = np.asarray(differences, dtype=float)
    if (
        x.ndim != 1
        or len(x) < 3
        or not np.isfinite(x).all()
        or not np.isfinite(margin)
        or margin <= 0
        or not 0 < alpha < 0.5
    ):
        raise ValueError("finite independent differences, positive margin and valid alpha required")
    se = float(x.std(ddof=1) / np.sqrt(len(x)))
    if se == 0:
        raise ValueError("zero variance: t equivalence not estimable")
    mean = float(x.mean())
    p = float(max(t.sf((mean + margin) / se, len(x) - 1), t.cdf((mean - margin) / se, len(x) - 1)))
    return {"mean": mean, "margin": margin, "p": p, "equivalent": p < alpha}
