"""Source-matched ds003927 image timing; published volume rows are not trial onsets."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from pathlib import PurePosixPath
from typing import Any

import numpy as np


def behavior_path(run: dict[str, Any]) -> str:
    """Map a validated BIDS run to the pinned upstream behavioural CSV; no neural reads."""
    match = re.fullmatch(r"(sub-\d+)_ses-(\d+)_task-recog_run-(\d+)", run["run_id"])
    if not match or match[1] != run["subject"] or f"ses-{match[2]}" != run["session"]:
        raise ValueError("unexpected BIDS run identity")
    return (
        f"data/behavioral/{match[1]}/session-{int(match[2]):02d}/"
        f"{match[1]}_unfeat_run-{int(match[3]):02d}.csv"
    )


def git_blob_sha(data: bytes) -> str:
    """Git's SHA-1 blob identity for upstream integrity, not a credential or security key."""
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def source_code(value: str) -> int:
    """Parse complete original integer codes, not the publisher's lossy first-digit extraction."""
    numbers = re.findall(r"\d+", value)
    return int(numbers[0]) if numbers else 99


def publisher_codes(values: list[str]) -> list[int]:
    """Reproduce the source helper's first-digit regex and pandas numeric-column failure.

    Numeric columns become floats after metadata missing values; regex on a float
    raises and the helper returns 99. This is for audit only, never physical duration.
    """
    numeric = True
    for value in values:
        try:
            float(value or "nan")
        except ValueError:
            numeric = False
            break
    if numeric:
        return [99] * len(values)
    return [
        int(re.findall(r"\d", value)[0]) if re.findall(r"\d", value) else 99 for value in values
    ]


def behavior_trials(data: bytes) -> list[dict[str, Any]]:
    """Parse PsychoPy trial table before the metadata footer; units are scanner seconds.

    Preserve missing reports/frames; never fit an E mapping here or use neural data.
    Rows may be in randomized CSV order, so numeric trial order defines identity.
    """
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
    header = next(reader)
    required = {
        "order",
        "image_onset_time_raw",
        "category",
        "probe_path",
        "visible.keys_raw",
        "response.keys_raw",
        "response.corr_raw",
        "response.rt_raw",
    }
    if not required <= set(header):
        raise ValueError("upstream behaviour schema mismatch")
    frame_key = "probe_Frames_raw" if "probe_Frames_raw" in header else "probeFrames_raw"
    if frame_key not in header:
        raise ValueError("source frame-count column missing")
    result, seen, footer = [], set(), False
    raw_frames, raw_reports = [], []
    for fields in reader:
        if (
            not fields
            or fields == ["extraInfo"]
            or (len(fields) == 2 and fields[0] and not fields[0].replace(".", "", 1).isdigit())
        ):
            footer = True
            continue
        if len(fields) != len(header):
            raise ValueError("malformed source trial/footer row")
        if footer:
            raise ValueError("trial-shaped row after metadata footer")
        row = dict(zip(header, fields, strict=True))
        order = float(row["order"])
        onset = float(row["image_onset_time_raw"])
        if not order.is_integer() or not 0 <= order < 32 or int(order) in seen:
            raise ValueError("duplicate/invalid source trial order")
        if not math.isfinite(onset) or onset < 0:
            raise ValueError("invalid scanner image onset")
        seen.add(int(order))
        report = source_code(row["visible.keys_raw"])
        frames = source_code(row[frame_key])
        if report not in {1, 2, 3, 99} or frames not in {*range(1, 16), 99}:
            raise ValueError("unknown report/frame source code")
        if row["category"] not in {"Living_Things", "Nonliving_Things"}:
            raise ValueError("unknown source category")
        response = source_code(row["response.keys_raw"])
        raw_frames.append(row[frame_key])
        raw_reports.append(row["visible.keys_raw"])
        result.append(
            {
                "trial": int(order) + 1,
                "image_onset_seconds": onset,
                "report": report - 1 if report != 99 else -1,
                "probe_frames": frames if frames != 99 else None,
                "nonliving": int(row["category"] == "Nonliving_Things"),
                "stimulus_id": PurePosixPath(row["probe_path"]).name,
                "response": response if response in {1, 2} else None,
                "correct": row["response.corr_raw"],
                "response_rt": row["response.rt_raw"],
            }
        )
    if not result:
        raise ValueError("empty source behaviour")
    for trial, frames, report in zip(
        result, publisher_codes(raw_frames), publisher_codes(raw_reports), strict=True
    ):
        trial["publisher_probe_frames"] = frames
        trial["publisher_report_code"] = report
    return sorted(result, key=lambda r: r["trial"])


