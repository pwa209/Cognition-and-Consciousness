"""Acquisition-bound empirical integrity and metadata census, never outcome selection."""

from __future__ import annotations

import csv
import io
import json
import re
import stat
import tarfile
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factorcon.acquire.manager import _fingerprint
from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig
from factorcon.errors import IntegrityError
from factorcon.util import (
    atomic_write_json,
    ensure_within,
    hash_file,
    read_jsonl,
    safe_relative_path,
    slug,
    write_jsonl,
)


@dataclass(frozen=True)
class AcquiredInput:
    """Same-run file identities; bytes/counts only, no measured scientific outcomes."""

    family: str
    data_root: Path
    manifest: Path
    ledger: Path
    events: Path
    manifest_sha256: str
    acquisition_identity: str
    records: tuple[FileRecord, ...]
    holds: tuple[dict[str, Any], ...]


def resolve_acquired_input(root: Path, dataset: DatasetConfig) -> AcquiredInput:
    """Bind a complete original/repaired acquisition to its exact manifest, read-only.

    Frozen manifests contain URLs but only their hashes enter exported provenance.
    Private holds are retained; completeness means the authorized manifest, not all
    possible upstream datasets. No scientific data are fit or relabeled here.
    """
    family = dataset.family
    repair = root / "operations/acquisition-repair-v1" / family
    snapshot = "exp1_20231231" if family == "cogitate" else slug(dataset.snapshot_label)
    holds: tuple[dict[str, Any], ...] = ()
    if family in {"cogitate", "dream", "propofol_volition_fmri"}:
        manifest = repair / "manifest.jsonl"
        resolution = json.loads((repair / "resolution.json").read_text())
        identity = hash_file(manifest)
        if resolution["manifest_sha256"] != identity:
            raise IntegrityError("frozen repair manifest changed")
        ledger = repair / "downloads.json"
        holds = tuple(resolution.get("holds", []))
    else:
        manifest = root / "manifests/generated" / family / f"{snapshot}.jsonl"
        ledger = root / "run_state/P02" / f"{family}.{snapshot}.downloads.json"
        identity = ""
    records = tuple(FileRecord.from_dict(v) for v in read_jsonl(manifest))
    if not records or any(r.family != family or slug(r.snapshot) != snapshot for r in records):
        raise IntegrityError("manifest family/snapshot mismatch or empty manifest")
    paths = [r.relative_path for r in records]
    if len(set(paths)) != len(paths):
        raise IntegrityError("duplicate acquisition target")
    receipt = json.loads(ledger.read_text())
    identity = identity or _fingerprint(list(records))
    if (
        receipt.get("success") is not True
        or receipt.get("failed") != 0
        or receipt.get("complete") != len(records)
        or receipt.get("total") != len(records)
        or receipt.get("source_manifest_sha256") != identity
    ):
        raise IntegrityError("complete same-manifest acquisition required")
    expected = dataset.values.get("expected_manifest_files")
    if expected is None and family == "bmvp":
        expected = dataset.values.get("expected_archive_urls")
    if expected is not None and len(records) != expected:
        raise IntegrityError("expected acquisition file count mismatch")
    expected_subjects = dataset.values.get("expected_participants")
    if isinstance(expected_subjects, int):
        subjects = {
            safe_relative_path(r.relative_path).parts[0]
            for r in records
            if safe_relative_path(r.relative_path).parts[0].startswith("sub-")
        }
        if len(subjects) != expected_subjects:
            raise IntegrityError("expected raw participant count mismatch")
    events = ledger.with_suffix(".events.jsonl")
    # download_many uses downloads.events.jsonl, not an arbitrary receipt-supplied path.
    for p in (manifest, ledger, events):
        ensure_within(root, p)
    return AcquiredInput(
        family,
        ensure_within(root, root / "data/raw" / family / snapshot),
        manifest,
        ledger,
        events,
        hash_file(manifest),
        identity,
        records,
        holds,
    )


