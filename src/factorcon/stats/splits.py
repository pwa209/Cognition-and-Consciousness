"""Deterministic grouped partitioning with optional group-level stratification."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Hashable, Sequence

import numpy as np

from factorcon.errors import IntegrityError


@dataclass(frozen=True, slots=True)
class Fold:
    """Train/test integer indices for one grouped fold."""

    train: np.ndarray
    test: np.ndarray
    repeat: int = 0
    index: int = 0


def _rank(seed: int, value: Hashable) -> str:
    return hashlib.sha256(f"{seed}|{value!r}".encode()).hexdigest()


def deterministic_group_folds(
    groups: Sequence[Hashable],
    n_splits: int,
    *,
    seed: int,
    strata: Sequence[Hashable] | None = None,
) -> list[Fold]:
    """Assign whole groups to deterministic folds, balanced within strata when supplied.

    All transforms downstream must be fit on ``Fold.train`` only. This function never
    observes scientific outcomes unless the caller explicitly supplies a declared stratum.
    """

    group_array = np.asarray(groups, dtype=object)
    if group_array.ndim != 1 or len(group_array) == 0:
        raise ValueError("groups must be a non-empty one-dimensional sequence")
    unique_groups = list(dict.fromkeys(groups))
    if n_splits < 2 or n_splits > len(unique_groups):
        raise ValueError("n_splits must be between 2 and the number of unique groups")

    group_strata: dict[Hashable, Hashable] = {}
    if strata is not None:
        if len(strata) != len(groups):
            raise ValueError("strata and groups must have equal length")
        for group, stratum in zip(groups, strata, strict=True):
            existing = group_strata.setdefault(group, stratum)
            if existing != stratum:
                raise IntegrityError(f"Group {group!r} spans multiple declared strata")
    else:
        group_strata = {group: "__all__" for group in unique_groups}

    buckets: dict[Hashable, list[Hashable]] = defaultdict(list)
    for group in unique_groups:
        buckets[group_strata[group]].append(group)
    fold_groups: list[set[Hashable]] = [set() for _ in range(n_splits)]
    offset = 0
    for stratum in sorted(buckets, key=repr):
        ordered = sorted(buckets[stratum], key=lambda item: _rank(seed, item))
        for position, group in enumerate(ordered):
            fold_groups[(offset + position) % n_splits].add(group)
        offset = (offset + len(ordered)) % n_splits

    folds: list[Fold] = []
    all_indices = np.arange(len(group_array), dtype=int)
    for index, test_groups in enumerate(fold_groups):
        mask = np.fromiter((group in test_groups for group in group_array), dtype=bool)
        test = all_indices[mask]
        train = all_indices[~mask]
        if len(test) == 0 or len(train) == 0:
            raise IntegrityError(f"Empty train/test set in fold {index}")
        if set(group_array[train]) & set(group_array[test]):
            raise IntegrityError(f"Group leakage in fold {index}")
        folds.append(Fold(train=train, test=test, index=index))
    return folds


def repeated_group_folds(
    groups: Sequence[Hashable],
    n_splits: int,
    repeats: int,
    *,
    seed: int,
    strata: Sequence[Hashable] | None = None,
) -> list[Fold]:
    """Create repeated deterministic grouped folds using independent derived seeds."""

    if repeats < 1:
        raise ValueError("repeats must be positive")
    result: list[Fold] = []
    for repeat in range(repeats):
        derived = int(hashlib.sha256(f"{seed}|repeat|{repeat}".encode()).hexdigest()[:16], 16)
        for fold in deterministic_group_folds(groups, n_splits, seed=derived, strata=strata):
            result.append(Fold(fold.train, fold.test, repeat=repeat, index=fold.index))
    return result


def deterministic_partition(
    groups: Sequence[Hashable], *, fraction: float, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Split whole groups into a named smaller partition and its complement."""

    if not 0 < fraction < 1:
        raise ValueError("fraction must lie strictly between zero and one")
    unique = sorted(set(groups), key=lambda value: _rank(seed, value))
    count = min(len(unique) - 1, max(1, round(fraction * len(unique))))
    small_groups = set(unique[:count])
    array = np.asarray(groups, dtype=object)
    small = np.flatnonzero(np.fromiter((item in small_groups for item in array), dtype=bool))
    large = np.flatnonzero(np.fromiter((item not in small_groups for item in array), dtype=bool))
    return small, large

