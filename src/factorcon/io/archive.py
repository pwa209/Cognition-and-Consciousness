"""Path-confined extraction for downloaded ZIP and TAR archives."""

from __future__ import annotations

import os
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from factorcon.errors import IntegrityError
from factorcon.util import ensure_within, safe_relative_path


@dataclass(frozen=True, slots=True)
class ExtractionSummary:
    """Safe extraction counts and total uncompressed bytes."""

    archive: str
    destination: str
    files: int
    directories: int
    bytes: int


def _copy_stream(source: object, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        shutil.copyfileobj(source, output, length=8 << 20)  # type: ignore[arg-type]
    return destination.stat().st_size


def _extract_zip(archive: Path, root: Path, max_bytes: int) -> ExtractionSummary:
    files = directories = total = 0
    with zipfile.ZipFile(archive) as handle:
        declared = sum(item.file_size for item in handle.infolist())
        if declared > max_bytes:
            raise IntegrityError(f"ZIP exceeds extraction budget: {declared} > {max_bytes}")
        for item in handle.infolist():
            relative = safe_relative_path(item.filename)
            target = ensure_within(root, root / relative)
            mode = (item.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise IntegrityError(f"ZIP symlink rejected: {item.filename}")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                directories += 1
                continue
            if target.exists():
                raise IntegrityError(f"Extraction target already exists: {target}")
            with handle.open(item, "r") as source:
                total += _copy_stream(source, target)
            files += 1
    return ExtractionSummary(str(archive), str(root), files, directories, total)


def _extract_tar(archive: Path, root: Path, max_bytes: int) -> ExtractionSummary:
    files = directories = total = 0
    with tarfile.open(archive, mode="r:*") as handle:
        members = handle.getmembers()
        declared = sum(item.size for item in members if item.isfile())
        if declared > max_bytes:
            raise IntegrityError(f"TAR exceeds extraction budget: {declared} > {max_bytes}")
        for item in members:
            relative = safe_relative_path(item.name)
            target = ensure_within(root, root / relative)
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
                directories += 1
                continue
            if not item.isfile():
                raise IntegrityError(
                    f"Non-regular TAR member rejected: {item.name} type={item.type!r}"
                )
            if target.exists():
                raise IntegrityError(f"Extraction target already exists: {target}")
            source = handle.extractfile(item)
            if source is None:
                raise IntegrityError(f"Cannot read TAR member: {item.name}")
            with source:
                total += _copy_stream(source, target)
            os.chmod(target, 0o640)
            files += 1
    return ExtractionSummary(str(archive), str(root), files, directories, total)


def extract_archive_safe(
    archive: str | Path,
    destination: str | Path,
    *,
    max_uncompressed_bytes: int = 5_000_000_000_000,
) -> ExtractionSummary:
    """Extract ZIP/TAR without traversal, links, devices, overwrite, or zip bombs."""

    source = Path(archive).resolve()
    root = Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    root.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(source):
        return _extract_zip(source, root, max_uncompressed_bytes)
    if tarfile.is_tarfile(source):
        return _extract_tar(source, root, max_uncompressed_bytes)
    raise IntegrityError(f"Unsupported or corrupt archive: {source}")
