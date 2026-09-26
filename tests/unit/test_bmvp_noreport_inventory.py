"""Tiny no-report metadata fixtures; no participant data or voxel arrays."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.bmvp_noreport_inventory import summarize_noreport_mri_archive
from scripts.alliance.bmvp_noreport_inventory import archive_rows, validate_plan
from scripts.alliance.submit_bmvp_noreport_inventory import command


PLAN = {
    "schema_version": 1, "family": "bmvp",
    "scope": "metadata_only_all_verified_noreport_archives_not_P08",
    "selection_basis": "all_67_P03_verified_noreport_archives_before_neural_outcomes",
    "expected_noreport_archives": 67, "expected_report_mri_archives": 37,
    "expected_participant_overlap": 2, "max_csv_bytes": 2_000_000,
    "read_voxel_data": False,
    "infer_absent_experience_from_unrequested_report": False,
    "cross_family_calibration_validated": False, "scientific_gates": False,
}
CSV = (
    "TRIAL TYPE,Trial start time,Perception answer,Perception keypress,Task Relevant,"
    "Center Face shown,Center Face opacity,Quadrant Face shown,Quadrant Face opacity\n"
    "NO REPORT NOISE TRIAL TYPE,15,1,2,Center,True,0.4,False,\n"
).encode()


def make_tar(path: Path, *, traversal: bool = False, bad_csv: bool = False) -> None:
    """Write one synthetic MRI-session TAR with bounded text and empty images."""
    prefix = "../escape" if traversal else "238_NRP/238_NRP_CenterRelevant/MRI_Session"
    entries = {
        f"{prefix}/Behavioral_Data/trials.csv": b"nonsense\n" if bad_csv else CSV,
        f"{prefix}/Behavioral_Data/trials.log": b"0 DATA Keypress: 5\n",
        f"{prefix}/MRI_Data/scan_bold_task_700.nii.gz": b"",
        f"{prefix}/MRI_Data/scan_bold_task_600.nii.gz": b"",
    }
    with tarfile.open(path, "w") as handle:
        for name, payload in entries.items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            handle.addfile(member, io.BytesIO(payload))


def test_inventory_counts_and_no_inferred_experience(tmp_path: Path) -> None:
    """Count raw task rows and scans without exporting rows or E labels."""
    archive = tmp_path / "fixture.tar"
    make_tar(archive)
    with tarfile.open(archive, "r:") as handle:
        result = summarize_noreport_mri_archive(handle, "238")
    assert result["mri_sessions"] == 1
    assert result["bold_700_files"] == result["bold_600_files"] == 1
    assert result["parsed_mri_csv"] == result["parsed_task_rows"] == 1
    assert result["parser_holds"] == []
    assert "experience" not in result


def test_unsupported_csv_recorded_without_fabricated_rows(tmp_path: Path) -> None:
    """An unfamiliar CSV is a hold, not zero trials or no experience."""
    archive = tmp_path / "fixture.tar"
    make_tar(archive, bad_csv=True)
    with tarfile.open(archive, "r:") as handle:
        result = summarize_noreport_mri_archive(handle, "238")
    assert result["parsed_task_rows"] == 0
    assert result["parser_holds"] == ["csv_schema_or_value"]


def test_traversal_and_wrong_participant_rejected(tmp_path: Path) -> None:
    """No TAR member can escape its declared participant root."""
    archive = tmp_path / "fixture.tar"
    make_tar(archive, traversal=True)
    with tarfile.open(archive, "r:") as handle, pytest.raises(IntegrityError):
        summarize_noreport_mri_archive(handle, "238")
    make_tar(archive)
    with tarfile.open(archive, "r:") as handle, pytest.raises(IntegrityError):
        summarize_noreport_mri_archive(handle, "274")


def test_exact_plan_and_expected_archive_count(tmp_path: Path) -> None:
    """The fixed all-source count cannot silently shrink to a favorable subset."""
    validate_plan(PLAN)
    with pytest.raises(ValueError):
        validate_plan({**PLAN, "expected_noreport_archives": 1})
    ledger = tmp_path / "verified-files.jsonl"
    ledger.write_text('{"relative_path":"archives/no_report/238_NRP.tar"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="identities changed"):
        archive_rows(ledger, PLAN)


def test_inventory_runs_only_inside_low_priority_slurm() -> None:
    """A declared one-core compute job, not a login controller, reads TARs."""
    root = Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916")
    source = root / "releases" / ("a" * 40) / "source"
    cmd = command(root, source, root / "operations/bmvp-noreport-inventory/test")
    assert "--cpus-per-task=1" in cmd
    assert "--nice=10000" in cmd
    assert "--no-requeue" in cmd
    assert "--job $SLURM_JOB_ID" in cmd[-1]
