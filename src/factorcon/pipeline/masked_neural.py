"""Dataset-specific raw MRI/run manifest and independent ordinal-report calibration.

The ds003927 event tables repeat trial metadata at each acquired volume. Treating
these rows as independent reports would multiply observations and misstate precision.
This module retains all actual trials, including explicit missing reports.
"""

from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from factorcon.util import ensure_within, hash_file, load_structured, safe_relative_path


def validate_plan(plan: dict[str, Any]) -> None:
    """Validate fixed processing choices/counts, without inspecting neural or report outcomes."""
    if (
        plan.get("schema_version") != 1
        or plan.get("family") != "masked_content_fmri"
        or plan.get("scientific_gates") is not False
        or plan.get("bids_validation") is not True
        or plan.get("freesurfer_reconstruction") is not False
        or plan.get("fmriprep_version") != "25.1.3"
        or plan.get("calibration_design")
        != [
            "intercept",
            "probe_frames_divided_by_10_missing_zero",
            "nonliving_category_indicator",
            "probe_frames_missing_indicator",
        ]
        or plan.get("calibration_context") != "subject_session"
        or plan.get("partition_method") != "sha256_seed_family_subject_smallest_hashes"
    ):
        raise ValueError("unsupported masked-neural plan")
    for key in (
        "expected_participants",
        "expected_bold_runs",
        "trials_per_run",
        "calibration_participants",
        "nprocs",
        "omp_nthreads",
        "memory_mb",
    ):
        if type(plan.get(key)) is not int or plan[key] < 1:
            raise ValueError(f"positive integer {key} required")
    if plan["expected_participants"] - plan["calibration_participants"] < 3:
        raise ValueError("at least three independent evaluation participants required")


def subject_partition(subjects: list[str], plan: dict[str, Any]) -> dict[str, Any]:
    """Allocate subjects by fixed ID hashes, never outcomes; all their sessions stay together.

    The reserved subjects are used for calibration, not discarded. Their neural data
    must never enter this campaign's outer evaluation, including other family aliases.
    This is a versioned non-preregistered design decision, not an unopened lockbox.
    """
    validate_plan(plan)
    if len(set(subjects)) != len(subjects) or len(subjects) != plan["expected_participants"]:
        raise ValueError("participant count/identity mismatch")
    if any(not re.fullmatch(r"sub-[A-Za-z0-9]+", s) for s in subjects):
        raise ValueError("invalid BIDS participant identifier")
    ranks = {
        s: hashlib.sha256(f"{plan['partition_seed']}:{plan['family']}:{s}".encode()).hexdigest()
        for s in subjects
    }
    ordered = sorted(subjects, key=lambda s: (ranks[s], s))
    n = plan["calibration_participants"]
    return {
        "schema_version": 1,
        "family": plan["family"],
        "seed": plan["partition_seed"],
        "method": plan["partition_method"],
        "subject_hashes": ranks,
        "calibration_subjects": sorted(ordered[:n]),
        "evaluation_subjects": sorted(ordered[n:]),
        "scientific_gate": None,
        "selection_used_reports_or_neural_values": False,
    }


