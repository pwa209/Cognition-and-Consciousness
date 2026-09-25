"""Lossless BMVP trial-CSV pilot; no neural alignment or E-scale claim."""

from __future__ import annotations

import csv
import io
import math
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from factorcon.errors import IntegrityError
from factorcon.pipeline.empirical import safe_tar_members


@dataclass(frozen=True, slots=True)
class BmvpStimulusCandidate:
    """One source stimulus; clock values retain unknown source units, no E label."""

    source_row: int
    trial_type: str
    trial_start_raw: float
    location: Literal["single", "center", "quadrant"]
    task_relevant: bool
    report_availability: Literal["available", "failed", "not_requested"]
    perception_answer: Literal["0", "1"] | None
    perception_keypress: str | None
    face_shown_raw: str
    face_opacity_raw: str | None
    face_time_raw: str | None


@dataclass(frozen=True, slots=True)
class BmvpCsvPilot:
    """Schema-only CSV parse with source-row counts; no neural or latent fitting."""

    source_rows: int
    calibration_rows: int
    task_rows: int
    blank_rows: int
    candidates: tuple[BmvpStimulusCandidate, ...]


def _required(row: dict[str, str | None], key: str, row_number: int) -> str:
    value = row.get(key)
    if value is None or not value.strip():
        raise IntegrityError(f"BMVP row {row_number} missing required {key!r}")
    return value.strip()


def _optional(row: dict[str, str | None], key: str) -> str | None:
    value = row.get(key)
    return value.strip() if value is not None and value.strip() else None


