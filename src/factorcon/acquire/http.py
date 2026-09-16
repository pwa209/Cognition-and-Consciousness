"""Concurrent, resumable, integrity-checked HTTP downloader."""

from __future__ import annotations

import http.client
import json
import os
import random
import re
import shutil
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factorcon.acquire.net import USER_AGENT
from factorcon.acquire.records import FileRecord
from factorcon.errors import CapacityError, IntegrityError, SourceError
from factorcon.util import atomic_write_json, ensure_within, hash_file, safe_relative_path, utc_now


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Verified local result for one upstream object."""

    relative_path: str
    status: str
    bytes: int
    sha256: str
    mtime_ns: int
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
    reserve_bytes: int = 0,
    space_check_interval: int = 1 << 30,
    storage_guard: Callable[[int], None] | None = None,
) -> DownloadResult:
    """Download an upstream object with resume, confinement and atomic promotion.

    ``storage_guard`` receives imminent write sizes in bytes (zero before transfer),
    and may raise CapacityError before writing. No scientific labels are inspected.
    """

    root = Path(destination_root)
    relative = safe_relative_path(record.relative_path)
    final = ensure_within(root, root / relative)
    partial = final.with_name(final.name + ".part")
    final.parent.mkdir(parents=True, exist_ok=True)
    if reserve_bytes < 0:
        raise ValueError("reserve_bytes must be nonnegative")
    if storage_guard is not None:
        storage_guard(0)

    valid, sha256 = _verify_existing(final, record)
    if valid and sha256 is not None:
        return DownloadResult(
            record.relative_path,
            "already_verified",
            final.stat().st_size,
            sha256,
            final.stat().st_mtime_ns,
            utc_now(),
            0,
        )
    if reserve_bytes and shutil.disk_usage(root).free <= reserve_bytes:
        raise CapacityError(f"Free-space reserve reached at {root}")

    if final.exists():
        quarantine = final.with_name(final.name + f".invalid-{int(time.time())}")
        os.replace(final, quarantine)

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity"}
        pinned_etag = (record.metadata or {}).get("http_etag")
        if pinned_etag:
            headers["If-Match"] = str(pinned_etag)
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
                response_headers = getattr(response, "headers", {})
                if pinned_etag and response_headers.get("ETag") != pinned_etag:
                    raise IntegrityError("HTTP object ETag changed or is missing")
                length_header = response_headers.get("Content-Length")
                expected_response_bytes = (
                    int(length_header.strip())
                    if isinstance(length_header, str) and length_header.strip().isdigit()
                    else None
                )
                expected_total_bytes: int | None = None
                content_range = response_headers.get("Content-Range")
                if status == 206 and isinstance(content_range, str):
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range.strip())
                    if match is None or int(match.group(1)) != offset:
                        raise IntegrityError(f"Invalid Content-Range for {record.relative_path}")
                    range_bytes = int(match.group(2)) - int(match.group(1)) + 1
                    if (
                        expected_response_bytes is not None
                        and range_bytes != expected_response_bytes
                    ):
                        raise IntegrityError(f"Conflicting HTTP lengths for {record.relative_path}")
                    expected_response_bytes = range_bytes
                    if match.group(3) != "*":
                        expected_total_bytes = int(match.group(3))
                mode = "ab" if offset else "wb"
                with partial.open(mode) as handle:
                    bytes_since_space_check = 0
                    response_bytes = 0
                    while chunk := response.read(chunk_size):
                        if storage_guard is not None:
                            storage_guard(len(chunk))
                        response_bytes += len(chunk)
                        bytes_since_space_check += len(chunk)
                        if reserve_bytes and bytes_since_space_check >= space_check_interval:
                            if shutil.disk_usage(root).free - len(chunk) <= reserve_bytes:
                                raise CapacityError(f"Free-space reserve reached at {root}")
                            bytes_since_space_check = 0
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
            if expected_response_bytes is not None and response_bytes != expected_response_bytes:
                raise IntegrityError(
                    f"Truncated HTTP body for {record.relative_path}: "
                    f"expected {expected_response_bytes}, got {response_bytes}"
                )
            size = partial.stat().st_size
            if expected_total_bytes is not None and size != expected_total_bytes:
                raise IntegrityError(
                    f"Range total mismatch for {record.relative_path}: "
                    f"expected {expected_total_bytes}, got {size}"
                )
            if record.size is not None and size != record.size:
                raise IntegrityError(
                    f"Size mismatch for {record.relative_path}: expected {record.size}, got {size}"
                )
            if record.checksum:
                observed = hash_file(partial, record.checksum_algorithm or "sha256")
                if observed.lower() != record.checksum.lower():
                    raise IntegrityError(
                        f"Checksum mismatch for {record.relative_path}: "
                        f"expected {record.checksum}, got {observed}"
                    )
            sha256 = hash_file(partial, "sha256")
            os.replace(partial, final)
            return DownloadResult(
                record.relative_path,
                "downloaded",
                size,
                sha256,
                final.stat().st_mtime_ns,
                utc_now(),
                attempt,
            )
        except urllib.error.HTTPError as exc:
            last_error = exc
            complete_size = record.size
            if exc.code == 416 and complete_size is None:
                content_range = exc.headers.get("Content-Range") if exc.headers else None
                match = (
                    re.fullmatch(r"bytes \*/(\d+)", content_range.strip())
                    if isinstance(content_range, str)
                    else None
                )
                if match is not None:
                    complete_size = int(match.group(1))
            if (
                exc.code == 416
                and (not pinned_etag or exc.headers.get("ETag") == pinned_etag)
                and complete_size is not None
                and partial.exists()
                and partial.stat().st_size == complete_size
            ):
                if record.checksum:
                    observed = hash_file(partial, record.checksum_algorithm or "sha256")
                    if observed.lower() != record.checksum.lower():
                        partial.unlink(missing_ok=True)
                        last_error = IntegrityError(
                            f"Checksum mismatch for complete partial {record.relative_path}"
                        )
                        if attempt < attempts:
                            continue
                        break
                sha256 = hash_file(partial, "sha256")
                os.replace(partial, final)
                return DownloadResult(
                    record.relative_path,
                    "resumed_verified",
                    complete_size,
                    sha256,
                    final.stat().st_mtime_ns,
                    utc_now(),
                    attempt,
                )
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                break
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
            IntegrityError,
            SourceError,
        ) as exc:
            last_error = exc
            if isinstance(exc, IntegrityError):
                partial.unlink(missing_ok=True)
        if attempt < attempts:
            time.sleep(min(60.0, (2 ** min(attempt, 6)) + random.random()))
    raise SourceError(
        f"Failed to download {record.relative_path} after {attempts} attempts: {last_error}"
    )


def _load_completion_cache(
    event_log: Path, source_manifest_sha256: str | None
) -> dict[str, dict[str, Any]]:
    """Load the latest same-manifest completion record for efficient crash recovery."""

    if source_manifest_sha256 is None or not event_log.is_file():
        return {}
    cached: dict[str, dict[str, Any]] = {}
    with event_log.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("source_manifest_sha256") != source_manifest_sha256:
                continue
            relative_path = event.get("relative_path")
            if not isinstance(relative_path, str):
                continue
            if event.get("event") == "file_complete":
                cached[relative_path] = event
            elif event.get("event") == "file_failed":
                cached.pop(relative_path, None)
    return cached


def _cached_result(
    record: FileRecord,
    destination_root: Path,
    cached: dict[str, Any] | None,
) -> DownloadResult | None:
    """Trust a same-manifest SHA event only while size and modification time are unchanged."""

    if cached is None:
        return None
    final = ensure_within(
        destination_root,
        destination_root / safe_relative_path(record.relative_path),
    )
    if not final.is_file():
        return None
    stat = final.stat()
    if record.size is not None and stat.st_size != record.size:
        return None
    if stat.st_size != cached.get("bytes") or stat.st_mtime_ns != cached.get("mtime_ns"):
        return None
    digest = cached.get("sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        return None
    return DownloadResult(
        relative_path=record.relative_path,
        status="ledger_verified",
        bytes=stat.st_size,
        sha256=digest,
        mtime_ns=stat.st_mtime_ns,
        completed_utc=utc_now(),
        attempts=0,
    )


def download_many(
    records: list[FileRecord],
    destination_root: str | Path,
    ledger_path: str | Path,
    *,
    workers: int = 4,
    reserve_bytes: int = 0,
    source_manifest_sha256: str | None = None,
    storage_guard: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Download records with bounded concurrency and durable per-file provenance.

    Scientific labels are not read here. The integrity boundary is one upstream object.
    The compact JSON ledger is checkpointed periodically; append-only JSONL events retain
    every observed SHA-256 without repeatedly rewriting an O(number-of-files) object.
    """

    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")
    complete = 0
    completed_bytes = 0
    failures: dict[str, str] = {}
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    event_log = ledger.with_name(f"{ledger.stem}.events.jsonl")
    run_started = utc_now()
    destination_path = Path(destination_root)
    cached = _load_completion_cache(event_log, source_manifest_sha256)
    remaining_records: list[FileRecord] = []
    cache_verified = 0
    for record in records:
        cached_value = _cached_result(record, destination_path, cached.get(record.relative_path))
        if cached_value is None:
            remaining_records.append(record)
        else:
            complete += 1
            completed_bytes += cached_value.bytes
            cache_verified += 1

    def checkpoint(*, final: bool) -> dict[str, Any]:
        summary = {
            "updated_utc": utc_now(),
            "run_started_utc": run_started,
            "destination_root": str(Path(destination_root)),
            "total": len(records),
            "processed": complete + len(failures),
            "complete": complete,
            "failed": len(failures),
            "bytes": completed_bytes,
            "cache_verified": cache_verified,
            "success": final and not failures and complete == len(records),
            "final": final,
            "stopped_early": final and complete + len(failures) < len(records),
            "event_log": str(event_log),
            "source_manifest_sha256": source_manifest_sha256,
            "failures": dict(sorted(failures.items())),
        }
        atomic_write_json(ledger, summary)
        return summary

    def write_event(handle: Any, value: dict[str, Any]) -> None:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")

    checkpoint(final=False)
    with event_log.open("a", encoding="utf-8", newline="\n") as events:
        write_event(
            events,
            {
                "event": "run_started",
                "run_started_utc": run_started,
                "destination_root": str(Path(destination_root)),
                "total": len(records),
                "cache_verified": cache_verified,
                "source_manifest_sha256": source_manifest_sha256,
            },
        )
        events.flush()
        os.fsync(events.fileno())
        last_checkpoint = time.monotonic()
        processed_at_checkpoint = 0
        iterator = iter(remaining_records)

        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="factorcon-download"
        ) as pool:
            pending = {}
            stop_submitting = False

            def submit_one() -> bool:
                try:
                    record = next(iterator)
                except StopIteration:
                    return False
                guarded = {"storage_guard": storage_guard} if storage_guard is not None else {}
                pending[
                    pool.submit(
                        download_one,
                        record,
                        destination_root,
                        reserve_bytes=reserve_bytes,
                        **guarded,
                    )
                ] = record
                return True

            for _ in range(min(len(remaining_records), workers * 2)):
                submit_one()

            while pending:
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    record = pending.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:  # finish other records; fail family below
                        error = f"{type(exc).__name__}: {exc}"
                        failures[record.relative_path] = error
                        if isinstance(exc, CapacityError):
                            stop_submitting = True
                        write_event(
                            events,
                            {
                                "event": "file_failed",
                                "recorded_utc": utc_now(),
                                "relative_path": record.relative_path,
                                "error": error,
                                "source_manifest_sha256": source_manifest_sha256,
                            },
                        )
                    else:
                        complete += 1
                        completed_bytes += result.bytes
                        write_event(
                            events,
                            {
                                "event": "file_complete",
                                "recorded_utc": utc_now(),
                                "source_manifest_sha256": source_manifest_sha256,
                                **asdict(result),
                            },
                        )
                    if not stop_submitting:
                        submit_one()

                if stop_submitting:
                    for future in list(pending):
                        if future.cancel():
                            pending.pop(future)

                processed = complete + len(failures)
                if (
                    processed - processed_at_checkpoint >= 256
                    or time.monotonic() - last_checkpoint >= 30
                ):
                    events.flush()
                    os.fsync(events.fileno())
                    checkpoint(final=False)
                    processed_at_checkpoint = processed
                    last_checkpoint = time.monotonic()

        write_event(
            events,
            {
                "event": "run_finished",
                "recorded_utc": utc_now(),
                "run_started_utc": run_started,
                "complete": complete,
                "failed": len(failures),
                "cache_verified": cache_verified,
                "source_manifest_sha256": source_manifest_sha256,
            },
        )
        events.flush()
        os.fsync(events.fileno())

    summary = checkpoint(final=True)
    summary["ledger"] = str(ledger)
    if failures:
        raise SourceError(f"{len(failures)} of {len(records)} downloads failed; see {ledger}")
    return summary
