"""Machine-readable provenance records for every operational stage."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factorcon.util import atomic_write_json, git_commit, hash_file, utc_now


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Minimal immutable provenance sidecar."""

    stage: str
    started_utc: str
    ended_utc: str
    status: str
    command: tuple[str, ...]
    code_commit: str | None
    config_sha256: str | None
    inputs: dict[str, str]
    outputs: dict[str, str]
    random_seed: int | None
    python: str
    platform: str
    details: dict[str, Any]


def hash_mapping(value: Mapping[str, Any]) -> str:
    """Hash a JSON-compatible mapping with deterministic serialization."""

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_hashes(paths: Sequence[str | Path]) -> dict[str, str]:
    """Return SHA-256 values for existing regular files."""

    return {str(Path(path)): hash_file(path) for path in paths if Path(path).is_file()}


def write_provenance(
    path: str | Path,
    *,
    stage: str,
    started_utc: str,
    status: str,
    config: Mapping[str, Any] | None = None,
    inputs: Sequence[str | Path] = (),
    outputs: Sequence[str | Path] = (),
    random_seed: int | None = None,
    details: Mapping[str, Any] | None = None,
    repository: str | Path | None = None,
) -> ProvenanceRecord:
    """Create and atomically write a completed stage provenance sidecar."""

    record = ProvenanceRecord(
        stage=stage,
        started_utc=started_utc,
        ended_utc=utc_now(),
        status=status,
        command=tuple(sys.argv),
        code_commit=git_commit(repository),
        config_sha256=hash_mapping(config) if config is not None else None,
        inputs=file_hashes(inputs),
        outputs=file_hashes(outputs),
        random_seed=random_seed,
        python=sys.version,
        platform=platform.platform(),
        details=dict(details or {}),
    )
    atomic_write_json(path, asdict(record))
    return record