def parse_bmvp_trial_csv(
    payload: bytes,
    *,
    context: Literal["report", "no_report"],
    expected_task_rows: int | None = None,
) -> BmvpCsvPilot:
    """Parse BMVP CSV bytes into source-clock candidates, without inferring E.

    `trial_start_raw` and `face_time_raw` are source clock values with unverified
    units/scan alignment, so this is not yet a common-schema P04 harmonizer.
    Calibration rows remain counted but cannot be neural task events. In the
    no-report paradigm, each task trial yields two stimulus candidates; the
    response is attached only to its task-relevant location. No cross-fitted
    calibration, neural outcomes, or participant data are consumed here.
    """
    if context not in {"report", "no_report"}:
        raise ValueError("context must be report or no_report")
    if expected_task_rows is not None and expected_task_rows < 0:
        raise ValueError("expected_task_rows must be nonnegative")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError as exc:
        raise IntegrityError("BMVP CSV is not valid UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = reader.fieldnames or []
    nonempty = [field for field in fields if field]
    if not nonempty or len(nonempty) != len(set(nonempty)):
        raise IntegrityError("BMVP CSV has missing or duplicate nonempty headers")
    base = {"TRIAL TYPE", "Trial start time", "Perception answer", "Perception keypress"}
    required = base | (
        {"Face shown", "Face opacity"}
        if context == "report"
        else {
            "Task Relevant",
            "Center Face shown",
            "Center Face opacity",
            "Quadrant Face shown",
            "Quadrant Face opacity",
        }
    )
    if missing := required - set(fields):
        raise IntegrityError(f"BMVP CSV missing columns: {sorted(missing)}")
    source_rows = calibration_rows = task_rows = blank_rows = 0
    candidates: list[BmvpStimulusCandidate] = []
    for source_row, row in enumerate(reader, start=2):
        source_rows += 1
        if None in row or any(value is None for value in row.values()):
            raise IntegrityError(f"BMVP CSV row {source_row} has wrong width")
        trial_type = _optional(row, "TRIAL TYPE")
        if trial_type is None:
            if any(value.strip() for value in row.values()):
                raise IntegrityError(f"BMVP CSV row {source_row} has values but no trial type")
            blank_rows += 1
            continue
        if "CALIBRATION" in trial_type.upper():
            calibration_rows += 1
            continue
        if context == "report" and trial_type.upper() not in {"MOVIE", "NOISE"}:
            raise IntegrityError(f"unknown BMVP report task type: {trial_type}")
        if context == "no_report" and not trial_type.upper().startswith("NO REPORT "):
            raise IntegrityError(f"unknown BMVP no-report task type: {trial_type}")
        task_rows += 1
        raw_start = _required(row, "Trial start time", source_row)
        try:
            trial_start = float(raw_start)
        except ValueError as exc:
            raise IntegrityError(f"BMVP row {source_row} has nonnumeric source clock") from exc
        if not math.isfinite(trial_start):
            raise IntegrityError(f"BMVP row {source_row} has nonfinite source clock")
        answer = _optional(row, "Perception answer")
        if answer not in {None, "0", "1"}:
            raise IntegrityError(f"BMVP row {source_row} has unknown report answer")
        keypress = _optional(row, "Perception keypress")
        if context == "report":
            locations: tuple[tuple[Literal["single", "center", "quadrant"], bool], ...] = (
                ("single", True),
            )
        else:
            relevant = _required(row, "Task Relevant", source_row).lower()
            if relevant not in {"center", "quadrant"}:
                raise IntegrityError(f"BMVP row {source_row} has unknown task-relevant location")
            locations = (("center", relevant == "center"), ("quadrant", relevant == "quadrant"))
        for location, is_relevant in locations:
            prefix = "Face" if location == "single" else f"{location.title()} Face"
            shown = _required(row, f"{prefix} shown", source_row)
            if shown not in {"True", "False"}:
                raise IntegrityError(f"BMVP row {source_row} has unknown face-presence token")
            opacity = _optional(row, f"{prefix} opacity")
            availability: Literal["available", "failed", "not_requested"] = (
                "not_requested" if not is_relevant else "failed" if answer is None else "available"
            )
            candidates.append(
                BmvpStimulusCandidate(
                    source_row=source_row,
                    trial_type=trial_type,
                    trial_start_raw=trial_start,
                    location=location,
                    task_relevant=is_relevant,
                    report_availability=availability,
                    perception_answer=answer if is_relevant else None,
                    perception_keypress=keypress if is_relevant else None,
                    face_shown_raw=shown,
                    face_opacity_raw=opacity,
                    face_time_raw=_optional(row, f"{prefix} time"),
                )
            )
    if expected_task_rows is not None and task_rows != expected_task_rows:
        raise IntegrityError(
            f"BMVP task-row count {task_rows} != expected {expected_task_rows}"
        )
    if task_rows == 0:
        raise IntegrityError("BMVP CSV contains no task rows")
    return BmvpCsvPilot(
        source_rows,
        calibration_rows,
        task_rows,
        blank_rows,
        tuple(candidates),
    )


def scan_bmvp_csv_archive(
    archive: Path,
    *,
    context: Literal["report", "no_report"],
    expected_csv_count: int | None = None,
    max_csv_bytes: int = 2_000_000,
) -> tuple[BmvpCsvPilot, ...]:
    """Read bounded CSV bytes from one validated TAR, never extract or fit labels.

    Archive members are checked for traversal, links, special files and duplicate
    destinations before a CSV is read. Source clock values remain uncalibrated;
    no participant-level rows should be logged or committed by the caller.
    """
    if max_csv_bytes <= 0 or expected_csv_count is not None and expected_csv_count < 0:
        raise ValueError("invalid BMVP archive count or byte bound")
    with tarfile.open(archive, "r:*") as handle:
        members = safe_tar_members(handle)
        csv_members = [
            member
            for member in members
            if member.isfile() and member.name.lower().endswith(".csv")
        ]
        if expected_csv_count is not None and len(csv_members) != expected_csv_count:
            raise IntegrityError(
                f"BMVP CSV member count {len(csv_members)} != expected {expected_csv_count}"
            )
        if not csv_members:
            raise IntegrityError("BMVP archive has no trial CSV")
        results = []
        for member in csv_members:
            if member.size > max_csv_bytes:
                raise IntegrityError("BMVP trial CSV exceeds configured byte bound")
            stream = handle.extractfile(member)
            if stream is None:
                raise IntegrityError("BMVP trial CSV is not a regular file")
            with stream:
                payload = stream.read(max_csv_bytes + 1)
            if len(payload) != member.size:
                raise IntegrityError("BMVP trial CSV size mismatch")
            results.append(parse_bmvp_trial_csv(payload, context=context))
        return tuple(results)
