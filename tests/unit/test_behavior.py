from __future__ import annotations

import numpy as np

from factorcon.behavior.logistic import LogisticCalibrator
from factorcon.behavior.ordinal import ordered_logit_probabilities


def test_ordered_probabilities_are_normalized_and_ordered() -> None:
    latent = np.array([-2.0, 0.0, 2.0])
    probabilities = ordered_logit_probabilities(latent, [-1.0, 0.5, 1.5])
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert np.argmax(probabilities[0]) < np.argmax(probabilities[-1])


def test_logistic_calibrator_separates_simple_data() -> None:
    x = np.array([[-2.0], [-1.0], [-0.5], [0.5], [1.0], [2.0]])
    y = np.array([0, 0, 0, 1, 1, 1])
    model = LogisticCalibrator(alpha=0.1).fit(x, y)
    prediction = model.predict_probability(x)
    assert prediction[:3].max() < prediction[3:].min()
