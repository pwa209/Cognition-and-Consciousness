from __future__ import annotations

import pytest

from factorcon.simulation import recover_architecture


@pytest.mark.parametrize("truth", ["M0", "M1", "M2", "M3", "M4"])
def test_each_theoretical_architecture_is_recovered(truth: str) -> None:
    result = recover_architecture(truth, seed=260830 + int(truth[1:]) * 1009)
    assert result.theory_winner == truth


def test_unitary_data_do_not_favor_factorized_model() -> None:
    result = recover_architecture("M0", seed=404)
    assert result.scores["M0"] > result.scores["M4"]


def test_factorized_data_recover_incremental_prediction() -> None:
    result = recover_architecture("M4", seed=505)
    assert result.scores["M4"] > max(result.scores[model] for model in ("M0", "M1", "M2", "M3"))

