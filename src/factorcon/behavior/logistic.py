"""Dependency-free fold-local logistic calibration for no-report probabilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(slots=True)
class LogisticCalibrator:
    """Ridge logistic model used only across explicitly independent calibration folds."""

    alpha: float = 1.0
    max_iter: int = 200
    tolerance: float = 1e-8
    coefficients_: NDArray[np.float64] | None = None

    def fit(self, x: ArrayLike, y: ArrayLike) -> LogisticCalibrator:
        features = np.asarray(x, dtype=float)
        labels = np.asarray(y, dtype=float)
        if features.ndim != 2 or labels.shape != (len(features),):
            raise ValueError("x must be rows-by-features and y row-long")
        if not set(np.unique(labels)).issubset({0.0, 1.0}):
            raise ValueError("logistic labels must be binary")
        design = np.column_stack([np.ones(len(features)), features])
        beta = np.zeros(design.shape[1], dtype=float)
        penalty = np.eye(len(beta)) * self.alpha
        penalty[0, 0] = 0.0
        for _ in range(self.max_iter):
            linear = np.clip(design @ beta, -30.0, 30.0)
            probability = 1.0 / (1.0 + np.exp(-linear))
            weight = np.clip(probability * (1 - probability), 1e-8, None)
            gradient = design.T @ (probability - labels) + penalty @ beta
            hessian = design.T @ (design * weight[:, None]) + penalty
            update = np.linalg.solve(hessian, gradient)
            beta -= update
            if np.max(np.abs(update)) < self.tolerance:
                break
        self.coefficients_ = beta
        return self

    def predict_probability(self, x: ArrayLike) -> NDArray[np.float64]:
        features = np.asarray(x, dtype=float)
        if features.ndim != 2 or self.coefficients_ is None:
            raise RuntimeError("calibrator is not fit or x is invalid")
        linear = np.clip(
            np.column_stack([np.ones(len(features)), features]) @ self.coefficients_, -30, 30
        )
        return 1.0 / (1.0 + np.exp(-linear))
