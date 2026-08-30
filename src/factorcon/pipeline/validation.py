"""Family-level downloaded-byte, archive, and BIDS validation."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path
from typing import Any

from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig, ProjectConfig
from factorcon.errors import ConfigError, IntegrityError
from factorcon.io.bids import inventory_bids
from factorcon.util import (
    atomic_write_json,
    hash_file,
    read_jsonl,
    safe_relative_path,
    slug,
    utc_now,
)


def _dataset(project: ProjectConfig, family: str) -> DatasetConfig:
    try:
        return next(item for item in project.datasets if item.family == family)
    except StopIteration as exc:
        raise ConfigError(f"Unknown family: {family}") from exc


def _check_archive(path: Path) -> dict[str, Any]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as handle:
            members = handle.infolist()
            for member in members:
                safe_relative_path(member.filename)
            return {
                "type": "zip",
                "members": len(members),
                "declared_bytes": sum(member.file_size for member in members),
                "test_result": handle.testzip(),
            }
    if tarfile.is_tarfile(path):
        with tarfile.open(path, mode="r:*") as handle:
            members = handle.getmembers()
            for member in members:
                safe_relative_path(member.name)
                if not member.isfile() and not member.isdir():
                    raise IntegrityError(f"Unsafe TAR member type in {path}: {member.name}")
            return {
                "type": "tar",
                "members": len(members),
                "declared_bytes": sum(member.size for member in members if member.isfile()),
            }
    return {"type": "not_archive"}


def validate_family(
    project: ProjectConfig,
    canonical_root: str | Path,
    family: str,
    output: str | Path,
    *,
    deep_hash: bool = False,
) -> dict[str, Any]:
    """Validate one resolved/downloaded family and write a complete issue report."""

    dataset = _dataset(project, family)
    root = Path(canonical_root)
    snapshot = slug(dataset.snapshot_label)
    manifest = root / "manifests" / "generated" / slug(family) / f"{snapshot}.jsonl"
    report: dict[str, Any] = {
        "family": family,
        "snapshot": dataset.snapshot_label,
        "checked_utc": utc_now(),
        "access": dataset.access,
        "deep_hash": deep_hash,
        "errors": [],
        "warnings": [],
        "files": 0,
        "bytes": 0,
        "archives": {},
    }
    if dataset.access == "account_and_terms_required" and not manifest.exists():
        report["status"] = "waiting_access"
        atomic_write_json(output, report)
        return report
    if not manifest.is_file():
        raise IntegrityError(f"Missing source manifest: {manifest}")
    data_root = root / "data" / "raw" / slug(family) / snapshot
    for value in read_jsonl(manifest):
        record = FileRecord.from_dict(value)
        path = data_root / safe_relative_path(record.relative_path)
        if not path.is_file():
            report["errors"].append({"path": record.relative_path, "issue": "missing"})
            continue
        size = path.stat().st_size
        report["files"] += 1
        report["bytes"] += size
        if record.size is not None and size != record.size:
            report["errors"].append(
                {
                    "path": record.relative_path,
                    "issue": "size_mismatch",
                    "expected": record.size,
                    "observed": size,
                }
            )
            continue
        if deep_hash and record.checksum:
            observed = hash_file(path, record.checksum_algorithm or "sha256")
            if observed.lower() != record.checksum.lower():
                report["errors"].append(
                    {
                        "path": record.relative_path,
                        "issue": "checksum_mismatch",
                        "observed": observed,
                    }
                )
        if path.name.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")):
            try:
                report["archives"][record.relative_path] = _check_archive(path)
            except (IntegrityError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
                report["errors"].append(
                    {"path": record.relative_path, "issue": "archive_invalid", "detail": str(exc)}
                )
    if dataset.source_type == "openneuro" and not report["errors"]:
        try:
            bids = inventory_bids(data_root)
        except IntegrityError as exc:
            report["errors"].append({"issue": "bids_identity", "detail": str(exc)})
        else:
            report["bids"] = {
                "name": bids.name,
                "version": bids.bids_version,
                "dataset_type": bids.dataset_type,
                "participants": len(bids.participants),
                "event_files": len(bids.event_files),
                "modalities": list(bids.modalities),
            }
            expected = dataset.values.get("expected_participants")
            if isinstance(expected, int) and len(bids.participants) != expected:
                report["warnings"].append(
                    {
                        "issue": "participant_count",
                        "expected": expected,
                        "observed": len(bids.participants),
                    }
                )
    report["status"] = "valid" if not report["errors"] else "invalid"
    atomic_write_json(output, report)
    return report
