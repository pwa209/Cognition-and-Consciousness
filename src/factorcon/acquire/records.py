"""Normalized upstream file records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from factorcon.errors import IntegrityError
from factorcon.util import safe_relative_path


@dataclass(frozen=True, slots=True)
class FileRecord:
    """One versioned upstream object destined for a relative local path."""

    family: str
    snapshot: str
    relative_path: str
    url: str
    size: int | None = None
    checksum_algorithm: str | None = None
    checksum: str | None = None
    source_id: str | None = None
    annexed: bool | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        safe_relative_path(self.relative_path)
        if not self.url.startswith(("https://", "http://")):
            raise IntegrityError(f"Unsupported download URL: {self.url!r}")
        if self.size is not None and self.size < 0:
            raise IntegrityError(f"Negative size for {self.relative_path}")
        if bool(self.checksum_algorithm) != bool(self.checksum):
            raise IntegrityError("checksum algorithm and value must be supplied together")

    def as_dict(self) -> dict[str, Any]:
        """Convert to a JSON-compatible dictionary."""

        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FileRecord":
        """Construct and validate a record loaded from JSON Lines."""

        return cls(**value)

