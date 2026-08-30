"""Dependency-free BIDS identity and event inventory checks."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from factorcon.errors import IntegrityError


@dataclass(frozen=True, slots=True)
class BIDSInventory:
    """Minimal BIDS identity/count inventory prior to full validator execution."""

    root: str
    name: str
    bids_version: str
    dataset_type: str
    participants: tuple[str, ...]
    event_files: tuple[str, ...]
    modalities: tuple[str, ...]


def inventory_bids(root: str | Path) -> BIDSInventory:
    """Validate essential BIDS identity files and inventory participants/events."""

    source = Path(root).resolve()
    description_path = source / "dataset_description.json"
    if not description_path.is_file():
        raise IntegrityError(f"Missing BIDS dataset_description.json: {source}")
    try:
        description = json.loads(description_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"Invalid BIDS dataset description: {exc}") from exc
    for key in ("Name", "BIDSVersion"):
        if not description.get(key):
            raise IntegrityError(f"BIDS description missing {key}")
    participants = tuple(sorted(path.name[4:] for path in source.glob("sub-*") if path.is_dir()))
    if not participants:
        raise IntegrityError(f"No subject directories found in {source}")
    event_files = tuple(
        sorted(str(path.relative_to(source)) for path in source.rglob("*_events.tsv"))
    )
    modalities = tuple(
        name
        for name in ("anat", "func", "dwi", "fmap", "eeg", "meg", "ieeg", "beh", "pet")
        if any(path.is_dir() for path in source.glob(f"sub-*/**/{name}"))
    )
    return BIDSInventory(
        root=str(source),
        name=str(description["Name"]),
        bids_version=str(description["BIDSVersion"]),
        dataset_type=str(description.get("DatasetType", "raw")),
        participants=participants,
        event_files=event_files,
        modalities=modalities,
    )


def read_events(path: str | Path) -> list[dict[str, str]]:
    """Read a BIDS events TSV and validate finite, nonnegative onsets/durations."""

    source = Path(path)
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows or "onset" not in rows[0] or "duration" not in rows[0]:
        raise IntegrityError(f"Events file lacks onset/duration: {source}")
    previous = float("-inf")
    for index, row in enumerate(rows, start=2):
        try:
            onset = float(row["onset"])
            duration = float(row["duration"])
        except (TypeError, ValueError) as exc:
            raise IntegrityError(f"Invalid event timing at {source}:{index}") from exc
        if onset < previous or duration < 0:
            raise IntegrityError(f"Nonmonotonic onset or negative duration at {source}:{index}")
        previous = onset
    return rows
