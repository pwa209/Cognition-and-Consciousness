from __future__ import annotations

import numpy as np

from factorcon.stats.splits import deterministic_partition


def test_named_partitions_never_split_subjects() -> None:
    groups = np.repeat([f"participant-{index}" for index in range(50)], 7)
    smaller, larger = deterministic_partition(groups, fraction=0.2, seed=260830)
    assert not set(groups[smaller]) & set(groups[larger])
    assert len(smaller) + len(larger) == len(groups)

