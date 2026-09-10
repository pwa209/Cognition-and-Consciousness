"""Machine-readable provenance records for every operational stage."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from functools import wraps
from inspect import signature
from pathlib import Path
from typing import Any
from uuid import uuid4

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


def analysis_artifact(stage: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Record local analysis attempts with atomic status and source/input hashes.

    Wrapped functions accept ``path`` or ``paths``, ``output``, and ``analysis_spec``.
    No scientific outcome controls success. Existing outputs must be given a new
    path, preserving old result versions; failed attempts without output can retry.
    Hashes are provenance only and never enter model fitting or held-out selection.
    """

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            bound = signature(function).bind(*args, **kwargs)
            bound.apply_defaults()
            output = Path(bound.arguments["output"])
            if output.exists():
                raise ValueError(
                    f"Output already exists; preserve it and choose a new path: {output}"
                )
            run_id = uuid4().hex
            started = utc_now()
            state = Path(str(output) + ".status.json")
            sidecar = Path(str(output) + f".runs/{run_id}.provenance.json")
            inputs = (
                bound.arguments["paths"]
                if "paths" in bound.arguments
                else [bound.arguments["path"]]
            )
            config_path = Path(bound.arguments["analysis_spec"])
            source_files = sorted(Path(__file__).parent.rglob("*.py"))
            metadata = {
                "stage": stage,
                "run_id": run_id,
                "started_utc": started,
                "provenance": str(sidecar),
            }
            atomic_write_json(state, {**metadata, "status": "RUNNING"})
            try:
                result = function(*args, **kwargs)
                write_provenance(
                    sidecar,
                    stage=stage,
                    started_utc=started,
                    status="SUCCESS",
                    inputs=[*inputs, config_path, *source_files],
                    outputs=[output],
                    random_seed=bound.arguments.get("seed"),
                    details={"run_id": run_id, "scientific_gate": None},
                )
                atomic_write_json(state, {**metadata, "status": "SUCCESS", "ended_utc": utc_now()})
                return result
            except Exception as exc:
                write_provenance(
                    sidecar,
                    stage=stage,
                    started_utc=started,
                    status="FAILED",
                    inputs=[*inputs, config_path, *source_files],
                    details={"run_id": run_id, "error_type": type(exc).__name__, "error": str(exc)},
                )
                atomic_write_json(state, {**metadata, "status": "FAILED", "ended_utc": utc_now()})
                raise

        return wrapped

    return decorate
