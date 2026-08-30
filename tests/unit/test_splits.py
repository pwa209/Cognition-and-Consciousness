from __future__ import annotations

import numpy as np

from factorcon.stats.splits import deterministic_group_folds, repeated_group_folds


def test_group_isolation_and_determinism() -> None:
    groups = np.repeat([f"sub-{index:02d}" for index in range(20)], 4)
    first = deterministic_group_folds(groups, 5, seed=19)
    second = deterministic_group_folds(groups, 5, seed=19)
    assert len(first) == 5
    for left, right in zip(first, second, strict=True):
        assert np.array_equal(left.train, right.train)
        assert np.array_equal(left.test, right.test)
        assert not set(groups[left.train]) & set(groups[left.test])


def test_repeats_derive_distinct_allocations() -> None:
    groups = np.repeat([f"sub-{index:02d}" for index in range(30)], 2)
    folds = repeated_group_folds(groups, 5, 3, seed=91)
    assert len(folds) == 15
    assert any(not np.array_equal(folds[0].test, fold.test) for fold in folds[5:])
