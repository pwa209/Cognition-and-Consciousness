"""Synthetic rows shaped like the read-only verified ds003927 event header."""

from pathlib import Path

import numpy as np
import pytest
from scipy.signal import periodogram

from factorcon.config import DatasetConfig
from factorcon.errors import IntegrityError
from factorcon.features.spectral import power_spectral_density
from factorcon.io.bids import read_events
from factorcon.pipeline.harmonize import harmonize_bids_events


def event_fixture(tmp_path):
    source = tmp_path / "sub-fixture" / "func" / "sub-fixture_task-example_run-1_events.tsv"
    source.parent.mkdir(parents=True)
    source.write_text(
        "onset\tduration\tvisibility\ttargets\tlabels\tpaths\tresponse\tcorrect\tRT_response\toptions\n"
        "-1\tn/a\tunconscious\tLiving_Things\tobject_a\t../../untrusted\t1\t1\t150\t'V_nV'\n"
        "1\t0.5\tn/a\tNonliving_Things\tobject_b\timage_b\tn/a\tn/a\tn/a\tn/a\n",
        encoding="utf-8-sig",
    )
    return source


def config(expected=1):
    return DatasetConfig(
        Path("fixture.yaml"), {"family": "masked_content_fmri", "expected_participants": expected}
    )


def test_verified_columns_preserve_source_label_not_E_zero(tmp_path):
    event_fixture(tmp_path)
    records, counts = harmonize_bids_events(config(), tmp_path)
    assert counts == {"participants": 1, "event_files": 1, "records": 2}
    assert records[0].observed_experience == "unconscious"
    assert records[0].metadata["visibility_ordinal_code"] == 0
    assert not records[0].metadata["ordinal_code_is_E_probability"]
    assert records[0].stimulus_features["category"] == "Living_Things"
    assert records[0].stimulus_id == "../../untrusted"  # Stored as data; never opened.
    assert records[0].response_time is None  # Units need verification.
    assert records[1].report_availability == "unknown"
    assert records[1].observed_experience is None


def test_masked_counts_and_schema_mismatches_stop_affected_adapter(tmp_path):
    source = event_fixture(tmp_path)
    with pytest.raises(IntegrityError, match="participant count"):
        harmonize_bids_events(config(2), tmp_path)
    source.write_text(
        source.read_text(encoding="utf-8-sig")
        .replace("glimpse", "invalid")
        .replace("unconscious", "invalid"),
        encoding="utf-8",
    )
    with pytest.raises(IntegrityError, match="visibility"):
        harmonize_bids_events(config(), tmp_path)


def test_event_path_resolution_cannot_escape_root(tmp_path, monkeypatch):
    source = event_fixture(tmp_path)
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        return (
            tmp_path.parent / "outside.tsv" if path == source else original(path, *args, **kwargs)
        )

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(IntegrityError, match="outside"):
        harmonize_bids_events(config(), tmp_path)


@pytest.mark.parametrize("field", ["onset", "duration"])
@pytest.mark.parametrize("value", ["NaN", "inf", "-inf"])
def test_nonfinite_timing_rejected(tmp_path, field, value):
    path = tmp_path / "events.tsv"
    values = {"onset": "-1", "duration": "0"}
    values[field] = value
    path.write_text(f"onset\tduration\n{values['onset']}\t{values['duration']}\n")
    with pytest.raises(IntegrityError):
        read_events(path)


@pytest.mark.parametrize("samples", [100, 101])
def test_one_sided_psd_matches_scipy_for_even_and_odd_lengths(samples):
    signal = np.random.default_rng(8).normal(size=(2, samples))
    f, power = power_spectral_density(signal, 200)
    reference_f, reference = periodogram(
        signal, 200, window=np.hanning(samples), detrend="constant"
    )
    np.testing.assert_allclose(f, reference_f)
    np.testing.assert_allclose(power, reference, rtol=1e-12, atol=1e-15)
