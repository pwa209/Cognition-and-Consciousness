"""Filesystem RPC for large-file digest computation on allocated compute nodes.

Requests are declarative paths/algorithms, never commands or downloaded code.
Only same-run raw files are allowed. Byte size and mtime bind every result.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from factorcon.errors import IntegrityError, SourceError
from factorcon.util import atomic_write_json, ensure_within


def queued_hash(path: Path, algorithm: str, directory: Path, timeout: float = 21600) -> str:
    """Return a digest bound to unchanged same-run bytes; wait at most timeout seconds.

    Called only for large acquisition files. No scientific labels are consulted.
    """
    if algorithm not in {"sha256", "md5"}:
        raise IntegrityError("Unsupported acquisition hash algorithm")
    directory = directory.resolve()
    root = directory.parent.parent
    path = ensure_within(root / "data/raw", path.resolve())
    before = path.stat()
    identity = uuid.uuid4().hex
    request = {
        "path": str(path),
        "algorithm": algorithm,
        "size": before.st_size,
        "mtime_ns": before.st_mtime_ns,
    }
    atomic_write_json(directory / "requests" / f"{identity}.json", request)
    result = directory / "results" / f"{identity}.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if result.exists():
            value = json.loads(result.read_text())
            after = path.stat()
            if (
                value.get("request") != request
                or value.get("status") != "SUCCESS"
                or (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns)
            ):
                raise SourceError("Scheduled hash failed or file changed; partial retained")
            digest = value["digest"]
            import re

            if (
                re.fullmatch("[0-9a-f]{64}" if algorithm == "sha256" else "[0-9a-f]{32}", digest)
                is None
            ):
                raise IntegrityError("Malformed scheduled digest")
            return digest
        time.sleep(2)
    raise SourceError("Scheduled hash timed out; file retained for restart")
