"""Small dependency-free utilities used by acquisition and provenance code."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from factorcon.errors import ConfigError, IntegrityError


def utc_now() -> str:
    """Return a second-resolution RFC 3339 timestamp in UTC."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_structured(path: str | Path) -> dict[str, Any]:
    """Load JSON or YAML; project ``.yaml`` files are intentionally JSON-compatible.

    The leakage boundary is irrelevant here: this function reads configuration only.
    PyYAML is optional and used only when the document is not valid JSON.
    """

    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration {source}: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                f"{source} is not JSON-compatible YAML and PyYAML is not installed"
            ) from exc
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ConfigError(f"Configuration root must be an object: {source}")
    return value


def atomic_write_text(path: str | Path, text: str) -> None:
    """Atomically replace a UTF-8 text file on the same filesystem."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=target.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, target)


def atomic_write_json(path: str | Path, value: Any) -> None:
    """Atomically serialize JSON with deterministic key ordering."""

    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> int:
    """Atomically write dictionaries as deterministic JSON Lines and return row count."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=target.parent, delete=False
    ) as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True, separators=(",", ":")) + "\n")
            count += 1
        temporary = Path(handle.name)
    os.replace(temporary, target)
    return count


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from a UTF-8 JSON Lines file."""

    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise IntegrityError(f"Expected object at {path}:{line_number}")
            yield value


def hash_file(path: str | Path, algorithm: str = "sha256", chunk_size: int = 8 << 20) -> str:
    """Hash a file in bounded memory and return a lowercase hexadecimal digest."""

    queue = os.environ.get("FACTORCON_HASH_QUEUE")
    if queue and Path(path).stat().st_size >= 256 * 1024 * 1024:
        from factorcon.hash_queue import queued_hash

        return queued_hash(Path(path), algorithm, Path(queue))
    digest = hashlib.new(algorithm)
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """Return a hexadecimal digest for in-memory bytes."""

    return hashlib.new(algorithm, data).hexdigest()


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def safe_relative_path(value: str) -> Path:
    """Validate an upstream relative path and return a local platform path.

    Absolute paths, traversal, NULs, URL separators, and Windows drive paths are rejected.
    This is a data-ingestion integrity boundary.
    """

    if not value or "\x00" in value:
        raise IntegrityError("Empty or NUL-containing upstream path")
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if value.startswith(("/", "\\")) or _WINDOWS_DRIVE.match(value):
        raise IntegrityError(f"Absolute upstream path rejected: {value!r}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise IntegrityError(f"Unsafe upstream path rejected: {value!r}")
    return Path(*pure.parts)


def ensure_within(root: str | Path, candidate: str | Path) -> Path:
    """Resolve ``candidate`` and verify it remains inside ``root``."""

    resolved_root = Path(root).resolve()
    resolved_candidate = Path(candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise IntegrityError(
            f"Path escapes root: {resolved_candidate} not in {resolved_root}"
        ) from exc
    return resolved_candidate


def slug(value: str) -> str:
    """Convert a source label to a conservative path component."""

    result = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    if not result:
        raise IntegrityError(f"Cannot derive safe path component from {value!r}")
    return result[:160]


def git_commit(cwd: str | Path | None = None) -> str | None:
    """Return the current Git commit, or ``None`` outside a committed repository."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def env_path(name: str, fallback: str | Path) -> Path:
    """Resolve a project path from an optional environment override."""

    return Path(os.environ.get(name, str(fallback))).expanduser()
