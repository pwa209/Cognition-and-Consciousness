"""Pure feature-pattern assembly with independent calibration whitening."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from numpy.typing import NDArray

from factorcon.models.generative import PatternData


def whiten_patterns(
    data: PatternData,
    calibration_residuals: NDArray[np.float64],
    *,
    calibration_ids: tuple[str, ...],
    ridge_fraction: float = 0.1,
) -> PatternData:
    """Whiten channels using independent residual rows x features (source units).

    Input patterns are group x partition x condition x feature beta/epoch summaries,
    NOT raw continuous recordings. Output is dimensionless residual-SD units. Ridge
    fraction is externally declared, never selected on evaluation scores. Trial-design
    covariance remains the supplied known noise matrix, not inferred from test betas.
    Caller must also check calibration disjointness across the complete collection.
    """
    data.validate()
    residuals = np.asarray(calibration_residuals, dtype=float)
    if (
        residuals.ndim != 2
        or residuals.shape[0] < 3
        or residuals.shape[1] != data.patterns.shape[-1]
        or not np.isfinite(residuals).all()
        or not 0 < ridge_fraction <= 1
    ):
        raise ValueError("finite independent residual matrix and ridge fraction in (0,1] required")
    if not calibration_ids or set(calibration_ids) & set(data.group_ids):
        raise ValueError("independent calibration IDs required; no neural subject overlap")
    centered = residuals - residuals.mean(axis=0)
    covariance = centered.T @ centered / (len(centered) - 1)
    scale = float(np.trace(covariance) / len(covariance))
    if scale <= 0:
        raise ValueError("calibration residual variance is zero")
    covariance = (1 - ridge_fraction) * covariance + ridge_fraction * scale * np.eye(
        len(covariance)
    )
    eig, vectors = np.linalg.eigh(covariance)
    transform = (vectors * eig**-0.5) @ vectors.T
    return replace(
        data,
        patterns=data.patterns @ transform,
        calibration_ids=tuple(sorted(set(data.calibration_ids) | set(calibration_ids))),
    )