def discover_runs(root: Path, plan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build a raw BIDS manifest in seconds and source paths, without loading neural voxels.

    Every run requires BOLD, sidecar and events; each subject requires one T1w.
    Symlink escape, unexpected run counts and missing units halt this preparation.
    Actual fMRIPrep also runs the official BIDS validator before processing.
    """
    validate_plan(plan)
    subjects = sorted(p.name for p in root.glob("sub-*") if p.is_dir())
    partition = subject_partition(subjects, plan)
    runs = []
    for subject in subjects:
        anatomy = sorted((root / subject).rglob("*_T1w.nii.gz"))
        if len(anatomy) != 1:
            raise ValueError("masked source requires exactly one T1w per participant")
        ensure_within(root, anatomy[0])
        for bold in sorted((root / subject).glob("ses-*/func/*_bold.nii.gz")):
            ensure_within(root, bold)
            stem = bold.name.removesuffix("_bold.nii.gz")
            sidecar = bold.with_name(stem + "_bold.json")
            events = bold.with_name(stem + "_events.tsv")
            for path in (sidecar, events):
                ensure_within(root, path)
                if not path.is_file():
                    raise ValueError("BOLD sidecar/event file missing")
            metadata = load_structured(sidecar)
            tr = metadata.get("RepetitionTime")
            if not isinstance(tr, (int, float)) or not math.isfinite(tr) or tr <= 0:
                raise ValueError("finite positive RepetitionTime in seconds required")
            runs.append(
                {
                    "subject": subject,
                    "session": bold.parent.parent.name,
                    "run_id": stem,
                    "bold": bold.relative_to(root).as_posix(),
                    "sidecar": sidecar.relative_to(root).as_posix(),
                    "events": events.relative_to(root).as_posix(),
                    "events_sha256": hash_file(events),
                    "sidecar_sha256": hash_file(sidecar),
                    "repetition_time_seconds": tr,
                }
            )
    if len(runs) != plan["expected_bold_runs"]:
        raise ValueError("expected raw BOLD run count mismatch")
    return runs, partition


def trial_census(root: Path, runs: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    """Audit source trial coverage without selecting on reports; counts are trials, not volumes.

    Reads all event files for schema integrity only. Evaluation reports never enter
    calibration fitting. Short runs and missing reports are retained explicitly.
    """
    histogram: Counter[str] = Counter()
    trials = missing_reports = missing_frames = 0
    for run in runs:
        path = ensure_within(root, root / safe_relative_path(run["events"]))
        if hash_file(path) != run["events_sha256"]:
            raise ValueError("source event bytes changed")
        rows = trial_reports(path, expected_trials=plan["trials_per_run"])
        histogram[str(len(rows))] += 1
        trials += len(rows)
        missing_reports += sum(r["report"] == -1 for r in rows)
        missing_frames += sum(r["probe_frames_missing"] for r in rows)
    if (
        dict(histogram) != plan["expected_trial_count_histogram"]
        or trials != plan["expected_source_trials"]
    ):
        raise ValueError("source trial census changed")
    return {
        "trials": trials,
        "run_trial_histogram": dict(histogram),
        "missing_reports": missing_reports,
        "missing_probe_frames": missing_frames,
        "partial_runs_retained": True,
        "event_timing_status": plan["event_timing_status"],
    }


def trial_reports(path: Path, *, expected_trials: int) -> list[dict[str, Any]]:
    """Collapse ds003927 volume rows to actual runwise trials; report codes 0..2/-1 missing.

    Probe durations remain in source frame counts, never assumed seconds. Grouping
    never uses visibility, neural values or favorable behavioral outcomes. Repeated
    trial metadata must agree; missing reports remain present and coded -1.
    """
    invariant = (
        "visibility",
        "probe_frame",
        "targets",
        "paths",
        "response",
        "correct",
        "RT_response",
    )
    grouped: dict[int, dict[str, str]] = {}
    multiplicity: dict[int, int] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not {"trials", *invariant} <= set(reader.fieldnames or []):
            raise ValueError("masked report columns missing")
        for row in reader:
            number = float(row["trials"])
            if not math.isfinite(number) or not number.is_integer() or number < 0:
                raise ValueError("finite nonnegative integer trial ID required")
            trial = int(number)
            if trial == 0:
                if row["visibility"] not in {"n/a", ""} or row["targets"] not in {"n/a", ""}:
                    raise ValueError("unexpected report in baseline trial zero")
                continue
            if trial in grouped and any(row[k] != grouped[trial][k] for k in invariant):
                raise ValueError("inconsistent metadata across repeated trial volumes")
            grouped[trial] = row
            multiplicity[trial] = multiplicity.get(trial, 0) + 1
    if not grouped or not set(grouped) <= set(range(1, expected_trials + 1)):
        raise ValueError("empty run or unexpected actual trial IDs")
    result = []
    for trial, row in sorted(grouped.items()):
        visibility = row["visibility"]
        categories = {"unconscious": 0, "glimpse": 1, "conscious": 2, "missing data": -1, "n/a": -1}
        if visibility not in categories or row["targets"] not in {
            "Living_Things",
            "Nonliving_Things",
        }:
            raise ValueError("unknown visibility or stimulus category")
        frames = float(row["probe_frame"])
        if frames not in {*range(1, 10), 99}:
            raise ValueError("source frame count must be 1..9 or missing sentinel 99")
        result.append(
            {
                "trial": trial,
                "source_volume_rows": multiplicity[trial],
                "report": categories[visibility],
                "report_token": visibility,
                "probe_frames": None if frames == 99 else frames,
                "probe_frames_missing": frames == 99,
                "nonliving": int(row["targets"] == "Nonliving_Things"),
                "stimulus_id": row["paths"],
            }
        )
    return result


def calibration_input(
    root: Path,
    runs: list[dict[str, Any]],
    partition: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Assemble independent reports with fixed-unit non-neural predictors, no neural reads.

    Evaluation-subject reports are not opened. Contexts are subject/session random
    intercepts. Calibration predicts ordinal report liability, not universal E, and
    stimulus-duration predictors cannot by themselves identify E separately from S.
    """
    calibration = set(partition["calibration_subjects"])
    if calibration & set(partition["evaluation_subjects"]):
        raise ValueError("calibration/evaluation participant overlap")
    design, reports, subjects, contexts, trial_ids = [], [], [], [], []
    sources = {}
    for run in runs:
        if run["subject"] not in calibration:
            continue
        path = ensure_within(root, root / safe_relative_path(run["events"]))
        if hash_file(path) != run["events_sha256"]:
            raise ValueError("source event bytes changed")
        sources[run["events"]] = run["events_sha256"]
        for row in trial_reports(path, expected_trials=plan["trials_per_run"]):
            design.append(
                [
                    1.0,
                    (row["probe_frames"] or 0.0) / 10.0,
                    float(row["nonliving"]),
                    float(row["probe_frames_missing"]),
                ]
            )
            reports.append(row["report"])
            subjects.append(f"masked_content_fmri:{run['subject']}")
            contexts.append(f"masked_content_fmri:{run['subject']}:{run['session']}")
            trial_ids.append(f"{run['run_id']}:trial-{row['trial']}")
    if not reports or len(set(trial_ids)) != len(trial_ids):
        raise ValueError("empty calibration or duplicate trial identities")
    if set(subjects) != {f"masked_content_fmri:{s}" for s in calibration}:
        raise ValueError("calibration cohort incomplete")
    return {
        "schema_version": 1,
        "predictor_source": "non_neural_fixed_units",
        "design": design,
        "reports": reports,
        "subjects": subjects,
        "contexts": contexts,
        "categories": 3,
        "anchor_id": plan["anchor_id"],
        "trial_ids": trial_ids,
        "source_sha256": sources,
        "predictors": plan["calibration_design"],
        "missing_report_code": -1,
        "repeated_volume_rows_deduplicated": True,
        "evaluation_ids": [f"masked_content_fmri:{s}" for s in partition["evaluation_subjects"]],
        "universal_E_scale_validated": False,
        "neural_noise_calibration": False,
    }


def fmriprep_arguments(
    *,
    bids: Path,
    output: Path,
    work: Path,
    license_file: Path,
    subject: str,
    plan: dict[str, Any],
) -> list[str]:
    """Build installed fMRIPrep 25.1.3 arguments; no shell interpolation or scientific exclusions.

    All runs for a subject are processed together. No smoothing, outcome-specific
    windows, anatomical surface reconstruction or BIDS validation bypass is requested.
    """
    validate_plan(plan)
    if not re.fullmatch(r"sub-[A-Za-z0-9]+", subject):
        raise ValueError("invalid participant identifier")
    return [
        "fmriprep",
        str(bids),
        str(output),
        "participant",
        "--participant-label",
        subject[4:],
        "--fs-license-file",
        str(license_file),
        "--fs-no-reconall",
        "--notrack",
        "--nprocs",
        str(plan["nprocs"]),
        "--omp-nthreads",
        str(plan["omp_nthreads"]),
        "--mem",
        str(plan["memory_mb"]),
        "--output-spaces",
        *plan["output_spaces"],
        "--skull-strip-template",
        plan["skull_strip_template"],
        "--skull-strip-fixed-seed",
        "--random-seed",
        str(plan["partition_seed"]),
        "--stop-on-first-crash",
        "-w",
        str(work),
    ]
