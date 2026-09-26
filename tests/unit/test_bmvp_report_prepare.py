"""Synthetic report-MRI preparation tests; never use participant recordings."""

from __future__ import annotations

import io
import tarfile

import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.bmvp_report_prepare import report_event_rows, select_report_members
from scripts.alliance.bmvp_report_prepare import validate_plan
from scripts.alliance.bmvp_report_preprocess import preprocessed_files


def example() -> tuple[bytes, bytes]:
    """Two 12-volume runs with three source trials and explicit missing reports."""
    log = []
    csv = [
        "TRIAL TYPE,Trial start time,BLOCK NUMBER,Perception answer,Perception keypress,Face shown,Face opacity,Face time"
    ]
    for block, start in ((1, 100.0), (2, 200.0)):
        for index in range(12):
            log.append(f"{start + index:.4f} \tDATA \tKeypress: 5")
        for index, onset in enumerate((start + 2.01, start + 4.0, start + 8.0)):
            answer = "" if index == 1 else str(index % 2)
            csv.append(f"MOVIE,{onset},{block},{answer},k,True,0.5,{onset}")
    return ("\n".join(log) + "\n").encode(), ("\n".join(csv) + "\n").encode()


def test_event_alignment_preserves_missingness_and_units() -> None:
    """An absent answer stays absent; scanner-relative onsets are seconds."""
    log, csv = example()
    timing, runs = report_event_rows(
        log, csv, expected_runs=2, volumes=12, trials_per_run=3,
        pretrial_triggers=2,
    )
    assert len(timing) == len(runs) == 2
    assert [r[0]["onset"] for r in runs] == [2.01, 2.01]
    assert runs[0][1]["report_availability"] == "failed"
    assert runs[0][1]["perception_answer"] == "n/a"
    assert runs[0][0]["perception_answer"] == "0"
    assert all(row["duration"] == 0 for run in runs for row in run)


def test_wrong_trial_block_rejected() -> None:
    """Timing misassignment cannot silently shift a trial to another run."""
    log, csv = example()
    with pytest.raises(IntegrityError):
        report_event_rows(
            log, csv.replace(b"MOVIE,202.01,2", b"MOVIE,202.01,1"),
            expected_runs=2, volumes=12, trials_per_run=3,
            pretrial_triggers=2,
        )


def test_select_report_members_rejects_traversal_and_ambiguous_anatomy(tmp_path) -> None:
    """Archive path safety and exact member counts precede extraction."""
    archive = tmp_path / "fixture.tar"
    names = [
        "191_RP_MRI/Behavioral_Data/task.csv",
        "191_RP_MRI/Behavioral_Data/task.log",
        "191_RP_MRI/MRI_Data/Defaced_MPRAGE_NIFTI/T1w.nii",
    ]
    with tarfile.open(archive, "w") as writer:
        for name in names:
            member = tarfile.TarInfo(name)
            member.size = 1
            writer.addfile(member, io.BytesIO(b"x"))
    with tarfile.open(archive) as reader:
        assert set(select_report_members(reader, "191")) == {"csv", "log", "anat"}
    with tarfile.open(archive, "a") as writer:
        member = tarfile.TarInfo("../outside.txt")
        member.size = 1
        writer.addfile(member, io.BytesIO(b"x"))
    with tarfile.open(archive) as reader, pytest.raises(IntegrityError):
        select_report_members(reader, "191")


def test_preparation_plan_does_not_promote_cross_family_scale() -> None:
    """The versioned plan retains fixed selection and no E-scale claim."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "conf/bmvp_report_preprocess.yaml"
    plan = json.loads(path.read_text())
    validate_plan(plan)
    plan["cross_family_e_scale_validated"] = True
    with pytest.raises(ValueError):
        validate_plan(plan)


def test_preprocessed_file_manifest_requires_all_fixed_spaces(tmp_path) -> None:
    """A success needs MNI, T1w and confounds for every declared run."""
    func = tmp_path / "sub-191/func"
    func.mkdir(parents=True)
    stem = "sub-191_task-bmvpReport_run-01"
    endings = (
        "_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz",
        "_space-T1w_desc-preproc_bold.nii.gz",
        "_desc-confounds_timeseries.tsv",
    )
    for ending in endings:
        (func / f"{stem}{ending}").write_bytes(b"synthetic")
    assert len(preprocessed_files(tmp_path, "191", 1)) == 3
    with pytest.raises(ValueError, match="missing"):
        preprocessed_files(tmp_path, "191", 2)
