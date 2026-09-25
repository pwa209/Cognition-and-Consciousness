"""Tiny synthetic BMVP CSV/TAR fixtures; never include participant source rows."""

from __future__ import annotations

import io
import tarfile

import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.bmvp_csv import parse_bmvp_trial_csv, scan_bmvp_csv_archive


REPORT = (
    "TRIAL TYPE,Trial start time,Perception answer,Perception keypress,Face shown,Face opacity\n"
    "NOISE CALIBRATION,,1,,True,0.5\n"
    "NOISE,12.25,0,1,True,0.4\n"
    ",,,,,\n"
).encode()
NO_REPORT = (
    "TRIAL TYPE,Trial start time,Perception answer,Perception keypress,Task Relevant,"
    "Center Face shown,Center Face opacity,Quadrant Face shown,Quadrant Face opacity\n"
    "NOISE CALIBRATION,,1,,,,,,\n"
    "NO REPORT NOISE TRIAL TYPE,15,1,2,Center,True,0.4,False,\n"
    "NO REPORT NOISE TRIAL TYPE,16,,,Quadrant,False,,True,0.3\n"
).encode()


def test_report_task_and_calibration_are_distinct() -> None:
    """One report task has one source-clock stimulus; calibration is not a task."""
    pilot = parse_bmvp_trial_csv(REPORT, context="report", expected_task_rows=1)
    assert (pilot.source_rows, pilot.calibration_rows, pilot.task_rows, pilot.blank_rows) == (
        3,
        1,
        1,
        1,
    )
    event = pilot.candidates[0]
    assert event.trial_start_raw == 12.25 and event.task_relevant
    assert event.report_availability == "available" and event.perception_answer == "0"
    assert event.face_opacity_raw == "0.4"


def test_no_report_trial_keeps_relevant_response_off_irrelevant_stimulus() -> None:
    """Archive context never turns an unreported stimulus into E=0."""
    pilot = parse_bmvp_trial_csv(NO_REPORT, context="no_report", expected_task_rows=2)
    assert (pilot.calibration_rows, pilot.task_rows, len(pilot.candidates)) == (1, 2, 4)
    center, quadrant, center2, quadrant2 = pilot.candidates
    assert center.task_relevant and center.perception_answer == "1"
    assert center.report_availability == "available"
    assert not quadrant.task_relevant and quadrant.report_availability == "not_requested"
    assert quadrant.perception_answer is None and quadrant.face_opacity_raw is None
    assert center2.report_availability == "not_requested"
    assert quadrant2.task_relevant and quadrant2.report_availability == "failed"
    assert quadrant2.perception_answer is None


@pytest.mark.parametrize(
    "payload,context",
    [
        (REPORT.replace(b"12.25", b"nan"), "report"),
        (REPORT.replace(b"NOISE,", b"UNKNOWN,"), "report"),
        (REPORT.replace(b"NOISE,12.25,0", b"NOISE,12.25,2"), "report"),
        (NO_REPORT.replace(b",Center,", b",Unknown,"), "no_report"),
        (REPORT.replace(b"Face shown,Face opacity", b"Face shown,Face shown"), "report"),
    ],
)
def test_unverified_schema_or_values_fail_closed(payload: bytes, context: str) -> None:
    """Unknown source fields, values, and clocks cannot silently enter P04."""
    with pytest.raises(IntegrityError):
        parse_bmvp_trial_csv(payload, context=context)


def test_expected_count_and_empty_task_guard() -> None:
    """A small pilot count is explicit; calibration-only files are not task input."""
    with pytest.raises(IntegrityError, match="task-row count"):
        parse_bmvp_trial_csv(REPORT, context="report", expected_task_rows=2)
    with pytest.raises(IntegrityError, match="no task rows"):
        parse_bmvp_trial_csv(
            b"TRIAL TYPE,Trial start time,Perception answer,Perception keypress,Face shown,Face opacity\n"
            b"NOISE CALIBRATION,,1,,True,0.5\n",
            context="report",
        )


@pytest.mark.parametrize("member_name", ["./trials.csv", "../escape.csv"])
def test_tar_pilot_checks_paths_and_never_extracts(tmp_path, member_name: str) -> None:
    """Archive traversal is rejected; a valid fixture remains packed."""
    archive = tmp_path / "fixture.tar"
    with tarfile.open(archive, "w") as handle:
        item = tarfile.TarInfo(member_name)
        item.size = len(REPORT)
        handle.addfile(item, io.BytesIO(REPORT))
    if member_name.startswith("../"):
        with pytest.raises(IntegrityError):
            scan_bmvp_csv_archive(archive, context="report")
    else:
        scans = scan_bmvp_csv_archive(archive, context="report", expected_csv_count=1)
        assert len(scans) == 1 and scans[0].task_rows == 1
        assert not (tmp_path / "trials.csv").exists()