def completion_records(inputs: AcquiredInput) -> dict[str, dict[str, Any]]:
    """Return final per-file SHA-256 receipts (bytes, nanosecond mtimes), no fitting."""
    result = {}
    for event in read_jsonl(inputs.events):
        if (
            event.get("event") == "file_complete"
            and event.get("source_manifest_sha256") == inputs.acquisition_identity
        ):
            result[event["relative_path"]] = event
    if set(result) != {r.relative_path for r in inputs.records}:
        raise IntegrityError("acquisition completion records do not match the manifest")
    return result


def verify_downloads(
    inputs: AcquiredInput,
    output: Path,
    *,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Rehash every manifest object in bounded memory against acquisition SHA-256.

    Output JSONL is a checkpoint of checked bytes/mtime/digest, not scientific QC.
    A new attempt may rehash from the beginning; old attempts are never overwritten.
    Even files without publisher hashes have local fixity checked; this does not
    turn a local checksum into independent publisher certification.
    """
    receipts = completion_records(inputs)
    checked = total = 0
    with output.open("x", encoding="utf-8") as handle:
        for record in inputs.records:
            path = ensure_within(
                inputs.data_root, inputs.data_root / safe_relative_path(record.relative_path)
            )
            before = path.stat()
            receipt = receipts[record.relative_path]
            expected = receipt.get("sha256", "")
            if (
                not path.is_file()
                or not re.fullmatch("[0-9a-f]{64}", expected)
                or before.st_size != receipt.get("bytes")
                or before.st_mtime_ns != receipt.get("mtime_ns")
                or (record.size is not None and record.size != before.st_size)
            ):
                raise IntegrityError(
                    f"acquisition file fingerprint changed: {record.relative_path}"
                )
            if progress:
                progress(
                    {
                        "stage": "hashing",
                        "file_index": checked + 1,
                        "checked_files": checked,
                        "checked_bytes": total,
                        "current_file": record.relative_path,
                    }
                )
            digest = hash_file(path)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (
                after.st_size,
                after.st_mtime_ns,
            ) or digest != expected:
                raise IntegrityError(f"file changed or SHA-256 mismatch: {record.relative_path}")
            if record.checksum_algorithm == "sha256" and digest != record.checksum.lower():
                raise IntegrityError("publisher SHA-256 mismatch")
            handle.write(
                json.dumps(
                    {
                        "relative_path": record.relative_path,
                        "bytes": after.st_size,
                        "mtime_ns": after.st_mtime_ns,
                        "sha256": digest,
                    }
                )
                + "\n"
            )
            handle.flush()
            checked += 1
            total += after.st_size
    return {"files": checked, "bytes": total, "fixity": "rehash_against_acquisition_sha256"}


def safe_zip_members(handle: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Validate central-directory paths/types, in archive bytes; never extract/execute.

    Duplicate normalized destinations, encryption, links and special files fail.
    Does not claim payload decompression/CRC verification for uninspected members.
    """
    members = handle.infolist()
    seen = set()
    for member in members:
        relative = safe_relative_path(member.filename).as_posix()
        mode = stat.S_IFMT(member.external_attr >> 16)
        if relative in seen or member.flag_bits & 1 or mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise IntegrityError(f"unsafe/duplicate/encrypted archive member: {relative}")
        seen.add(relative)
    return members


def safe_tar_members(handle: tarfile.TarFile) -> list[tarfile.TarInfo]:
    """Validate TAR paths/regular types without extracting; sizes have units bytes."""
    members = handle.getmembers()
    seen = set()
    for member in members:
        # An archive's explicit root-directory marker is not an extraction target.
        if member.isdir() and member.name in {".", "./"}:
            continue
        relative = safe_relative_path(member.name).as_posix()
        if relative in seen or not (member.isfile() or member.isdir()):
            raise IntegrityError(f"unsafe/duplicate TAR member: {relative}")
        seen.add(relative)
    return members


def summarize_metadata(name: str, payload: bytes) -> dict[str, Any]:
    """Describe table/JSON schema without exporting participant rows or fitting labels.

    Table counts have units rows; field names are upstream schema. No data paths or
    executable content read from a cell are followed. Invalid encodings are explicit.
    """
    text = payload.decode("utf-8-sig")
    if name.endswith((".tsv", ".csv")):
        reader = csv.DictReader(io.StringIO(text), delimiter="\t" if name.endswith(".tsv") else ",")
        fields = reader.fieldnames or []
        if not fields or len(set(fields)) != len(fields):
            raise IntegrityError("empty or duplicate table header")
        count = 0
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise IntegrityError("table row width mismatch")
            count += 1
        return {"kind": "table", "fields": fields, "rows": count}
    if name.endswith(".json"):
        value = json.loads(text)
        return {
            "kind": "json",
            "keys": sorted(value) if isinstance(value, dict) else [],
            "root_type": type(value).__name__,
        }
    return {"kind": "text", "characters": len(text)}


def inventory_sources(
    inputs: AcquiredInput, output: Path, *, max_metadata_bytes: int
) -> dict[str, Any]:
    """Inventory files and ZIP members, inspecting bounded text metadata only.

    All outputs stay in personal scratch. Unsupported/binary source formats remain
    counted, not claimed parsed. No neural records are extracted or transformed.
    Metadata parser failures are retained as schema issues, not silent exclusions.
    """
    if max_metadata_bytes <= 0:
        raise ValueError("positive metadata byte limit required")
    totals: Counter[str] = Counter()
    issues = []

    def describe(name: str, size: int, read: Callable[[], bytes]) -> dict[str, Any]:
        result: dict[str, Any] = {"path": name, "bytes": size}
        suffix = "".join(Path(name).suffixes)
        totals[suffix] += 1
        metadata = name.endswith((".tsv", ".csv", ".json")) or Path(name).name.lower().startswith(
            "readme"
        )
        if metadata and size <= max_metadata_bytes:
            try:
                result["schema"] = summarize_metadata(name, read())
            except (UnicodeError, ValueError, IntegrityError, csv.Error) as exc:
                result["schema_error"] = f"{type(exc).__name__}: {exc}"
                issues.append({"path": name, "issue": result["schema_error"]})
        elif metadata:
            result["schema_status"] = "over_metadata_byte_limit"
        return result

    def rows():
        for record in inputs.records:
            path = ensure_within(
                inputs.data_root, inputs.data_root / safe_relative_path(record.relative_path)
            )
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as z:
                    members = safe_zip_members(z)
                    yield {
                        "path": record.relative_path,
                        "kind": "zip",
                        "members": len(members),
                        "uncompressed_bytes": sum(m.file_size for m in members),
                        "full_payload_crc_checked": False,
                    }
                    for m in members:
                        if not m.is_dir():
                            row = describe(m.filename, m.file_size, lambda m=m: z.read(m))
                            yield {"archive": record.relative_path, **row}
            elif path.name.lower().endswith((".tar", ".tar.gz", ".tgz")):
                with tarfile.open(path, "r:*") as tar:
                    members = safe_tar_members(tar)
                    yield {
                        "path": record.relative_path,
                        "kind": "tar",
                        "members": len(members),
                        "uncompressed_bytes": sum(m.size for m in members if m.isfile()),
                    }
                    for m in members:
                        if m.isfile():

                            def read_member(m=m):
                                with tar.extractfile(m) as stream:
                                    return stream.read(max_metadata_bytes + 1)

                            yield {
                                "archive": record.relative_path,
                                **describe(m.name, m.size, read_member),
                            }
            else:
                yield describe(record.relative_path, path.stat().st_size, path.read_bytes)

    count = write_jsonl(output, rows())
    report = {
        "inventory_rows": count,
        "extensions": dict(totals),
        "schema_issues": issues,
        "holds": list(inputs.holds),
        "full_archive_crc_checked": False,
        "neural_preprocessing_validated": False,
    }
    atomic_write_json(output.with_suffix(".summary.json"), report)
    return report
