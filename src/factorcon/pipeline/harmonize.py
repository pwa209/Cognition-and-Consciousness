"""Conservative normalization of BIDS events into the common trial schema."""

from __future__ import annotations

import csv
import math
import re
from dataclasses import asdict, replace
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
        number = float(value)
        return number if math.isfinite(number) else None
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
    files = sorted(
        p
        for p in data_root.rglob("*_events.tsv")
        if "derivatives" not in p.relative_to(data_root).parts
    )
    for event_file in files:
        if not event_file.resolve().is_relative_to(data_root.resolve()):
            raise IntegrityError("event file resolves outside the dataset root")
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
            report_availability = "available" if awareness is not None else "unknown"
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
                    for key in (
                        "category",
                        "orientation",
                        "duration",
                        "contrast",
                        "stimulus_present",
                    )
                    if row.get(key) not in {None, "", "n/a"}
                },
                response=response,
                response_time=_float(_first(row, ("response_time", "reaction_time", "rt"))),
                correctness=_float(_first(row, ("correct", "correctness", "accuracy"))),
                observed_experience=_float(awareness)
                if awareness is not None and _float(awareness) is not None
                else awareness,
                arousal_state=_float(arousal)
                if arousal is not None and _float(arousal) is not None
                else arousal,
                report_availability=report_availability,
                qc_status="pending",
                metadata={
                    "source_file": event_file.relative_to(data_root).as_posix(),
                    "source_row": index + 2,
                    "source_fields": row,
                },
            )
            record.validate()
            if dataset.family == "masked_content_fmri":
                required = {
                    "visibility",
                    "targets",
                    "labels",
                    "paths",
                    "response",
                    "correct",
                    "RT_response",
                    "options",
                }
                if missing := required - row.keys():
                    raise IntegrityError(f"ds003927 event columns missing: {sorted(missing)}")
                visibility = _first(row, ("visibility",))
                if visibility not in {None, "unconscious", "glimpse", "conscious"}:
                    raise IntegrityError(f"Unrecognized ds003927 visibility: {visibility}")
                category = _first(row, ("targets",))
                if category not in {None, "Living_Things", "Nonliving_Things"}:
                    raise IntegrityError(f"Unrecognized ds003927 target category: {category}")
                record = replace(
                    record,
                    condition=category or "unspecified",
                    stimulus_id=_first(row, ("paths", "labels")),
                    stimulus_features={
                        **record.stimulus_features,
                        "category": category,
                        "object_label": _first(row, ("labels",)),
                        "response_mapping": _first(row, ("options",)),
                    },
                    # RT units are not established by the inspected header: preserve raw only.
                    response_time=None,
                    metadata={
                        **record.metadata,
                        "adapter": "ds003927_1.0.3_verified_columns_v1",
                        "visibility_ordinal_code": {
                            "unconscious": 0,
                            "glimpse": 1,
                            "conscious": 2,
                        }.get(visibility),
                        "ordinal_code_is_E_probability": False,
                        "RT_response_raw": _first(row, ("RT_response",)),
                        "RT_response_unit_status": "requires_source_verification",
                    },
                )
                record.validate()
            records.append(record)
    participants = {r.subject for r in records}
    if dataset.family == "masked_content_fmri":
        expected = dataset.values.get("expected_participants")
        if isinstance(expected, int) and len(participants) != expected:
            raise IntegrityError(f"ds003927 participant count {len(participants)} != {expected}")
    return records, {
        "event_files": len(files),
        "records": len(records),
        "participants": len(participants),
    }


