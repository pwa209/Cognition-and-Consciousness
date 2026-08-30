"""Source-free perturbational state-transition complexity summary."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def state_transition_complexity(
    evoked: ArrayLike,
    baseline: ArrayLike,
    *,
    threshold_sd: float = 2.0,
) -> float:
    """Count normalized spatiotemporal response-state transitions above baseline noise.

    This transparent summary is not represented as the published PCIst implementation;
    final PCIst analyses must call the version-pinned reference implementation and retain
    its provenance alongside this source-free sensitivity measure.
    """

    response = np.asarray(evoked, dtype=float)
    noise = np.asarray(baseline, dtype=float)
    if response.ndim != 2 or noise.ndim != 2 or response.shape[0] != noise.shape[0]:
        raise ValueError("evoked and baseline must be channels-by-time with equal channels")
    scale = np.std(noise, axis=1, ddof=1)
    scale = np.where(scale > np.finfo(float).eps, scale, 1.0)
    active = np.abs(response) > threshold_sd * scale[:, None]
    temporal = np.count_nonzero(np.diff(active.astype(np.int8), axis=1))
    spatial = np.count_nonzero(np.diff(active.astype(np.int8), axis=0))
    maximum = active.shape[0] * max(active.shape[1] - 1, 1) + max(active.shape[0] - 1, 1) * active.shape[1]
    return float((temporal + spatial) / maximum)

