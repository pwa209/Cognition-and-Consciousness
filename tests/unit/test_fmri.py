from __future__ import annotations

import numpy as np

from factorcon.fmri.glm import fit_runwise_glm


def test_runwise_glm_recovers_condition_beta() -> None:
    rng = np.random.default_rng(10)
    condition = rng.normal(size=(100, 2))
    confounds = rng.normal(size=(100, 3))
    true_beta = np.array([[2.0, -1.0], [0.5, 3.0]])
    signals = condition @ true_beta + confounds @ rng.normal(size=(3, 2)) + rng.normal(scale=0.01, size=(100, 2))
    result = fit_runwise_glm(signals, condition, confounds)
    assert np.allclose(result.betas, true_beta, atol=0.03)
    assert result.rank == 6

