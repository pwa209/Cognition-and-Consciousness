"""Source-verified COGITATE Exp1 fMRI event adapter; no neural/experience inference."""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from factorcon.errors import IntegrityError
from factorcon.pipeline.empirical import AcquiredInput, safe_zip_members
from factorcon.schemas.trial import TrialRecord
from factorcon.util import ensure_within, safe_relative_path, write_jsonl

_ENTITIES = re.compile(r"(?:^|_)(sub|ses|task|run)-([^_]+)")
_STIMULI = {"face", "object", "letter", "falseFont"}
_OTHER = {"baseline", "response", "targetScreen"}
_REQUIRED = {
    "onset",
    "duration",
    "trial_type",
    "task_relevance",
    "stimulus_orientation",
    "stimulus_id",
    "response",
}


def parse_fmri_events(payload: bytes, member: str, archive: str) -> list[TrialRecord]:
    """Parse one upstream TSV: onset/duration in seconds, no outcome-dependent fitting.

    Retain stimulus and nonstimulus rows. Task relevance is a task manipulation,
    not experience. Behavioral response outcome is not a measured button time.
    All original fields stay in private metadata; values never become file paths.
    """
    safe_relative_path(member)
    entities = dict(_ENTITIES.findall(Path(member).name))
    if not {"sub", "ses", "task", "run"} <= entities.keys():
        raise IntegrityError("COGITATE fMRI subject/session/task/run identity missing")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter="\t")
    if set(reader.fieldnames or []) != _REQUIRED:
        raise IntegrityError("COGITATE Exp1 fMRI event schema changed")
    previous = -math.inf
    records = []
    for index, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise IntegrityError("COGITATE event row width mismatch")
        onset, duration = float(row["onset"]), float(row["duration"])
        if (
            not math.isfinite(onset)
            or not math.isfinite(duration)
            or onset < previous
            or duration < 0
        ):
            raise IntegrityError("invalid/nonmonotonic COGITATE event timing")
        previous = onset
        kind = row["trial_type"]
        if kind not in _STIMULI | _OTHER:
            raise IntegrityError(f"unknown COGITATE event type: {kind}")
        if kind in _STIMULI:
            if row["task_relevance"] not in {"target", "relevant", "irrelevant"}:
                raise IntegrityError("unknown stimulus task relevance")
            if row["stimulus_orientation"] not in {"center", "left", "right"}:
                raise IntegrityError("unknown stimulus orientation")
            if row["response"] not in {"hit", "miss", "correctRejection", "falseAlarm", "n/a"}:
                raise IntegrityError("unknown behavioral outcome")
        record = TrialRecord(
            dataset_family="cogitate",
            modality="fmri",
            site="unknown",
            subject=entities["sub"],
            session=entities["ses"],
            run=f"{entities['task']}:{entities['run']}",
            event_id=f"{archive}!{member}#{index}",
            time_reference=onset,
            condition=f"{kind}:{row['task_relevance']}",
            stimulus_id=row["stimulus_id"] if kind in _STIMULI else None,
            stimulus_features={
                "category": kind if kind in _STIMULI else None,
                "orientation": row["stimulus_orientation"],
                "duration": duration,
                "task_relevance": row["task_relevance"],
            },
            response=None,
            response_time=None,
            correctness=None,
            observed_experience=None,
            arousal_state=None,
            report_availability="unknown",
            qc_status="pending",
            metadata={
                "source_archive": archive,
                "source_file": member,
                "source_row": index,
                "source_fields": row,
                "time_reference_unit": "seconds",
                "event_role": "stimulus" if kind in _STIMULI else kind,
                "behavioral_outcome": row["response"],
                "E_not_measured": True,
                "adapter": "cogitate_exp1_fmri_observed_events_v1",
            },
        )
        record.validate()
        records.append(record)
    if not records:
        raise IntegrityError("empty COGITATE event table")
    return records


def harmonize_cogitate_fmri(
    inputs: AcquiredInput, output: Path, *, expected_participants: int, expected_event_files: int
) -> dict[str, Any]:
    """Stream verified BIDS fMRI ZIP events to private JSONL; no recording extraction.

    Count all subjects and event files; mismatches fail the affected adapter. M/EEG
    and iEEG trigger streams are not mislabeled as equivalent fMRI trial schemas.
    Independent subject identities remain intact; site is unknown until verified.
    """
    candidates = [r for r in inputs.records if "_bids_fmri_" in r.relative_path]
    if len(candidates) != 1:
        raise IntegrityError("exactly one acquired COGITATE BIDS fMRI bundle required")
    archive = candidates[0].relative_path
    path = ensure_within(inputs.data_root, inputs.data_root / safe_relative_path(archive))
    subjects = set()
    count = 0
    with zipfile.ZipFile(path) as z:
        members = safe_zip_members(z)
        events = [m for m in members if m.filename.endswith("_events.tsv")]
        if len(events) != expected_event_files:
            raise IntegrityError("COGITATE fMRI event-file count mismatch")

        def rows():
            nonlocal count
            for member in sorted(events, key=lambda m: m.filename):
                if member.file_size > 2_000_000:
                    raise IntegrityError("event TSV exceeds declared metadata budget")
                for record in parse_fmri_events(z.read(member), member.filename, archive):
                    subjects.add(record.subject)
                    count += 1
                    yield asdict(record)
            if len(subjects) != expected_participants:
                raise IntegrityError("COGITATE fMRI participant count mismatch")

        write_jsonl(output, rows())
    return {
        "status": "harmonized",
        "modality_scope": "fmri_only",
        "records": count,
        "participants": len(subjects),
        "event_files": len(events),
        "experience_calibrated": False,
        "neural_preprocessing_validated": False,
    }
