"""Run-wise fMRI GLM with explicit confound and censoring inputs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class GLMResult:
    """Condition betas and residuals from one run."""

    betas: NDArray[np.float64]
    residuals: NDArray[np.float64]
    rank: int
    condition_count: int
    censored_volumes: int


def fit_runwise_glm(
    signals: ArrayLike,
    condition_design: ArrayLike,
    confounds: ArrayLike,
    *,
    censor: ArrayLike | None = None,
    ridge: float = 1e-6,
) -> GLMResult:
    """Fit condition and nuisance regressors to volumes-by-features data.

    ``condition_design`` must already contain the declared HRF-convolved regressors.
    Censored volumes are removed before fit. Construct effects (dose, A, K, R) must not
    be passed as nuisance confounds.
    """

    y = np.asarray(signals, dtype=float)
    conditions = np.asarray(condition_design, dtype=float)
    nuisance = np.asarray(confounds, dtype=float)
    if y.ndim != 2 or conditions.ndim != 2 or nuisance.ndim != 2:
        raise ValueError("signals/design/confounds must be matrices")
    if len(y) != len(conditions) or len(y) != len(nuisance):
        raise ValueError("all inputs must have equal volume count")
    keep = np.ones(len(y), dtype=bool) if censor is None else ~np.asarray(censor, dtype=bool)
    if keep.shape != (len(y),) or keep.sum() <= conditions.shape[1] + nuisance.shape[1]:
        raise ValueError("censor mask invalid or leaves insufficient volumes")
    design = np.column_stack([conditions[keep], nuisance[keep], np.ones(keep.sum())])
    penalty = np.eye(design.shape[1]) * ridge
    penalty[-1, -1] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y[keep])
    residuals = y[keep] - design @ coefficients
    return GLMResult(
        betas=coefficients[: conditions.shape[1]],
        residuals=residuals,
        rank=int(np.linalg.matrix_rank(design)),
        condition_count=conditions.shape[1],
        censored_volumes=int((~keep).sum()),
    )

