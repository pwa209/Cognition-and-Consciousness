from __future__ import annotations

import numpy as np

from factorcon.features.complexity import median_binarized_lz, permutation_entropy
from factorcon.features.connectivity import correlation_connectivity, participation_coefficient
from factorcon.features.spectral import (
    aperiodic_loglog_slope,
    power_spectral_density,
    relative_bandpower,
    spectral_entropy,
)


def test_spectral_features_identify_ten_hz_signal() -> None:
    sampling_rate = 200.0
    time = np.arange(0, 5, 1 / sampling_rate)
    signal = np.sin(2 * np.pi * 10 * time)[None, :]
    frequencies, psd = power_spectral_density(signal, sampling_rate)
    bands = relative_bandpower(frequencies, psd, {"alpha": (8, 13), "beta": (15, 30)})
    assert bands["alpha"][0] > bands["beta"][0]
    assert 0 <= spectral_entropy(psd)[0] <= 1
    assert np.isfinite(aperiodic_loglog_slope(frequencies, psd)).all()


def test_complexity_functions_are_finite() -> None:
    rng = np.random.default_rng(8)
    signal = rng.normal(size=1000)
    assert np.isfinite(median_binarized_lz(signal))
    assert 0 <= permutation_entropy(signal, order=4) <= 1


def test_connectivity_and_participation_contracts() -> None:
    rng = np.random.default_rng(9)
    time_series = rng.normal(size=(200, 4))
    matrix = correlation_connectivity(time_series)
    assert matrix.shape == (4, 4)
    assert np.allclose(matrix, matrix.T)
    participation = participation_coefficient(matrix, [0, 0, 1, 1])
    assert participation.shape == (4,)

