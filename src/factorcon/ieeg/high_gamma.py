"""Broadband high-gamma extraction using sub-band Hilbert envelopes."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def high_gamma_envelope(
    signals: ArrayLike,
    sampling_rate_hz: float,
    *,
    bands: tuple[tuple[float, float], ...] = ((70, 90), (90, 110), (110, 130), (130, 150)),
    axis: int = -1,
) -> NDArray[np.float64]:
    """Return the mean log Hilbert envelope across high-gamma sub-bands."""

    try:
        from scipy.signal import butter, hilbert, sosfiltfilt  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("high_gamma_envelope requires the 'analysis' optional dependencies") from exc
    data = np.asarray(signals, dtype=float)
    nyquist = sampling_rate_hz / 2
    envelopes = []
    for low, high in bands:
        if not 0 < low < high < nyquist:
            raise ValueError(f"invalid high-gamma band {(low, high)} at fs={sampling_rate_hz}")
        sos = butter(4, [low / nyquist, high / nyquist], btype="bandpass", output="sos")
        filtered = sosfiltfilt(sos, data, axis=axis)
        envelopes.append(np.log(np.maximum(np.abs(hilbert(filtered, axis=axis)), np.finfo(float).tiny)))
    return np.mean(envelopes, axis=0)

