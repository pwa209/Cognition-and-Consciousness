"""Outcome-blind BMVP report-MRI event preparation in scanner-relative seconds."""

from __future__ import annotations

import csv
import io
import math
import tarfile
from pathlib import PurePosixPath
from typing import Any

from factorcon.errors import IntegrityError
from factorcon.pipeline.bmvp_csv import parse_bmvp_trial_csv
from factorcon.pipeline.bmvp_timing import BmvpRunTiming, align_report_mri_timing
from factorcon.pipeline.empirical import safe_tar_members


def select_report_members(handle: tarfile.TarFile, participant: str) -> dict[str, tarfile.TarInfo]:
    """Select one CSV, log and defaced T1w from a validated TAR; no extraction.

    The participant is a fixed archive identity, not selected on behavior or
    neural outcomes. All TAR names/types are checked before reading any member.
    """
    if not participant.isdecimal() or len(participant) != 3:
        raise ValueError("three-digit BMVP participant required")
    members = safe_tar_members(handle)
    base = f"{participant}_RP_MRI/"
    chosen: dict[str, list[tarfile.TarInfo]] = {k: [] for k in ("csv", "log", "anat")}
    for member in members:
        name = PurePosixPath(member.name).as_posix()
        if not member.isfile() or not name.startswith(base):
            continue
        if "/Behavioral_Data/" in name and name.lower().endswith(".csv"):
            chosen["csv"].append(member)
        elif "/Behavioral_Data/" in name and name.lower().endswith(".log"):
            chosen["log"].append(member)
        elif "/Defaced_MPRAGE_NIFTI/" in name and name.lower().endswith((".nii", ".nii.gz")):
            chosen["anat"].append(member)
    if any(len(value) != 1 for value in chosen.values()):
        raise IntegrityError("report archive must contain exactly one CSV, log and defaced T1w")
    return {key: value[0] for key, value in chosen.items()}


def bounded_member(handle: tarfile.TarFile, member: tarfile.TarInfo, limit: int) -> bytes:
    """Read one text member with a strict byte bound; no archive file executes."""
    if not member.isfile() or member.size < 1 or member.size > limit:
        raise IntegrityError("BMVP metadata member exceeds size/type bound")
    stream = handle.extractfile(member)
    if stream is None:
        raise IntegrityError("BMVP metadata member is not regular")
    with stream:
        value = stream.read(limit + 1)
    if len(value) != member.size:
        raise IntegrityError("BMVP metadata member length mismatch")
    return value


def report_event_rows(
    log_bytes: bytes, csv_bytes: bytes, *, expected_runs: int,
    volumes: int = 720, tr_seconds: float = 1.0, trials_per_run: int = 32,
    pretrial_triggers: int = 10,
) -> tuple[tuple[BmvpRunTiming, ...], tuple[tuple[dict[str, Any], ...], ...]]:
    """Map each source task trial to a report run; onset/duration are seconds.

    The source CSV/log, not BOLD or evaluation outcomes, defines block identity.
    Zero duration is an onset impulse, not an inferred stimulus duration. Missing
    reports remain missing; response 0 is never equated with absence of E.
    """
    alignment = align_report_mri_timing(
        log_bytes, csv_bytes, expected_runs=expected_runs,
        expected_volumes_per_run=volumes,
        expected_task_trials_per_run=trials_per_run,
        tr_seconds=tr_seconds, expected_pretrial_triggers=pretrial_triggers,
    )
    pilot = parse_bmvp_trial_csv(
        csv_bytes, context="report", expected_task_rows=expected_runs * trials_per_run
    )
    source_rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"), newline="")))
    by_row = {candidate.source_row: candidate for candidate in pilot.candidates}
    if len(by_row) != expected_runs * trials_per_run:
        raise IntegrityError("report source-row/candidate count mismatch")
    by_block: dict[int, list[dict[str, Any]]] = {i: [] for i in range(1, expected_runs + 1)}
    for row_number, row in enumerate(source_rows, start=2):
        candidate = by_row.get(row_number)
        if candidate is None:
            continue
        try:
            block = int((row.get("BLOCK NUMBER") or "").strip())
        except ValueError as exc:
            raise IntegrityError("report task block is not numeric") from exc
        if block not in by_block:
            raise IntegrityError("report task block not in fixed scanner-run list")
        run = alignment[block - 1]
        onset = candidate.trial_start_raw - run.first_trigger_seconds
        if not math.isfinite(onset) or not 0 <= onset < volumes * tr_seconds:
            raise IntegrityError("report task onset lies outside its scanner run")
        by_block[block].append({
            "onset": round(onset, 6),
            "duration": 0.0,
            "trial_type": candidate.trial_type,
            "source_row": row_number,
            "face_shown": candidate.face_shown_raw,
            "face_opacity_source": candidate.face_opacity_raw or "n/a",
            "report_availability": candidate.report_availability,
            "perception_answer": candidate.perception_answer or "n/a",
            "perception_keypress": candidate.perception_keypress or "n/a",
        })
    result = []
    for block in range(1, expected_runs + 1):
        events = by_block[block]
        if len(events) != trials_per_run or any(
            right["onset"] <= left["onset"] for left, right in zip(events, events[1:])
        ):
            raise IntegrityError("report run trial count/order mismatch")
        result.append(tuple(events))
    return alignment, tuple(result)
