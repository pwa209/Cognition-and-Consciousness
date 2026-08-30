"""Nested held-out fitting for component-RDM candidate architectures."""

from __future__ import annotations

from dataclasses import dataclass
from math import log, pi
from collections.abc import Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from factorcon.features.rdm import design_rdm, vectorize_rdm
from factorcon.models.architectures import component_design


@dataclass(frozen=True, slots=True)
class ArchitectureScore:
    """Held-out score and fitted complexity for one candidate architecture."""

    architecture: str
    log_score: float
    mean_squared_error: float
    alpha: float
    effective_df: float
    intercept: float
    weights: dict[str, float]
    residual_variance: float
    predictions: NDArray[np.float64]


def nonnegative_ridge(
    components: ArrayLike,
    target: ArrayLike,
    *,
    alpha: float,
    max_iter: int = 20_000,
    tolerance: float = 1e-11,
) -> tuple[float, NDArray[np.float64]]:
    """Fit nonnegative component weights with an unrestricted intercept."""

    x = np.asarray(components, dtype=float)
    y = np.asarray(target, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("components must be pairs-by-components and target pairs-long")
    if alpha < 0 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("invalid finite data or alpha")
    weights = np.zeros(x.shape[1], dtype=float)
    intercept = float(y.mean())
    norms = np.sum(np.square(x), axis=0) + alpha
    for _ in range(max_iter):
        previous = weights.copy()
        intercept = float(np.mean(y - x @ weights))
        for column in range(x.shape[1]):
            residual = y - intercept - x @ weights + x[:, column] * weights[column]
            weights[column] = max(0.0, float(x[:, column] @ residual / norms[column]))
        if np.max(np.abs(weights - previous), initial=0.0) < tolerance:
            break
    return intercept, weights


def _component_matrix(
    architecture: str, design: Mapping[str, ArrayLike]
) -> tuple[list[str], NDArray[np.float64]]:
    components = component_design(architecture, design)
    names = list(components)
    columns = [vectorize_rdm(design_rdm(vector)) for vector in components.values()]
    if not columns:
        return names, np.empty((len(next(iter(design.values()))) * (len(next(iter(design.values()))) - 1) // 2, 0))
    matrix = np.column_stack(columns)
    scale = np.linalg.norm(matrix, axis=0)
    scale = np.where(scale > np.finfo(float).eps, scale, 1.0)
    return names, matrix / scale


def _score_prediction(observations: NDArray[np.float64], prediction: NDArray[np.float64], variance: float) -> float:
    residual = observations - prediction[None, :]
    return float(-0.5 * np.mean(np.square(residual) / variance + log(2 * pi * variance)))


def _select_alpha(
    matrix: NDArray[np.float64],
    train: NDArray[np.float64],
    alphas: Sequence[float],
) -> float:
    if len(train) < 2 or matrix.shape[1] == 0:
        return float(alphas[0])
    losses = []
    for alpha in alphas:
        fold_losses = []
        for held_out in range(len(train)):
            fit_rows = np.delete(train, held_out, axis=0)
            intercept, weights = nonnegative_ridge(matrix, fit_rows.mean(axis=0), alpha=float(alpha))
            prediction = intercept + matrix @ weights
            fold_losses.append(float(np.mean(np.square(train[held_out] - prediction))))
        losses.append(float(np.mean(fold_losses)))
    return float(alphas[int(np.argmin(losses))])


def evaluate_architecture(
    architecture: str,
    design: Mapping[str, ArrayLike],
    train_rdms: ArrayLike,
    test_rdms: ArrayLike,
    *,
    alphas: Sequence[float] = (0.0, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0),
) -> ArchitectureScore:
    """Fit on independent training RDM replicates and score untouched test replicates."""

    train = np.asarray(train_rdms, dtype=float)
    test = np.asarray(test_rdms, dtype=float)
    if train.ndim == 1:
        train = train[None, :]
    if test.ndim == 1:
        test = test[None, :]
    if train.ndim != 2 or test.ndim != 2 or train.shape[1] != test.shape[1]:
        raise ValueError("train_rdms and test_rdms must have the same pair dimension")
    names, matrix = _component_matrix(architecture, design)
    if matrix.shape[0] != train.shape[1]:
        raise ValueError("condition design and observed RDM pair counts disagree")

    if architecture == "M5":
        prediction = train.mean(axis=0)
        alpha = 0.0
        intercept = 0.0
        weights = np.empty(0)
        effective_df = float(len(prediction))
    else:
        alpha = _select_alpha(matrix, train, alphas)
        intercept, weights = nonnegative_ridge(matrix, train.mean(axis=0), alpha=alpha)
        prediction = intercept + matrix @ weights
        active = weights > 1e-10
        if np.any(active):
            gram = matrix[:, active].T @ matrix[:, active]
            effective_df = 1.0 + float(np.trace(gram @ np.linalg.pinv(gram + alpha * np.eye(len(gram)))))
        else:
            effective_df = 1.0
    train_residual = train - prediction[None, :]
    variance = max(float(np.mean(np.square(train_residual))), 1e-9)
    mse = float(np.mean(np.square(test - prediction[None, :])))
    return ArchitectureScore(
        architecture=architecture,
        log_score=_score_prediction(test, prediction, variance),
        mean_squared_error=mse,
        alpha=alpha,
        effective_df=effective_df,
        intercept=intercept,
        weights={name: float(value) for name, value in zip(names, weights, strict=True)},
        residual_variance=variance,
        predictions=prediction,
    )


def component_removal_scores(
    full_prediction: ArrayLike,
    reduced_predictions: Mapping[str, ArrayLike],
    observations: ArrayLike,
) -> dict[str, float]:
    """Return out-of-sample MSE improvement of a full model over each component removal."""

    full = np.asarray(full_prediction, dtype=float)
    observed = np.asarray(observations, dtype=float)
    full_error = float(np.mean(np.square(observed - full)))
    return {
        name: float(np.mean(np.square(observed - np.asarray(prediction, dtype=float))) - full_error)
        for name, prediction in reduced_predictions.items()
    }

