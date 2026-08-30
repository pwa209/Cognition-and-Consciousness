"""Formal design components for M0-M5."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

ARCHITECTURES = {
    "M0": "unitary_global_state",
    "M1": "experience_gating",
    "M2": "cognitive_access",
    "M3": "report_bottleneck",
    "M4": "factorized_interactive",
    "M5": "saturated_predictable_ceiling",
}

CONSTRUCT_ORDER = ("E", "A", "R", "K_content", "K_memory", "K_task", "K_volition", "S")
K_NAMES = ("K_content", "K_memory", "K_task", "K_volition")


def _standardize(value: ArrayLike) -> NDArray[np.float64]:
    vector = np.asarray(value, dtype=float)
    if vector.ndim != 1 or not np.isfinite(vector).all():
        raise ValueError("construct columns must be finite one-dimensional arrays")
    scale = float(vector.std())
    return (vector - vector.mean()) / scale if scale > np.finfo(float).eps else vector * 0.0


def _validated_design(design: Mapping[str, ArrayLike]) -> dict[str, NDArray[np.float64]]:
    if not design:
        raise ValueError("design cannot be empty")
    result = {name: _standardize(value) for name, value in design.items()}
    lengths = {len(value) for value in result.values()}
    if len(lengths) != 1 or next(iter(lengths)) < 3:
        raise ValueError("all design columns must have equal length >= 3")
    return result


def _interaction(left: NDArray[np.float64], right: NDArray[np.float64]) -> NDArray[np.float64]:
    return _standardize(left * right)


def component_design(
    architecture: str, design: Mapping[str, ArrayLike]
) -> dict[str, NDArray[np.float64]]:
    """Return condition-level component vectors for one candidate architecture.

    The vectors define covariance/RDM components; their nonnegative weights are learned
    only from training partitions. M5 is handled as a pairwise saturated ceiling by the
    evaluator and therefore returns no construct vectors.
    """

    if architecture not in ARCHITECTURES:
        raise ValueError(f"Unknown architecture: {architecture}")
    columns = _validated_design(design)
    e = columns.get("E")
    a = columns.get("A")
    r = columns.get("R")
    s = columns.get("S")
    ks = {name: columns[name] for name in K_NAMES if name in columns}

    if architecture == "M5":
        return {}
    if architecture == "M0":
        global_columns = [columns[name] for name in CONSTRUCT_ORDER if name in columns and name != "S"]
        if not global_columns:
            raise ValueError("M0 requires at least one E/K/A/R construct")
        result = {"G": _standardize(np.mean(global_columns, axis=0))}
        if s is not None:
            result["S"] = s
        return result
    if architecture == "M1":
        if e is None or not ks:
            raise ValueError("M1 requires E and at least one K component")
        gate = 1.0 / (1.0 + np.exp(-e))
        result = {"E": e, **{f"gate({name})": _standardize(gate * value) for name, value in ks.items()}}
        if a is not None:
            result["A"] = a
        if r is not None:
            result["R"] = r
        if s is not None:
            result["S"] = s
        return result
    if architecture == "M2":
        if not ks:
            raise ValueError("M2 requires at least one K component")
        access = _standardize(np.mean(list(ks.values()), axis=0))
        result = {"K_access": access}
        if a is not None:
            result["A"] = a
            result["E_within_access_A"] = _standardize(access + a)
        else:
            result["E_within_access_A"] = access
        if r is not None:
            result["R"] = r
        if s is not None:
            result["S"] = s
        return result
    if architecture == "M3":
        if r is None:
            raise ValueError("M3 requires R")
        result = {"R": r}
        if e is not None:
            result["E:R"] = _interaction(e, r)
        result.update({f"{name}:R": _interaction(value, r) for name, value in ks.items()})
        if s is not None:
            result["S"] = s
        return result

    result = {name: columns[name] for name in CONSTRUCT_ORDER if name in columns}
    interaction_pairs = (
        ("E", "A"),
        ("E", "K_content"),
        ("E", "K_memory"),
        ("A", "K_volition"),
        ("K_task", "R"),
    )
    for left, right in interaction_pairs:
        if left in columns and right in columns:
            result[f"{left}:{right}"] = _interaction(columns[left], columns[right])
    return result

