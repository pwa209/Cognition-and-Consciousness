import numpy as np
import pytest

from factorcon.stats.multiplicity import holm_adjust, max_t_sign_flip, tost_equivalence


def test_holm_exact_and_no_silent_missing_endpoints():
    np.testing.assert_allclose(
        holm_adjust(np.asarray([0.01, 0.04, 0.03, 0.5])), [0.04, 0.09, 0.09, 0.5]
    )
    with pytest.raises(ValueError):
        holm_adjust(np.asarray([0.01, np.nan]))


def test_shared_max_t_respects_identical_endpoints():
    x = np.random.default_rng(2).normal(size=20)
    result = max_t_sign_flip(np.column_stack([x, x]), permutations=199)
    assert result["adjusted_p"][0] == result["adjusted_p"][1]


def test_equivalence_requires_precision_not_nonsignificance():
    narrow = np.linspace(-0.05, 0.05, 30)
    assert tost_equivalence(narrow, 0.1)["equivalent"]
    assert not tost_equivalence(narrow * 100, 0.1)["equivalent"]
