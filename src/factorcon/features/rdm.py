"""Crossvalidated representational dissimilarity primitives."""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from itertools import permutations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def vectorize_rdm(matrix: ArrayLike) -> NDArray[np.float64]:
    """Return the strict upper triangle of a square RDM without truncating negatives."""

    rdm = np.asarray(matrix, dtype=float)
    if rdm.ndim != 2 or rdm.shape[0] != rdm.shape[1]:
        raise ValueError("RDM must be square")
    return rdm[np.triu_indices(len(rdm), k=1)]


def design_rdm(column: ArrayLike, *, categorical: bool = False) -> NDArray[np.float64]:
    """Build a squared-difference (or categorical mismatch) model RDM."""

    values = np.asarray(column)
    if values.ndim != 1:
        raise ValueError("column must be one-dimensional")
    if categorical:
        return (values[:, None] != values[None, :]).astype(float)
    numeric = values.astype(float)
    scale = numeric.std()
    if scale > np.finfo(float).eps:
        numeric = (numeric - numeric.mean()) / scale
    else:
        numeric = numeric - numeric.mean()
    return np.square(numeric[:, None] - numeric[None, :])


def shrinkage_precision(residuals: ArrayLike, shrinkage: float = 0.1) -> NDArray[np.float64]:
    """Estimate a positive semidefinite shrinkage precision matrix."""

    data = np.asarray(residuals, dtype=float)
    if data.ndim != 2 or len(data) < 2 or not 0 <= shrinkage <= 1:
        raise ValueError("residuals must be a matrix and shrinkage in [0, 1]")
    covariance = np.atleast_2d(np.cov(data, rowvar=False, ddof=1))
    target = np.eye(covariance.shape[0]) * float(np.trace(covariance) / covariance.shape[0])
    regularized = (1 - shrinkage) * covariance + shrinkage * target
    return np.linalg.pinv(regularized, hermitian=True)


def crossnobis_rdm(
    patterns: ArrayLike,
    conditions: Sequence[Hashable],
    partitions: Sequence[Hashable],
    *,
    precision: ArrayLike | None = None,
) -> tuple[list[Hashable], NDArray[np.float64]]:
    """Estimate a crossvalidated Mahalanobis RDM from independent partitions.

    Every condition must appear in every partition. The precision matrix should be
    estimated from independent residuals; identity is used when omitted. Negative
    distances are retained because their null expectation is zero.
    """

    x = np.asarray(patterns, dtype=float)
    condition_array = np.asarray(conditions, dtype=object)
    partition_array = np.asarray(partitions, dtype=object)
    if x.ndim != 2 or len(x) != len(condition_array) or len(x) != len(partition_array):
        raise ValueError("patterns, conditions, and partitions must have equal rows")
    condition_levels = list(dict.fromkeys(conditions))
    partition_levels = list(dict.fromkeys(partitions))
    if len(condition_levels) < 2 or len(partition_levels) < 2:
        raise ValueError("at least two conditions and two independent partitions are required")
    means: dict[tuple[Hashable, Hashable], NDArray[np.float64]] = {}
    for partition in partition_levels:
        for condition in condition_levels:
            mask = (partition_array == partition) & (condition_array == condition)
            if not np.any(mask):
                raise ValueError(f"condition {condition!r} absent from partition {partition!r}")
            means[(partition, condition)] = x[mask].mean(axis=0)
    metric = np.eye(x.shape[1]) if precision is None else np.asarray(precision, dtype=float)
    if metric.shape != (x.shape[1], x.shape[1]):
        raise ValueError("precision has incompatible dimensions")
    result = np.zeros((len(condition_levels), len(condition_levels)), dtype=float)
    pairs = list(permutations(partition_levels, 2))
    for i, left in enumerate(condition_levels):
        for j in range(i + 1, len(condition_levels)):
            right = condition_levels[j]
            values = []
            for first, second in pairs:
                delta_first = means[(first, left)] - means[(first, right)]
                delta_second = means[(second, left)] - means[(second, right)]
                values.append(float(delta_first @ metric @ delta_second / x.shape[1]))
            result[i, j] = result[j, i] = float(np.mean(values))
    return condition_levels, result
