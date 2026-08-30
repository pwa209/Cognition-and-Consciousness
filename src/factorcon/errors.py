"""Project-specific error types."""

from __future__ import annotations


class FactorconError(RuntimeError):
    """Base class for expected operational failures."""


class ConfigError(FactorconError):
    """Raised when declarative configuration violates its contract."""


class AccessRequired(FactorconError):
    """Raised when owner interaction or acceptance of terms is required."""


class IntegrityError(FactorconError):
    """Raised when bytes, metadata, or paths fail integrity checks."""


class CapacityError(FactorconError):
    """Raised before an acquisition would consume the protected storage reserve."""


class SourceError(FactorconError):
    """Raised when an upstream source cannot be resolved safely."""