def align_run(
    events: bytes,
    behavior: bytes,
    *,
    volumes: int,
    tr_seconds: float,
    removed_volumes: int = 10,
) -> dict[str, Any]:
    """Reproduce published volume membership from original onsets; never infer a shift from BOLD.

    Events are sampled after removal of ten volumes; returned image onsets remain
    in the original raw/fMRIPrep scanner coordinate. Every row and image/report label
    must match. Unrepresented source trials are reported, not silently reassigned.
    """
    trials = behavior_trials(behavior)
    rows = list(csv.DictReader(io.StringIO(events.decode("utf-8-sig")), delimiter="\t"))
    if not rows or volumes - len(rows) != removed_volumes or not 0 < tr_seconds < 10:
        raise ValueError("raw/event volume-count or TR mismatch")
    times = np.arange(len(rows)) * tr_seconds
    starts = np.array(
        [t["image_onset_seconds"] - removed_volumes * tr_seconds - 1.4 for t in trials]
    )
    if np.any(np.diff(starts) <= 0):
        raise ValueError("source image times not strictly increasing by trial")
    represented, repaired_names = set(), set()
    for i, row in enumerate(rows):
        if not math.isclose(float(row["onset"]), times[i], abs_tol=1e-5) or not math.isclose(
            float(row["duration"]), tr_seconds, abs_tol=1e-5
        ):
            raise ValueError("published event coordinate differs from inspected source")
        eligible = np.flatnonzero(times[i] >= starts)
        expected_trial = trials[eligible[-1]]["trial"] if len(eligible) else 0
        if float(row["trials"]) != expected_trial:
            raise ValueError(f"source trial/volume alignment mismatch at volume {i}")
        if not expected_trial:
            continue
        trial = trials[eligible[-1]]
        represented.add(expected_trial)
        report = {1: "unconscious", 2: "glimpse", 3: "conscious", 99: "missing data"}[
            trial["publisher_report_code"]
        ]
        observed_name = row["paths"]
        candidates = {
            t["stimulus_id"] for t in trials if t["stimulus_id"].startswith(observed_name)
        }
        name_matches = observed_name == trial["stimulus_id"] or (
            len(observed_name) == 20 and candidates == {trial["stimulus_id"]}
        )
        if (
            row["visibility"] != report
            or not name_matches
            or row["targets"] != ("Nonliving_Things" if trial["nonliving"] else "Living_Things")
        ):
            raise ValueError("source trial image/category/report linkage differs")
        if observed_name != trial["stimulus_id"]:
            repaired_names.add(trial["trial"])
        if "probe_frame" in row and float(row["probe_frame"]) != trial["publisher_probe_frames"]:
            raise ValueError("source frame-count linkage differs")
        interest = any(
            t["image_onset_seconds"] - removed_volumes * tr_seconds + 4
            < times[i]
            < t["image_onset_seconds"] - removed_volumes * tr_seconds + 7
            for t in trials
        )
        if "volume_interest" in row and float(row["volume_interest"]) != int(interest):
            raise ValueError("publisher response-window mapping differs")
    return {
        "raw_volumes": volumes,
        "event_rows": len(rows),
        "tr_seconds": tr_seconds,
        "removed_volumes": removed_volumes,
        "event_alignment_verified": True,
        "onset_coordinate": "raw_scanner_seconds_no_shift_for_untrimmed_fmriprep",
        "trials": trials,
        "unrepresented_source_trials": sorted({t["trial"] for t in trials} - represented),
        "corrected_frame_codes": sum(
            (t["probe_frames"] or 99) != t["publisher_probe_frames"] for t in trials
        ),
        "uniquely_resolved_truncated_filenames": sorted(repaired_names),
    }


def audit_run(events: bytes, behavior: bytes, *, volumes: int, tr_seconds: float) -> dict[str, Any]:
    """Preserve source reports but exclude neural runs with unresolved crosswalk/timing integrity.

    Exclusions depend only on source metadata, never BOLD values or model outcomes.
    Source parse errors still raise. A mismatched run is never repaired by searching
    for a different behavioural run or by fitting an onset shift to neural activity.
    """
    trials = behavior_trials(behavior)
    try:
        return align_run(events, behavior, volumes=volumes, tr_seconds=tr_seconds)
    except ValueError as exc:
        expected = (
            "raw/event volume-count",
            "source trial/volume alignment",
            "source trial image/",
            "source frame-count linkage",
            "publisher response-window",
            "published event coordinate",
        )
        if not str(exc).startswith(expected):
            raise
        return {
            "raw_volumes": volumes,
            "tr_seconds": tr_seconds,
            "trials": trials,
            "event_alignment_verified": False,
            "technical_exclusion_reason": str(exc),
            "corrected_frame_codes": sum(
                (t["probe_frames"] or 99) != t["publisher_probe_frames"] for t in trials
            ),
        }
