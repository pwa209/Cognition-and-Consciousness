"""Outcome-blind, bounded BMVP no-report MRI archive inventory."""

from __future__ import annotations

import tarfile
from pathlib import PurePosixPath
from typing import Any

from factorcon.errors import IntegrityError
from factorcon.pipeline.bmvp_csv import parse_bmvp_trial_csv
from factorcon.pipeline.empirical import safe_tar_members


def summarize_noreport_mri_archive(
    handle: tarfile.TarFile, participant: str, *, max_csv_bytes: int = 2_000_000
) -> dict[str, Any]:
    """Count MRI-session files and task rows; no voxels or fitted labels are read.

    Counts have units files, sessions and source task rows. The TAR paths are
    validated before bounded CSV reads. A parser hold is recorded, not silently
    interpreted as missing experience or a no-report trial label.
    """
    if not participant.isdecimal() or len(participant) != 3 or max_csv_bytes < 1:
        raise ValueError("three-digit participant and positive CSV byte bound required")
    members = safe_tar_members(handle)
    prefix = f"{participant}_NRP/"
    if any(
        member.name not in {f"{participant}_NRP", f"{participant}_NRP/"}
        and not member.name.startswith(prefix)
        for member in members
    ):
        raise IntegrityError("no-report TAR member lies outside participant root")
    sessions: set[str] = set()
    bold_700 = bold_600 = behavioral_logs = behavioral_csv = parsed_csv = task_rows = 0
    parser_holds: list[str] = []
    for member in members:
        if not member.isfile():
            continue
        name = PurePosixPath(member.name).as_posix()
        if "/MRI_Session/" not in name:
            continue
        session = name.split("/MRI_Session/", 1)[0]
        sessions.add(session)
        leaf = PurePosixPath(name).name.lower()
        if "/MRI_Data/" in name and leaf.endswith((".nii", ".nii.gz")):
            if "bold_task_700" in leaf:
                bold_700 += 1
            elif "bold_task_600" in leaf:
                bold_600 += 1
        if "/Behavioral_Data/" not in name:
            continue
        if leaf.endswith(".log"):
            behavioral_logs += 1
        elif leaf.endswith(".csv"):
            behavioral_csv += 1
            if member.size < 1 or member.size > max_csv_bytes:
                parser_holds.append("csv_size_bound")
                continue
            stream = handle.extractfile(member)
            if stream is None:
                raise IntegrityError("no-report behavioral CSV member is not regular")
            with stream:
                payload = stream.read(max_csv_bytes + 1)
            if len(payload) != member.size:
                raise IntegrityError("no-report behavioral CSV length mismatch")
            try:
                pilot = parse_bmvp_trial_csv(payload, context="no_report")
            except IntegrityError:
                parser_holds.append("csv_schema_or_value")
            else:
                parsed_csv += 1
                task_rows += pilot.task_rows
    return {
        "participant": participant,
        "mri_sessions": len(sessions),
        "bold_700_files": bold_700,
        "bold_600_files": bold_600,
        "mri_behavioral_logs": behavioral_logs,
        "mri_behavioral_csv": behavioral_csv,
        "parsed_mri_csv": parsed_csv,
        "parsed_task_rows": task_rows,
        "parser_holds": sorted(set(parser_holds)),
        "scope": "metadata_inventory_not_event_alignment_or_E_calibration",
    }
