from __future__ import annotations

import numpy as np

from factorcon.features.rdm import crossnobis_rdm, vectorize_rdm


def test_crossnobis_recovers_separated_conditions() -> None:
    rng = np.random.default_rng(4)
    rows = []
    conditions = []
    partitions = []
    for partition in ("run-1", "run-2", "run-3"):
        for condition, mean in (("a", -1.0), ("b", 1.0)):
            for _ in range(20):
                rows.append(rng.normal(mean, 0.4, size=8))
                conditions.append(condition)
                partitions.append(partition)
    levels, rdm = crossnobis_rdm(rows, conditions, partitions)
    assert levels == ["a", "b"]
    assert vectorize_rdm(rdm)[0] > 0


def test_vectorizer_retains_negative_values() -> None:
    matrix = np.array([[0.0, -0.25], [-0.25, 0.0]])
    assert vectorize_rdm(matrix).tolist() == [-0.25]
