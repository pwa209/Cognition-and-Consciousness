"""Long-form common trial/awakening/state-window schema."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Any, Iterable, Mapping

from factorcon.errors import IntegrityError

REQUIRED_TRIAL_FIELDS = (
    "dataset_family",
    "modality",
    "site",
    "subject",
    "session",
    "run",
    "event_id",
    "time_reference",
    "condition",
    "stimulus_id",
    "stimulus_features",
    "response",
    "response_time",
    "correctness",
    "observed_experience",
    "arousal_state",
    "report_availability",
    "qc_status",
)


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """One normalized trial, awakening, block, or state window.

    Times are seconds in the source-declared reference frame. Missing, instructed
    no-response, and failed-response states must be represented distinctly in metadata.
    """

    dataset_family: str
    modality: str
    site: str
    subject: str
    session: str
    run: str
    event_id: str
    time_reference: float
    condition: str
    stimulus_id: str | None
    stimulus_features: Mapping[str, Any]
    response: str | None
    response_time: float | None
    correctness: float | None
    observed_experience: str | float | None
    arousal_state: str | float | None
    report_availability: str
    qc_status: str
    metadata: Mapping[str, Any]

    def validate(self) -> None:
        """Validate identifiers, finite numeric fields, and categorical contracts."""

        for name in ("dataset_family", "modality", "subject", "event_id", "condition"):
            if not getattr(self, name):
                raise IntegrityError(f"TrialRecord.{name} must be non-empty")
        for name in ("time_reference", "response_time", "correctness"):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise IntegrityError(f"TrialRecord.{name} must be finite or null")
        if self.response_time is not None and self.response_time < 0:
            raise IntegrityError("response_time cannot be negative")
        if self.report_availability not in {
            "available",
            "not_requested",
            "unavailable",
            "failed",
            "unknown",
        }:
            raise IntegrityError(f"Invalid report_availability={self.report_availability!r}")
        if self.qc_status not in {"pending", "include", "exclude", "flag"}:
            raise IntegrityError(f"Invalid qc_status={self.qc_status!r}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TrialRecord":
        """Construct from a mapping while rejecting absent required fields."""

        missing = [name for name in REQUIRED_TRIAL_FIELDS if name not in value]
        if missing:
            raise IntegrityError(f"Missing trial fields: {missing}")
        known = {field.name for field in fields(cls)}
        payload = {key: value[key] for key in known if key in value}
        payload.setdefault("metadata", {key: item for key, item in value.items() if key not in known})
        record = cls(**payload)
        record.validate()
        return record


def validate_trial_records(records: Iterable[Mapping[str, Any]]) -> list[TrialRecord]:
    """Validate records and reject duplicate family/subject/session/run/event keys."""

    validated: list[TrialRecord] = []
    keys: set[tuple[str, str, str, str, str]] = set()
    last_times: dict[tuple[str, str, str, str], float] = {}
    for value in records:
        record = TrialRecord.from_mapping(value)
        key = (
            record.dataset_family,
            record.subject,
            record.session,
            record.run,
            record.event_id,
        )
        if key in keys:
            raise IntegrityError(f"Duplicate event key: {key}")
        keys.add(key)
        run_key = key[:-1]
        previous = last_times.get(run_key)
        if previous is not None and record.time_reference < previous:
            raise IntegrityError(f"Nonmonotonic event time within {run_key}")
        last_times[run_key] = record.time_reference
        validated.append(record)
    return validated

