"""Static connectivity and graph summaries with explicit dimensional contracts."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def correlation_connectivity(timeseries: ArrayLike) -> NDArray[np.float64]:
    """Return a Fisher-z correlation matrix from samples-by-nodes time series."""

    data = np.asarray(timeseries, dtype=float)
    if data.ndim != 2 or data.shape[0] < 4 or data.shape[1] < 2:
        raise ValueError("timeseries must be samples-by-at-least-two-nodes")
    if not np.isfinite(data).all():
        raise ValueError("timeseries must be finite")
    correlation = np.corrcoef(data, rowvar=False)
    np.fill_diagonal(correlation, 0.0)
    clipped = np.clip(correlation, -0.999999, 0.999999)
    fisher = np.arctanh(clipped)
    np.fill_diagonal(fisher, 0.0)
    return fisher


def participation_coefficient(weights: ArrayLike, communities: ArrayLike) -> NDArray[np.float64]:
    """Return weighted participation coefficients for nodes across fixed communities."""

    matrix = np.asarray(weights, dtype=float)
    labels = np.asarray(communities)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or len(labels) != len(matrix):
        raise ValueError("weights must be square and communities node-long")
    absolute = np.abs(matrix.copy())
    np.fill_diagonal(absolute, 0.0)
    strength = absolute.sum(axis=1)
    result = np.zeros(len(matrix), dtype=float)
    for community in np.unique(labels):
        within = absolute[:, labels == community].sum(axis=1)
        result += np.square(np.divide(within, strength, out=np.zeros_like(within), where=strength > 0))
    return 1.0 - result

