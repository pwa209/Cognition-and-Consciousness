"""Ordinal experience-measurement primitives."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def ordered_logit_probabilities(latent: ArrayLike, thresholds: ArrayLike) -> NDArray[np.float64]:
    """Return category probabilities under a cumulative ordered-logit link."""

    eta = np.asarray(latent, dtype=float)
    cuts = np.asarray(thresholds, dtype=float)
    if eta.ndim != 1 or cuts.ndim != 1 or len(cuts) < 1:
        raise ValueError("latent and thresholds must be one-dimensional")
    if not np.all(np.diff(cuts) > 0):
        raise ValueError("thresholds must be strictly increasing")
    cumulative = 1.0 / (1.0 + np.exp(-(cuts[None, :] - eta[:, None])))
    padded = np.column_stack([np.zeros(len(eta)), cumulative, np.ones(len(eta))])
    probabilities = np.diff(padded, axis=1)
    return probabilities / probabilities.sum(axis=1, keepdims=True)


def empirical_ordered_thresholds(ratings: ArrayLike) -> NDArray[np.float64]:
    """Initialize ordered-logit thresholds from empirical cumulative frequencies."""

    values = np.asarray(ratings)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("ratings must be a non-empty vector")
    levels, counts = np.unique(values, return_counts=True)
    if len(levels) < 2:
        raise ValueError("at least two ordinal levels are required")
    cumulative = np.cumsum(counts)[:-1] / counts.sum()
    cumulative = np.clip(cumulative, 1e-6, 1 - 1e-6)
    return np.log(cumulative / (1 - cumulative))

