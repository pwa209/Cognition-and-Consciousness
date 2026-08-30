"""Fold-local linear transforms and estimators."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _matrix(value: ArrayLike, name: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or len(array) == 0 or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a non-empty finite two-dimensional array")
    return array


@dataclass(slots=True)
class FoldStandardizer:
    """Column standardizer whose state must be fit from training rows only."""

    mean_: NDArray[np.float64] | None = None
    scale_: NDArray[np.float64] | None = None

    def fit(self, x: ArrayLike) -> "FoldStandardizer":
        data = _matrix(x, "x")
        self.mean_ = data.mean(axis=0)
        scale = data.std(axis=0, ddof=0)
        self.scale_ = np.where(scale > np.finfo(float).eps, scale, 1.0)
        return self

    def transform(self, x: ArrayLike) -> NDArray[np.float64]:
        data = _matrix(x, "x")
        if self.mean_ is None or self.scale_ is None:
            raise RuntimeError("FoldStandardizer is not fit")
        return (data - self.mean_) / self.scale_

    def fit_transform(self, x: ArrayLike) -> NDArray[np.float64]:
        return self.fit(x).transform(x)


@dataclass(slots=True)
class NuisanceResidualizer:
    """Ridge nuisance regression fit only on the training fold."""

    alpha: float = 1e-6
    coefficients_: NDArray[np.float64] | None = None

    def fit(self, nuisance: ArrayLike, targets: ArrayLike) -> "NuisanceResidualizer":
        z = _matrix(nuisance, "nuisance")
        y = _matrix(targets, "targets")
        if len(z) != len(y):
            raise ValueError("nuisance and targets must have equal rows")
        design = np.column_stack([np.ones(len(z)), z])
        penalty = np.eye(design.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coefficients_ = np.linalg.solve(design.T @ design + penalty, design.T @ y)
        return self

    def transform(self, nuisance: ArrayLike, targets: ArrayLike) -> NDArray[np.float64]:
        z = _matrix(nuisance, "nuisance")
        y = _matrix(targets, "targets")
        if self.coefficients_ is None:
            raise RuntimeError("NuisanceResidualizer is not fit")
        design = np.column_stack([np.ones(len(z)), z])
        return y - design @ self.coefficients_


@dataclass(slots=True)
class RidgeRegressor:
    """Multi-output ridge regression with an unpenalized intercept."""

    alpha: float = 1.0
    coefficients_: NDArray[np.float64] | None = None

    def fit(self, x: ArrayLike, y: ArrayLike) -> "RidgeRegressor":
        features = _matrix(x, "x")
        targets = _matrix(y, "y")
        if len(features) != len(targets):
            raise ValueError("x and y must have equal rows")
        design = np.column_stack([np.ones(len(features)), features])
        penalty = np.eye(design.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coefficients_ = np.linalg.solve(design.T @ design + penalty, design.T @ targets)
        return self

    def predict(self, x: ArrayLike) -> NDArray[np.float64]:
        features = _matrix(x, "x")
        if self.coefficients_ is None:
            raise RuntimeError("RidgeRegressor is not fit")
        return np.column_stack([np.ones(len(features)), features]) @ self.coefficients_


def haufe_patterns(
    x: ArrayLike, predictions: ArrayLike, weights: ArrayLike
) -> NDArray[np.float64]:
    """Transform linear encoding/decoding weights into activation patterns."""

    features = _matrix(x, "x")
    scores = _matrix(predictions, "predictions")
    weight_matrix = _matrix(weights, "weights")
    covariance_x = np.cov(features, rowvar=False)
    covariance_s = np.cov(scores, rowvar=False)
    covariance_s = np.atleast_2d(covariance_s)
    return covariance_x @ weight_matrix @ np.linalg.pinv(covariance_s)

