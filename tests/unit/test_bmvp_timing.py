"""Synthetic scanner-trigger alignment fixtures; no participant material."""

from __future__ import annotations

import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.bmvp_timing import align_report_mri_timing
from scripts.alliance.bmvp_timing_pilot import dicom_time_seconds


def fixture() -> tuple[bytes, bytes]:
    """Two 12-volume runs with three task trials and two pretask triggers."""
    log = []
    csv = ["TRIAL TYPE,Trial start time,BLOCK NUMBER"]
    for block, start in ((1, 100.0), (2, 200.0)):
        for index in range(12):
            log.append(f"{start + index:.4f} \tDATA \tKeypress: 5")
        for onset in (start + 2.01, start + 4.0, start + 8.0):
            csv.append(f"MOVIE,{onset},{block}")
    return ("\n".join(log) + "\n").encode(), ("\n".join(csv) + "\n").encode()


def align(log: bytes, csv: bytes) -> tuple:
    """Run the synthetic alignment with fixture-specific counts and TR units."""
    return align_report_mri_timing(
        log,
        csv,
        expected_runs=2,
        expected_volumes_per_run=12,
        expected_task_trials_per_run=3,
        expected_pretrial_triggers=2,
    )


def test_exact_run_mapping_and_source_clock() -> None:
    """Pretask scanner triggers define the non-neural event time origin."""
    log, csv = fixture()
    results = align(log, csv)
    assert [(x.block, x.trigger_count, x.task_trials) for x in results] == [
        (1, 12, 3), (2, 12, 3)
    ]
    assert results[0].first_trial_onset_seconds == pytest.approx(2.01)
    assert results[1].first_trigger_seconds == 200


def test_dropped_trigger_rejects_run() -> None:
    """A missing trigger cannot silently shift all later event onsets."""
    log, csv = fixture()
    with pytest.raises(IntegrityError, match="train count"):
        align(log.replace(b"105.0000 \tDATA \tKeypress: 5\n", b""), csv)


def test_wrong_block_or_onset_rejects_run() -> None:
    """Block mislabeling and pretask offset changes are integrity failures."""
    log, csv = fixture()
    with pytest.raises(IntegrityError, match="identities"):
        align(log, csv.replace(b"MOVIE,202.01,2", b"MOVIE,202.01,3"))
    with pytest.raises(IntegrityError, match="expected trigger index"):
        align(log, csv.replace(b"MOVIE,102.01,1", b"MOVIE,103.01,1"))


def test_nonmonotonic_triggers_and_bad_expectation_reject() -> None:
    """Neither malformed logs nor impossible scanner parameters enter P04."""
    log, csv = fixture()
    with pytest.raises(IntegrityError, match="nonmonotonic"):
        align(b"0 \tDATA \tKeypress: 5\n0 \tDATA \tKeypress: 5\n", csv)
    with pytest.raises(ValueError, match="expectations"):
        align_report_mri_timing(log, csv, expected_volumes_per_run=2, expected_pretrial_triggers=1)


def test_dicom_clock_formats_and_bounds() -> None:
    """Both official DICOM time renderings retain second precision and validity."""
    assert dicom_time_seconds("1:02:03.25") == pytest.approx(3723.25)
    assert dicom_time_seconds("010203.25") == pytest.approx(3723.25)
    with pytest.raises(ValueError):
        dicom_time_seconds("25:02:03")
