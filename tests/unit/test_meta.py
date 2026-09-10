from __future__ import annotations

from factorcon.stats.meta import random_effects_normal


def test_precision_weighted_random_effects_sensitivity() -> None:
    result = random_effects_normal([0.4, 0.2, 0.6, -0.1], [0.1, 0.2, 0.15, 0.3])
    assert result.family_count == 4
    assert result.ci_low < result.mean < result.ci_high
    assert result.prediction_low <= result.ci_low
    assert result.prediction_high >= result.ci_high
