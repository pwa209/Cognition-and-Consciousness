"""Concurrent, resumable, integrity-checked HTTP downloader."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factorcon.acquire.net import USER_AGENT
from factorcon.acquire.records import FileRecord
from factorcon.errors import IntegrityError, SourceError
from factorcon.util import atomic_write_json, ensure_within, hash_file, safe_relative_path, utc_now


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Verified local result for one upstream object."""

    relative_path: str
    status: str
    bytes: int
    sha256: str
    completed_utc: str
    attempts: int


def _verify_existing(path: Path, record: FileRecord) -> tuple[bool, str | None]:
    if not path.is_file():
        return False, None
    if record.size is not None and path.stat().st_size != record.size:
        return False, None
    if record.checksum:
        digest = hash_file(path, record.checksum_algorithm or "sha256")
        if digest.lower() != record.checksum.lower():
            return False, None
    return True, hash_file(path, "sha256")


def download_one(
    record: FileRecord,
    destination_root: str | Path,
    *,
    timeout: int = 180,
    attempts: int = 8,
    chunk_size: int = 8 << 20,
) -> DownloadResult:
    """Download one file with resume, path confinement, size/hash checks, and atomic promotion."""

    root = Path(destination_root)
    relative = safe_relative_path(record.relative_path)
    final = ensure_within(root, root / relative)
    partial = final.with_name(final.name + ".part")
    final.parent.mkdir(parents=True, exist_ok=True)

    valid, sha256 = _verify_existing(final, record)
    if valid and sha256 is not None:
        return DownloadResult(record.relative_path, "already_verified", final.stat().st_size, sha256, utc_now(), 0)

    if final.exists():
        quarantine = final.with_name(final.name + f".invalid-{int(time.time())}")
        os.replace(final, quarantine)

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(record.url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(response.status)
                if offset and status != 206:
                    partial.unlink(missing_ok=True)
                    offset = 0
                    raise SourceError("Server ignored Range; partial reset for clean retry")
                mode = "ab" if offset else "wb"
                with partial.open(mode) as handle:
                    while chunk := response.read(chunk_size):
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
            size = partial.stat().st_size
            if record.size is not None and size != record.size:
                raise IntegrityError(
                    f"Size mismatch for {record.relative_path}: expected {record.size}, got {size}"
                )
            if record.checksum:
                observed = hash_file(partial, record.checksum_algorithm or "sha256")
                if observed.lower() != record.checksum.lower():
                    raise IntegrityError(
                        f"Checksum mismatch for {record.relative_path}: expected {record.checksum}, got {observed}"
                    )
            sha256 = hash_file(partial, "sha256")
            os.replace(partial, final)
            return DownloadResult(record.relative_path, "downloaded", size, sha256, utc_now(), attempt)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 416 and record.size is not None and partial.exists() and partial.stat().st_size == record.size:
                sha256 = hash_file(partial, "sha256")
                os.replace(partial, final)
                return DownloadResult(record.relative_path, "resumed_verified", record.size, sha256, utc_now(), attempt)
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                break
        except (urllib.error.URLError, TimeoutError, OSError, IntegrityError, SourceError) as exc:
            last_error = exc
            if isinstance(exc, IntegrityError):
                partial.unlink(missing_ok=True)
        if attempt < attempts:
            time.sleep(min(60.0, (2 ** min(attempt, 6)) + random.random()))
    raise SourceError(f"Failed to download {record.relative_path} after {attempts} attempts: {last_error}")


def download_many(
    records: list[FileRecord],
    destination_root: str | Path,
    ledger_path: str | Path,
    *,
    workers: int = 4,
) -> dict[str, Any]:
    """Download records concurrently and maintain an atomic completion ledger.

    Scientific labels are not read here. The integrity boundary is one upstream object.
    """

    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")
    results: dict[str, DownloadResult] = {}
    failures: dict[str, str] = {}
    ledger = Path(ledger_path)

    def checkpoint() -> None:
        atomic_write_json(
            ledger,
            {
                "updated_utc": utc_now(),
                "destination_root": str(Path(destination_root)),
                "total": len(records),
                "complete": len(results),
                "failed": len(failures),
                "results": {key: asdict(value) for key, value in sorted(results.items())},
                "failures": dict(sorted(failures.items())),
            },
        )

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="factorcon-download") as pool:
        futures = {pool.submit(download_one, record, destination_root): record for record in records}
        for future in as_completed(futures):
            record = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # each failure is recorded; family status is decided below
                failures[record.relative_path] = f"{type(exc).__name__}: {exc}"
            else:
                results[record.relative_path] = result
            checkpoint()
    summary = {
        "total": len(records),
        "complete": len(results),
        "failed": len(failures),
        "bytes": sum(item.bytes for item in results.values()),
        "success": not failures and len(results) == len(records),
        "ledger": str(ledger),
    }
    if failures:
        raise SourceError(f"{len(failures)} of {len(records)} downloads failed; see {ledger}")
    return summary

