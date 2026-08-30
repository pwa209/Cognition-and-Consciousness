"""Length-controlled spectral EEG/MEG feature extraction."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray


def power_spectral_density(
    signals: ArrayLike,
    sampling_rate_hz: float,
    *,
    axis: int = -1,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return Hann-window periodogram power and frequencies.

    Signals are in source amplitude units; PSD units are amplitude squared per Hz.
    Window length must be matched before comparing complexity/state conditions.
    """

    data = np.asarray(signals, dtype=float)
    if data.ndim < 1 or data.shape[axis] < 4 or sampling_rate_hz <= 0:
        raise ValueError("signals need at least four samples and positive sampling rate")
    if not np.isfinite(data).all():
        raise ValueError("signals must be finite")
    sample_count = data.shape[axis]
    window = np.hanning(sample_count)
    shape = [1] * data.ndim
    shape[axis] = sample_count
    centered = data - data.mean(axis=axis, keepdims=True)
    spectrum = np.fft.rfft(centered * window.reshape(shape), axis=axis)
    normalization = sampling_rate_hz * np.sum(window**2)
    power = np.square(np.abs(spectrum)) / normalization
    frequencies = np.fft.rfftfreq(sample_count, d=1.0 / sampling_rate_hz)
    return frequencies, power


def relative_bandpower(
    frequencies_hz: ArrayLike,
    psd: ArrayLike,
    bands_hz: Mapping[str, tuple[float, float]],
    *,
    axis: int = -1,
) -> dict[str, NDArray[np.float64]]:
    """Integrate each half-open band and divide by total positive-frequency power."""

    frequencies = np.asarray(frequencies_hz, dtype=float)
    power = np.asarray(psd, dtype=float)
    if power.shape[axis] != len(frequencies):
        raise ValueError("PSD frequency axis does not match frequencies")
    positive = frequencies > 0
    total = np.trapezoid(
        np.take(power, np.flatnonzero(positive), axis=axis), frequencies[positive], axis=axis
    )
    total = np.maximum(total, np.finfo(float).tiny)
    result: dict[str, NDArray[np.float64]] = {}
    for name, (low, high) in bands_hz.items():
        if not 0 <= low < high:
            raise ValueError(f"Invalid band {name}: {(low, high)}")
        mask = (frequencies >= low) & (frequencies < high)
        if mask.sum() < 2:
            raise ValueError(f"Band {name} has fewer than two frequency bins")
        band = np.trapezoid(
            np.take(power, np.flatnonzero(mask), axis=axis), frequencies[mask], axis=axis
        )
        result[name] = band / total
    return result


def aperiodic_loglog_slope(
    frequencies_hz: ArrayLike,
    psd: ArrayLike,
    *,
    low_hz: float = 2.0,
    high_hz: float = 40.0,
    axis: int = -1,
) -> NDArray[np.float64]:
    """Estimate a simple log-power/log-frequency slope over a fixed range."""

    frequencies = np.asarray(frequencies_hz, dtype=float)
    power = np.asarray(psd, dtype=float)
    mask = (frequencies >= low_hz) & (frequencies <= high_hz)
    if mask.sum() < 3 or power.shape[axis] != len(frequencies):
        raise ValueError("insufficient bins or incompatible PSD shape")
    x = np.log(frequencies[mask])
    x = x - x.mean()
    selected = np.take(power, np.flatnonzero(mask), axis=axis)
    y = np.log(np.maximum(selected, np.finfo(float).tiny))
    y = y - y.mean(axis=axis, keepdims=True)
    return np.sum(y * x, axis=axis) / np.sum(x**2)


def spectral_entropy(psd: ArrayLike, *, axis: int = -1) -> NDArray[np.float64]:
    """Return Shannon spectral entropy normalized to [0, 1]."""

    power = np.asarray(psd, dtype=float)
    probabilities = power / np.maximum(power.sum(axis=axis, keepdims=True), np.finfo(float).tiny)
    entropy = -np.sum(
        probabilities * np.log(np.maximum(probabilities, np.finfo(float).tiny)), axis=axis
    )
    return entropy / np.log(power.shape[axis])
