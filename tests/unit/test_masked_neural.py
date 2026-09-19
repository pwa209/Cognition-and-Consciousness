"""Tiny non-participant fixtures verify trial units, missingness and no-leakage allocation."""

import copy
from pathlib import Path

import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.masked_neural import (
    calibration_input,
    discover_runs,
    fmriprep_arguments,
    subject_partition,
    trial_census,
    trial_reports,
    validate_plan,
)
from factorcon.util import hash_file, load_structured

SOURCE = Path(__file__).resolve().parents[2]
FIXTURE = SOURCE / "tests/fixtures/masked_volume_events.tsv"


def test_dedup_missing_and_partial_runs():
    rows = trial_reports(FIXTURE, expected_trials=32)
    assert len(rows) == 2 and rows[0]["source_volume_rows"] == 2
    assert rows[0]["report"] == 0
    assert rows[1]["report"] == -1 and rows[1]["probe_frames"] is None
    assert rows[1]["probe_frames_missing"]


@pytest.mark.parametrize(
    "old,new",
    [("3.0", "100.0"), ("unconscious", "no experience"), ("2.0\tmissing", "33.0\tmissing")],
)
def test_malformed_source_rejected(tmp_path, old, new):
    file = tmp_path / "bad.tsv"
    file.write_text(FIXTURE.read_text().replace(old, new))
    with pytest.raises(ValueError):
        trial_reports(file, expected_trials=32)


def test_inconsistent_repeated_volume_is_not_a_new_trial(tmp_path):
    file = tmp_path / "bad.tsv"
    file.write_text(FIXTURE.read_text().replace("unconscious", "conscious", 1))
    with pytest.raises(ValueError, match="inconsistent"):
        trial_reports(file, expected_trials=32)


def test_partition_is_order_invariant_and_disjoint():
    plan = load_structured(SOURCE / "conf/masked_neural_plan.yaml")
    subjects = [f"sub-0{i}" for i in range(1, 8)]
    partition = subject_partition(subjects, plan)
    assert partition == subject_partition(subjects[::-1], plan)
    assert len(partition["calibration_subjects"]) == 2
    assert len(partition["evaluation_subjects"]) == 5
    assert not set(partition["calibration_subjects"]) & set(partition["evaluation_subjects"])
    with pytest.raises(ValueError):
        subject_partition(subjects[:-1], plan)


def test_calibration_does_not_open_evaluation_reports(tmp_path):
    plan = load_structured(SOURCE / "conf/masked_neural_plan.yaml")
    partition = {"calibration_subjects": ["sub-01"], "evaluation_subjects": ["sub-02"]}
    file = tmp_path / "event.tsv"
    file.write_bytes(FIXTURE.read_bytes())
    runs = [
        dict(
            subject="sub-01",
            session="ses-1",
            run_id="sub-01_ses-1_run-1",
            events="event.tsv",
            events_sha256=hash_file(file),
        ),
        dict(subject="sub-02", events="not-existing-evaluation.tsv"),
    ]
    data = calibration_input(tmp_path, runs, partition, plan)
    assert data["reports"] == [0, -1]
    assert data["design"] == [[1.0, 0.3, 0.0, 0.0], [1.0, 0.0, 1.0, 1.0]]
    assert set(data["subjects"]) == {"masked_content_fmri:sub-01"}
    runs[0]["events"] = "../escape.tsv"
    with pytest.raises(IntegrityError):
        calibration_input(tmp_path, runs, partition, plan)


def test_hash_overlap_counts_and_census_rejected(tmp_path):
    plan = load_structured(SOURCE / "conf/masked_neural_plan.yaml")
    file = tmp_path / "events.tsv"
    file.write_bytes(FIXTURE.read_bytes())
    run = dict(events="events.tsv", events_sha256=hash_file(file), subject="sub-01")
    with pytest.raises(ValueError, match="census"):
        trial_census(tmp_path, [run], plan)
    with pytest.raises(ValueError, match="overlap"):
        calibration_input(
            tmp_path,
            [run],
            {"calibration_subjects": ["sub-01"], "evaluation_subjects": ["sub-01"]},
            plan,
        )
    run["events_sha256"] = "changed"
    with pytest.raises(ValueError, match="bytes changed"):
        trial_census(tmp_path, [run], plan)
    with pytest.raises(ValueError, match="count"):
        discover_runs(tmp_path, plan)


def test_command_no_validation_bypass_or_outcome_selection(tmp_path):
    plan = load_structured(SOURCE / "conf/masked_neural_plan.yaml")
    argv = fmriprep_arguments(
        bids=tmp_path / "raw",
        output=tmp_path / "out",
        work=tmp_path / "work",
        license_file=tmp_path / "license",
        subject="sub-01",
        plan=plan,
    )
    assert "--fs-no-reconall" in argv and "--notrack" in argv
    assert "--skip-bids-validation" not in argv and "--sloppy" not in argv
    assert argv[argv.index("--participant-label") + 1] == "01"
    for key in ("bids_validation", "scientific_gates", "freesurfer_reconstruction"):
        bad = copy.deepcopy(plan)
        bad[key] = not bad[key]
        with pytest.raises(ValueError):
            validate_plan(bad)
