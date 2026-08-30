"""Reliable subspace-orientation statistics."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def orthonormal_basis(vectors: ArrayLike, tolerance: float = 1e-10) -> NDArray[np.float64]:
    """Return an orthonormal basis after dropping numerically null directions."""

    matrix = np.asarray(vectors, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix[:, None]
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("vectors must be a finite matrix")
    u, singular, _ = np.linalg.svd(matrix, full_matrices=False)
    keep = singular > tolerance * max(1.0, singular[0] if len(singular) else 1.0)
    if not np.any(keep):
        raise ValueError("vectors do not contain a stable nonzero direction")
    return u[:, keep]


def principal_angles(left: ArrayLike, right: ArrayLike) -> NDArray[np.float64]:
    """Return principal angles in degrees between column subspaces."""

    a = orthonormal_basis(left)
    b = orthonormal_basis(right)
    singular = np.linalg.svd(a.T @ b, compute_uv=False)
    singular = np.clip(singular, 0.0, 1.0)
    return np.degrees(np.arccos(singular))