def harmonize_multisite_working_memory(
    dataset: DatasetConfig,
    data_root: Path,
) -> tuple[list[TrialRecord], dict[str, Any]]:
    """Normalize the official OSF clean trial table without reproducing its hard PAS binning."""

    source = data_root / "Data" / "uWM_012_Clean_Data.csv"
    if not source.is_file():
        raise IntegrityError(f"Expected official clean table is missing: {source}")
    required = {
        "laboratory",
        "participant",
        "subjID",
        "session",
        "trial",
        "phase",
        "cueType",
        "oriMemo",
        "gyre",
        "oriTest",
        "contrast",
        "WMresp",
        "WMacc",
        "PASresp",
    }
    records: list[TrialRecord] = []
    laboratories: set[str] = set()
    subjects: set[str] = set()
    phase_counts: dict[str, int] = {}
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise IntegrityError(f"Working-memory clean table lacks columns: {sorted(missing)}")
        for index, row in enumerate(reader, start=2):
            lab = row["laboratory"]
            subject = row["subjID"]
            phase = row["phase"]
            laboratories.add(lab)
            subjects.add(subject)
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
            cue = _float(row.get("cueType"))
            cue_label = {0.0: "cue_absent", 1.0: "cue_present", 2.0: "supraliminal"}.get(
                cue, "not_applicable"
            )
            trial = _float(row.get("trial"))
            record = TrialRecord(
                dataset_family=dataset.family,
                modality="behavior",
                site=f"laboratory-{lab}",
                subject=f"subj-{subject}",
                session=f"ses-{row['session']}",
                run=f"phase-{phase}",
                event_id=f"row-{index}",
                time_reference=float(trial if trial is not None else index - 2),
                condition=f"{phase}:{cue_label}",
                stimulus_id=None,
                stimulus_features={
                    "cue_type": cue,
                    "memory_orientation_deg": _float(row.get("oriMemo")),
                    "test_orientation_deg": _float(row.get("oriTest")),
                    "rotation_direction": _float(row.get("gyre")),
                    "contrast": _float(row.get("contrast")),
                },
                response=row.get("WMresp") if row.get("WMresp") not in {None, "", "NA"} else None,
                response_time=None,
                correctness=_float(row.get("WMacc")),
                observed_experience=_float(row.get("PASresp")),
                arousal_state=None,
                report_availability="available"
                if _float(row.get("PASresp")) is not None
                else "unknown",
                qc_status="pending",
                metadata={
                    "source_file": "Data/uWM_012_Clean_Data.csv",
                    "source_row": index,
                    "participant_within_laboratory": row["participant"],
                    "block": _float(row.get("block")),
                    "language": row.get("language"),
                    "payment": row.get("payment"),
                    "age": _float(row.get("age")),
                    "gender": row.get("gender"),
                    "time_reference_unit": "trial_index",
                },
            )
            record.validate()
            records.append(record)
    expected_participants = dataset.values.get("expected_participants")
    expected_sites = dataset.values.get("expected_sites")
    if isinstance(expected_participants, int) and len(subjects) != expected_participants:
        raise IntegrityError(
            f"Working-memory participant count {len(subjects)} "
            f"!= configured {expected_participants}"
        )
    if isinstance(expected_sites, int) and len(laboratories) != expected_sites:
        raise IntegrityError(
            f"Working-memory laboratory count {len(laboratories)} != configured {expected_sites}"
        )
    return records, {
        "source_file": str(source),
        "records": len(records),
        "participants": len(subjects),
        "laboratories": len(laboratories),
        "phase_counts": phase_counts,
    }


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
    if dataset.family == "multisite_working_memory":
        records, details = harmonize_multisite_working_memory(dataset, data_root)
        write_jsonl(output_path, (asdict(record) for record in records))
        report.update(details)
        report["status"] = "harmonized"
    elif dataset.source_type == "openneuro" or (
        dataset.source_type == "cogitate_account"
        and (data_root / "dataset_description.json").exists()
    ):
        records, details = harmonize_bids_events(dataset, data_root)
        write_jsonl(output_path, (asdict(record) for record in records))
        report.update(details)
        report["status"] = "harmonized" if records else "no_events_found"
    else:
        write_jsonl(output_path, [])
        report["status"] = "adapter_requires_downloaded_schema_inspection"
        report["reason"] = (
            "non-BIDS adapter remains explicit until the downloaded release schema is validated"
        )
    atomic_write_json(report_path, report)
    return report
