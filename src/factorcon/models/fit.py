"""Nested held-out fitting for component-RDM candidate architectures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import log, pi

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
    replicate_log_scores: NDArray[np.float64]
    group_log_scores: NDArray[np.float64]
    variance_method: str = "leave_one_training_group_out_prediction_error"
    score_kind: str = "mean_gaussian_marginal_log_score_nats_per_pair"


def nonnegative_ridge(
    components: ArrayLike,
    target: ArrayLike,
    *,
    alpha: float,
    max_iter: int = 20_000,
    tolerance: float = 1e-11,
) -> tuple[float, NDArray[np.float64]]:
    """Fit pairs-by-components to pair distances using training data only.

    Alpha penalizes squared weights; the intercept is unpenalized. Distances retain
    their supplied units and signs. Zero/aliased columns are valid, not scientific gates.
    """

    x = np.asarray(components, dtype=float)
    y = np.asarray(target, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("components must be pairs-by-components and target pairs-long")
    if len(y) == 0 or not np.isfinite(alpha) or alpha < 0:
        raise ValueError("non-empty target and finite nonnegative alpha required")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("invalid finite data or alpha")
    if max_iter < 1 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("positive iteration limit and tolerance required")
    x_mean = x.mean(axis=0)
    y_mean = float(y.mean())
    x = x - x_mean
    y = y - y_mean
    weights = np.zeros(x.shape[1], dtype=float)
    norms = np.sum(np.square(x), axis=0) + alpha
    for _ in range(max_iter):
        previous = weights.copy()
        for column in range(x.shape[1]):
            residual = y - x @ weights + x[:, column] * weights[column]
            weights[column] = (
                max(0.0, float(x[:, column] @ residual / norms[column]))
                if norms[column] > 0
                else 0.0
            )
        if np.max(np.abs(weights - previous), initial=0.0) < tolerance:
            break
    else:
        raise ValueError("nonnegative ridge did not converge; no score was produced")
    return y_mean - float(x_mean @ weights), weights


def _component_matrix(
    architecture: str, design: Mapping[str, ArrayLike]
) -> tuple[list[str], NDArray[np.float64]]:
    components = component_design(architecture, design)
    names = list(components)
    columns = [vectorize_rdm(design_rdm(vector)) for vector in components.values()]
    if not columns:
        return names, np.empty(
            (len(next(iter(design.values()))) * (len(next(iter(design.values()))) - 1) // 2, 0)
        )
    matrix = np.column_stack(columns)
    scale = np.linalg.norm(matrix, axis=0)
    scale = np.where(scale > np.finfo(float).eps, scale, 1.0)
    return names, matrix / scale


def _score_prediction(
    observations: NDArray[np.float64], prediction: NDArray[np.float64], variance: float
) -> float:
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
            intercept, weights = nonnegative_ridge(
                matrix, fit_rows.mean(axis=0), alpha=float(alpha)
            )
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
    train_groups: Sequence[str] | None = None,
    test_groups: Sequence[str] | None = None,
) -> ArchitectureScore:
    """Fit replicates-by-pairs RDMs; score in nats per pair, not joint ELPD.

    Repeated rows are averaged within training groups; tuning and predictive-error
    variance use leave-one-training-group-out folds. Test RDMs are also averaged
    within group before scoring, with equal group weights. Group sets must be disjoint.
    Omitted IDs assert independent rows (for low-level/synthetic callers only).
    Design must be fixed independently of these RDM observations. Empirical designs
    require a separate per-inner-fold measurement interface, not one prefit table.
    Pair dependence is not modeled: this is a marginal/composite Gaussian score.
    """

    train = np.asarray(train_rdms, dtype=float)
    test = np.asarray(test_rdms, dtype=float)
    if train.ndim == 1:
        train = train[None, :]
    if test.ndim == 1:
        test = test[None, :]
    if train.ndim != 2 or test.ndim != 2 or train.shape[1] != test.shape[1]:
        raise ValueError("train_rdms and test_rdms must have the same pair dimension")
    if (
        not train.size
        or not test.size
        or not np.isfinite(train).all()
        or not np.isfinite(test).all()
    ):
        raise ValueError("RDM arrays must be non-empty and finite")
    if not alphas or any(not np.isfinite(a) or a < 0 for a in alphas):
        raise ValueError("alphas must be non-empty, finite and nonnegative")
    train_ids = _group_ids(train_groups, len(train), "train")
    test_ids = _group_ids(test_groups, len(test), "test")
    if set(train_ids) & set(test_ids):
        raise ValueError("train/test group overlap: independent-unit leakage")
    train = group_means(train, train_ids)
    if len(train) < 3:
        raise ValueError("at least three independent training groups required for calibration")
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
            centered = matrix[:, active] - matrix[:, active].mean(axis=0)
            gram = centered.T @ centered
            effective_df = 1.0 + float(
                np.trace(gram @ np.linalg.pinv(gram + alpha * np.eye(len(gram))))
            )
        else:
            effective_df = 1.0
    # Never estimate predictive noise from in-sample residuals (especially M5).
    calibration_errors = []
    for held_out in range(len(train)):
        fit_rows = np.delete(train, held_out, axis=0)
        if architecture == "M5":
            inner_prediction = fit_rows.mean(axis=0)
        else:
            inner_alpha = _select_alpha(matrix, fit_rows, alphas)
            inner_intercept, inner_weights = nonnegative_ridge(
                matrix, fit_rows.mean(axis=0), alpha=inner_alpha
            )
            inner_prediction = inner_intercept + matrix @ inner_weights
        calibration_errors.append(np.square(train[held_out] - inner_prediction))
    floor = np.finfo(float).eps * max(float(np.mean(np.square(train))), 1.0)
    variance = max(float(np.mean(calibration_errors)), floor)
    replicate_scores = -0.5 * np.mean(
        np.square(test - prediction[None, :]) / variance + log(2 * pi * variance), axis=1
    )
    group_test = group_means(test, test_ids)
    grouped_scores = -0.5 * np.mean(
        np.square(group_test - prediction[None, :]) / variance + log(2 * pi * variance), axis=1
    )
    mse = float(np.mean(np.square(group_test - prediction[None, :])))
    return ArchitectureScore(
        architecture=architecture,
        log_score=float(grouped_scores.mean()),
        mean_squared_error=mse,
        alpha=alpha,
        effective_df=effective_df,
        intercept=intercept,
        weights={name: float(value) for name, value in zip(names, weights, strict=True)},
        residual_variance=variance,
        predictions=prediction,
        replicate_log_scores=replicate_scores,
        group_log_scores=grouped_scores,
    )


def _group_ids(groups: Sequence[str] | None, size: int, prefix: str) -> list[str]:
    ids = list(groups) if groups is not None else [f"{prefix}-{i}" for i in range(size)]
    if len(ids) != size or any(not isinstance(g, str) or not g.strip() for g in ids):
        raise ValueError("group IDs must be non-empty strings, one per RDM row")
    return ids


def group_means(values: ArrayLike, groups: Sequence[str]) -> NDArray[np.float64]:
    """Average rows per independent ID, preserving first-seen order and input units.

    No fitting or cross-split information is used; call separately on each split.
    """
    data = np.asarray(values, dtype=float)
    ids = _group_ids(groups, len(data), "group")
    if data.ndim != 2 or not data.size or not np.isfinite(data).all():
        raise ValueError("values must be a non-empty finite rows-by-features matrix")
    return np.stack([data[np.asarray(ids) == group].mean(axis=0) for group in dict.fromkeys(ids)])


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
