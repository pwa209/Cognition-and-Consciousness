"""Conservative normalization of BIDS events into the common trial schema."""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from factorcon.config import DatasetConfig, ProjectConfig
from factorcon.errors import ConfigError, IntegrityError
from factorcon.io.bids import read_events
from factorcon.schemas.trial import TrialRecord
from factorcon.util import atomic_write_json, slug, utc_now, write_jsonl

_ENTITY = re.compile(r"(?:^|_)(sub|ses|task|run)-([^_]+)")


def _dataset(project: ProjectConfig, family: str) -> DatasetConfig:
    try:
        return next(item for item in project.datasets if item.family == family)
    except StopIteration as exc:
        raise ConfigError(f"Unknown family: {family}") from exc


def _first(row: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = row.get(name)
        if value not in {None, "", "n/a", "NA", "NaN"}:
            return value
    return None


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _entities(path: Path) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _ENTITY.finditer(path.name)}


def _modality(path: Path) -> str:
    for value in ("func", "eeg", "meg", "ieeg", "beh"):
        if value in path.parts:
            return "fmri" if value == "func" else value
    return "unknown"


def harmonize_bids_events(
    dataset: DatasetConfig,
    data_root: Path,
) -> tuple[list[TrialRecord], dict[str, Any]]:
    """Normalize all event files while preserving every source column in metadata."""

    records: list[TrialRecord] = []
    files = sorted(data_root.rglob("*_events.tsv"))
    for event_file in files:
        entities = _entities(event_file)
        rows = read_events(event_file)
        for index, row in enumerate(rows):
            response = _first(row, ("response", "response_key", "button", "choice", "key_press"))
            awareness = _first(
                row,
                ("visibility", "awareness", "pas", "pas_rating", "experience", "dream_report"),
            )
            arousal = _first(
                row,
                ("sleep_stage", "state", "sedation_state", "rass", "propofol_concentration"),
            )
            report_availability = "available" if awareness is not None else "not_requested"
            record = TrialRecord(
                dataset_family=dataset.family,
                modality=_modality(event_file),
                site=_first(row, ("site", "center", "lab")) or "unknown",
                subject=entities.get("sub", "unknown"),
                session=entities.get("ses", "none"),
                run=entities.get("run", "none"),
                event_id=f"{event_file.relative_to(data_root).as_posix()}#{index + 1}",
                time_reference=float(row["onset"]),
                condition=_first(row, ("trial_type", "condition", "event_type")) or "unspecified",
                stimulus_id=_first(row, ("stimulus_id", "stim_file", "stimulus", "image")),
                stimulus_features={
                    key: row[key]
                    for key in ("category", "orientation", "duration", "contrast", "stimulus_present")
                    if row.get(key) not in {None, "", "n/a"}
                },
                response=response,
                response_time=_float(_first(row, ("response_time", "reaction_time", "rt"))),
                correctness=_float(_first(row, ("correct", "correctness", "accuracy"))),
                observed_experience=_float(awareness) if awareness is not None and _float(awareness) is not None else awareness,
                arousal_state=_float(arousal) if arousal is not None and _float(arousal) is not None else arousal,
                report_availability=report_availability,
                qc_status="pending",
                metadata={
                    "source_file": event_file.relative_to(data_root).as_posix(),
                    "source_row": index + 2,
                    "source_fields": row,
                },
            )
            record.validate()
            records.append(record)
    return records, {"event_files": len(files), "records": len(records)}


def harmonize_family(
    project: ProjectConfig,
    canonical_root: str | Path,
    family: str,
    output: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    """Create common-schema rows for one family or an explicit unsupported/access state."""

    dataset = _dataset(project, family)
    root = Path(canonical_root)
    data_root = root / "data" / "raw" / slug(family) / slug(dataset.snapshot_label)
    output_path = Path(output)
    report: dict[str, Any] = {
        "family": family,
        "created_utc": utc_now(),
        "source_type": dataset.source_type,
        "status": "pending",
        "records": 0,
    }
    if dataset.access == "account_and_terms_required" and not data_root.exists():
        write_jsonl(output_path, [])
        report["status"] = "waiting_access"
        atomic_write_json(report_path, report)
        return report
    if dataset.source_type == "openneuro" or (
        dataset.source_type == "cogitate_account" and (data_root / "dataset_description.json").exists()
    ):
        records, details = harmonize_bids_events(dataset, data_root)
        write_jsonl(output_path, (asdict(record) for record in records))
        report.update(details)
        report["status"] = "harmonized" if records else "no_events_found"
    else:
        write_jsonl(output_path, [])
        report["status"] = "adapter_requires_downloaded_schema_inspection"
        report["reason"] = "non-BIDS adapter remains explicit until the downloaded release schema is validated"
    atomic_write_json(report_path, report)
    return report
