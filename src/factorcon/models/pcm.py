"""Gaussian pattern-component likelihood for condition-level neural patterns."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class PCMFit:
    """Maximum-likelihood nonnegative covariance-component fit."""

    component_weights: NDArray[np.float64]
    noise_variance: float
    log_likelihood: float
    converged: bool
    iterations: int


def _log_likelihood(
    parameters: NDArray[np.float64],
    patterns: NDArray[np.float64],
    components: Sequence[NDArray[np.float64]],
) -> float:
    weights = np.exp(parameters[:-1])
    noise = float(np.exp(parameters[-1]))
    covariance = sum(
        weight * component for weight, component in zip(weights, components, strict=True)
    )
    covariance = covariance + np.eye(len(covariance)) * noise
    sign, logdet = np.linalg.slogdet(covariance)
    if sign <= 0:
        return -np.inf
    solved = np.linalg.solve(covariance, patterns)
    feature_count = patterns.shape[1]
    return float(
        -0.5
        * (
            feature_count * logdet
            + np.sum(patterns * solved)
            + len(covariance) * feature_count * np.log(2 * np.pi)
        )
    )


def fit_pcm(
    condition_patterns: ArrayLike,
    covariance_components: Sequence[ArrayLike],
    *,
    initial_variance: float = 1.0,
    max_iter: int = 1_000,
) -> PCMFit:
    """Fit nonnegative PCM covariance weights by L-BFGS-B.

    Rows are condition estimates from one independent partition; columns are noise-
    normalized features. Hyperparameters must be fit separately inside each outer fold.
    SciPy is an optional analysis dependency and imported only when this model runs.
    """

    try:
        from scipy.optimize import minimize  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("fit_pcm requires the 'analysis' optional dependencies") from exc
    patterns = np.asarray(condition_patterns, dtype=float)
    components = [np.asarray(value, dtype=float) for value in covariance_components]
    if patterns.ndim != 2 or not components:
        raise ValueError("condition_patterns must be a matrix and components non-empty")
    for component in components:
        if component.shape != (len(patterns), len(patterns)) or not np.allclose(
            component, component.T
        ):
            raise ValueError(
                "every covariance component must be symmetric conditions-by-conditions"
            )
    start = np.full(len(components) + 1, np.log(max(initial_variance, 1e-8)), dtype=float)
    result = minimize(
        lambda parameter: -_log_likelihood(parameter, patterns, components),
        start,
        method="L-BFGS-B",
        bounds=[(-20.0, 20.0)] * len(start),
        options={"maxiter": max_iter, "ftol": 1e-12},
    )
    return PCMFit(
        component_weights=np.exp(result.x[:-1]),
        noise_variance=float(np.exp(result.x[-1])),
        log_likelihood=float(-result.fun),
        converged=bool(result.success),
        iterations=int(result.nit),
    )
