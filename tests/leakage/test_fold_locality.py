from __future__ import annotations

import numpy as np

from factorcon.stats.transforms import FoldStandardizer, NuisanceResidualizer


def test_standardizer_does_not_learn_test_distribution() -> None:
    train = np.array([[0.0], [1.0], [2.0]])
    test = np.array([[100.0], [101.0]])
    transform = FoldStandardizer().fit(train)
    assert transform.mean_ is not None
    assert transform.mean_[0] == 1.0
    transformed_test = transform.transform(test)
    assert transformed_test.mean() > 100.0


def test_nuisance_coefficients_are_unchanged_by_test_targets() -> None:
    nuisance_train = np.arange(10.0)[:, None]
    targets_train = np.column_stack([2 * nuisance_train[:, 0], -nuisance_train[:, 0]])
    model = NuisanceResidualizer(alpha=1e-9).fit(nuisance_train, targets_train)
    before = model.coefficients_.copy()  # type: ignore[union-attr]
    model.transform(np.array([[100.0], [200.0]]), np.array([[999.0, -999.0], [999.0, -999.0]]))
    assert np.array_equal(before, model.coefficients_)

