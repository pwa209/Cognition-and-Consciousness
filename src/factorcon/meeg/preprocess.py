"""MNE-based sensor preprocessing with condition-blind rejection parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def preprocess_raw(
    bids_path: str | Path,
    *,
    highpass_hz: float = 0.1,
    lowpass_hz: float = 150.0,
    resample_hz: float = 500.0,
    line_frequency_hz: float = 50.0,
) -> Any:
    """Load BIDS M/EEG, filter/notch/resample, and return an in-memory MNE Raw.

    Bad channels and ICA components require a separate condition-blind QC record; this
    function intentionally does not infer or remove components from scientific labels.
    """

    try:
        from mne_bids import BIDSPath, read_raw_bids  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("preprocess_raw requires the 'neuro' optional dependencies") from exc
    path = Path(bids_path)
    entities = BIDSPath(root=path.parent, basename=path.name)
    raw = read_raw_bids(entities, verbose="ERROR")
    harmonics = [line_frequency_hz * factor for factor in range(1, int(lowpass_hz // line_frequency_hz) + 1)]
    raw.load_data().notch_filter(harmonics).filter(highpass_hz, lowpass_hz)
    raw.resample(resample_hz)
    return raw

