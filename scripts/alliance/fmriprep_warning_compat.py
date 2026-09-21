"""Narrow Python 3.12 warning-signature repair; never changes numerical processing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from factorcon.util import atomic_write_json, hash_file, utc_now

ORIGINAL = b"def _warn(message, category=None, stacklevel=1, source=None):"
REPLACEMENT = (
    b"def _warn(message, category=None, stacklevel=1, source=None, *, skip_file_prefixes=()):"
)


def patched_bytes(original: bytes, expected_sha256: str) -> bytes:
    """Accept only exact inspected source bytes; alter one signature, not logging or models.

    SHA-256 is over bytes. No participant inputs, fitting, or fold boundaries exist here.
    The original handler already ignores source-location arguments; this additionally
    accepts Python 3.12's location-prefix tuple while retaining every warning message.
    """
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise ValueError("warning source checksum mismatch")
    if original.count(ORIGINAL) != 1:
        raise ValueError("expected exactly one original warning signature")
    return original.replace(ORIGINAL, REPLACEMENT)


def prepare_patch(root: Path, repair: Path, spec: dict[str, Any]) -> Path:
    """Materialize an immutable byte-checked runtime overlay in study personal scratch.

    The source container is read-only and never edited. Existing unequal artifacts
    fail closed; repeated calls with identical bytes are idempotent. No data fitting.
    """
    original = Path(spec["image"]) / spec["container_path"].lstrip("/")
    data = patched_bytes(original.read_bytes(), spec["original_sha256"])
    directory = root / "operations/inode-recovery" / repair.parent.name / "warning-compat"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "_warnings.py"
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError("existing warning patch differs; preserve and investigate")
    else:
        with target.open("xb") as handle:
            handle.write(data)
        target.chmod(0o444)
    record = directory / "provenance.json"
    if not record.exists():
        atomic_write_json(
            record,
            {
                "created_utc": utc_now(),
                "source": str(original),
                "original_sha256": spec["original_sha256"],
                "patched_sha256": hash_file(target),
                "change": "accept_keyword_only_skip_file_prefixes_keep_warning_logging",
                "scientific_changes": False,
            },
        )
    return target


def bind_patch(prefix: list[str], patch: Path, spec: dict[str, Any]) -> list[str]:
    """Add one read-only Python source bind; all container/scientific arguments stay intact."""
    if prefix[:2] != ["apptainer", "exec"] or prefix[-1] != spec["image"]:
        raise ValueError("unexpected fMRIPrep container invocation")
    return [*prefix[:-1], "--bind", f"{patch}:{spec['container_path']}:ro", prefix[-1]]
