"""Common, modality-neutral data contracts."""

from factorcon.schemas.trial import REQUIRED_TRIAL_FIELDS, TrialRecord, validate_trial_records

__all__ = ["REQUIRED_TRIAL_FIELDS", "TrialRecord", "validate_trial_records"]
