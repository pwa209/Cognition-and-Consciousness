"""Verified consolidation of quiescent MRI work or retired environments, never research inputs."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tarfile
from pathlib import Path
from typing import Any, BinaryIO

from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def work_target(root: Path, work: Path) -> Path:
    """Accept only an exact study MRI attempt/work directory, without redirected parents."""
    expected = root / "analysis/masked-neural/PREPROCESS"
    if (
        root.resolve() != root
        or work.resolve() != work
        or work.name != "work"
        or work.parent.parent != expected
        or not re.fullmatch(r"\d+-\d+", work.parent.name)
    ):
        raise ValueError("only an unredirected numeric MRI attempt/work tree is permitted")
    return work


def environment_target(root: Path, environment: Path) -> Path:
    """Accept only numeric qualification environments; explicitly protect current MRI/P05 runtimes.

    The caller additionally checks live scheduler consumers. This function never
    permits raw data, derivatives, source releases or the named PyMC environment.
    """
    if (
        root.resolve() != root
        or environment.resolve() != environment
        or environment.parent != root / "environments"
        or not re.fullmatch(r"qualification-\d+", environment.name)
        or environment.name in {"qualification-21169236", "qualification-21417196"}
    ):
        raise ValueError("only an inactive numeric qualification environment is permitted")
    return environment


def _target(root: Path, path: Path, category: str) -> None:
    if category == "mri-work":
        work_target(root, path)
    elif category == "environments":
        environment_target(root, path)
    else:
        raise ValueError("unknown archive category")


def identity(path: Path) -> dict[str, Any]:
    """Capture non-followed filesystem identity, bytes and modification metadata, not outcomes."""
    s = path.lstat()
    kind = (
        "directory"
        if stat.S_ISDIR(s.st_mode)
        else "symlink"
        if stat.S_ISLNK(s.st_mode)
        else "file"
        if stat.S_ISREG(s.st_mode)
        else "special"
    )
    if kind == "special":
        raise ValueError("special filesystem object cannot be archived")
    return {
        "kind": kind,
        "bytes": s.st_size if kind == "file" else 0,
        "mode": stat.S_IMODE(s.st_mode),
        "inode": s.st_ino,
        "device": s.st_dev,
        "mtime_ns": s.st_mtime_ns,
        "ctime_ns": s.st_ctime_ns,
        "link": os.readlink(path) if kind == "symlink" else None,
    }


def inventory(root: Path, work: Path, *, category: str = "mri-work") -> dict[str, dict[str, Any]]:
    """Enumerate a quiescent scoped tree; only environment links may point to read-only CVMFS."""
    _target(root, work, category)
    rows = {work.name: identity(work)}
    for folder, dirs, files in os.walk(work, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(folder) / name
            row = identity(path)
            if (
                row["kind"] == "symlink"
                and not path.resolve().is_relative_to(root)
                and (
                    category != "environments"
                    or not path.resolve().is_relative_to(Path("/cvmfs"))
                )
            ):
                raise ValueError("archive link resolves outside approved study/software roots")
            rows[path.relative_to(work.parent).as_posix()] = row
    return dict(sorted(rows.items()))


class _HashReader:
    def __init__(self, handle: BinaryIO) -> None:
        self.handle, self.digest = handle, hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        value = self.handle.read(size)
        self.digest.update(value)
        return value


def verify_archive(archive: Path, rows: dict[str, dict[str, Any]]) -> str:
    """Read every archive payload and verify exact member inventory, metadata and SHA-256."""
    seen = set()
    with archive.open("rb") as source:
        archive_stream = _HashReader(source)
        with tarfile.open(fileobj=archive_stream, mode="r|", bufsize=8 << 20) as tar:
            for member in tar:
                _verify_member(tar, member, rows, seen)
        while archive_stream.read(8 << 20):
            pass
        digest = archive_stream.digest.hexdigest()
    if seen != rows.keys():
        raise ValueError("archive inventory incomplete")
    return digest


def _verify_member(
    tar: tarfile.TarFile, member: tarfile.TarInfo, rows: dict[str, dict[str, Any]], seen: set[str]
) -> None:
    name = member.name.rstrip("/")
    if name not in rows or name in seen or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("unexpected, duplicate or unsafe archive member")
    seen.add(name)
    row = rows[name]
    if member.mode != row["mode"]:
        raise ValueError("archive mode mismatch")
    if row["kind"] == "directory":
        if not member.isdir():
            raise ValueError("archive directory mismatch")
    elif row["kind"] == "symlink":
        if not member.issym() or member.linkname != row["link"]:
            raise ValueError("archive link mismatch")
    else:
        if not member.isfile() or member.size != row["bytes"]:
            raise ValueError("archive size/type mismatch")
        handle = tar.extractfile(member)
        if handle is None:
            raise ValueError("archive payload missing")
        digest = hashlib.sha256()
        while chunk := handle.read(8 << 20):
            digest.update(chunk)
        if digest.hexdigest() != row["sha256"]:
            raise ValueError("archive checksum mismatch")


def pack(
    root: Path,
    work: Path,
    destination: Path,
    *,
    dry_run: bool = False,
    category: str = "mri-work",
) -> dict[str, Any]:
    """Create a new verified tar plus manifest; never remove originals in this operation.

    Caller must establish job quiescence. No raw/derivative data are targeted. Bytes
    are copied exactly, with symlinks preserved rather than followed. A failed
    attempt cannot be overwritten; a retry requires another destination directory.
    """
    rows = inventory(root, work, category=category)
    total = sum(row["bytes"] for row in rows.values())
    if destination.resolve() != destination or not destination.is_relative_to(
        root / "archives" / category
    ):
        raise ValueError("archive destination must be inside its scoped study archive category")
    summary = {
        "source": str(work),
        "members": len(rows),
        "source_bytes": total,
        "category": category,
    }
    if dry_run:
        return {**summary, "dry_run": True}
    destination.mkdir(parents=True, exist_ok=False)
    state = {**summary, "status": "RUNNING", "started_utc": utc_now(), "source_removed": False}
    marker = destination / "status.json"
    atomic_write_json(marker, state)
    atomic_write_json(destination / "provenance.json", state)
    try:
        partial = destination / "work.tar.partial"
        with tarfile.open(partial, "x", format=tarfile.PAX_FORMAT) as tar:
            for name, row in rows.items():
                path = work.parent / name
                if identity(path) != {k: v for k, v in row.items() if k != "sha256"}:
                    raise ValueError("source changed before archiving")
                member = tar.gettarinfo(str(path), arcname=name)
                if row["kind"] == "file":
                    member.type, member.linkname, member.size = tarfile.REGTYPE, "", row["bytes"]
                    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                    with os.fdopen(descriptor, "rb") as handle:
                        stream = _HashReader(handle)
                        tar.addfile(member, stream)
                        row["sha256"] = stream.digest.hexdigest()
                else:
                    tar.addfile(member)
                if identity(path) != {k: v for k, v in row.items() if k != "sha256"}:
                    raise ValueError("source changed during archiving")
        with partial.open("r+b") as persisted:
            os.fsync(persisted.fileno())
        archive_digest = verify_archive(partial, rows)
        archive = destination / "work.tar"
        partial.rename(archive)
        atomic_write_json(
            destination / "manifest.json",
            {"schema_version": 1, "source": str(work), "members": rows},
        )
        state.update(
            status="VERIFIED",
            ended_utc=utc_now(),
            archive_sha256=archive_digest,
            manifest_sha256=hash_file(destination / "manifest.json"),
            archive_bytes=archive.stat().st_size,
        )
    except BaseException as exc:
        state.update(status="FAILED", error=f"{type(exc).__name__}: {exc}", ended_utc=utc_now())
        raise
    finally:
        atomic_write_json(marker, state)
        atomic_write_json(destination / "provenance.json", state)
    return state


def retire(
    root: Path, work: Path, destination: Path, *, category: str = "mri-work"
) -> dict[str, Any]:
    """Remove only verified duplicate work members, retaining recoverable tar and manifest.

    No broad recursive deletion is used. Validate archive SHA, member payloads and
    live source identities before any unlink; interrupted retirements resume from
    the recorded immutable inventory. Raw data, derivative paths and attempt logs
    cannot be targets. The caller must keep the source job quiescent throughout.
    """
    _target(root, work, category)
    if destination.resolve() != destination or not destination.is_relative_to(
        root / "archives" / category
    ):
        raise ValueError("invalid archive destination")
    state = load_structured(destination / "status.json")
    if state.get("category", "mri-work") != category:
        raise ValueError("archive category mismatch")
    if state.get("status") not in {"VERIFIED", "RETIRING", "RETIRED"} or state.get("source") != str(
        work
    ):
        raise ValueError("verified matching archive required")
    if hash_file(destination / "manifest.json") != state["manifest_sha256"]:
        raise ValueError("manifest changed")
    rows = load_structured(destination / "manifest.json")["members"]
    if verify_archive(destination / "work.tar", rows) != state["archive_sha256"]:
        raise ValueError("archive changed")
    if state["status"] == "RETIRED":
        if work.exists():
            raise ValueError("retired source unexpectedly reappeared")
        return state
    if work.exists():
        current = inventory(root, work, category=category)
        if not current.keys() <= rows.keys():
            raise ValueError("new source member appeared")
        for name, row in current.items():
            # Directory times change as already-verified children are retired.
            expected = {k: v for k, v in rows[name].items() if k != "sha256"}
            keys = (
                ["kind", "mode", "inode", "device"]
                if row["kind"] == "directory"
                else expected.keys()
            )
            if any(row[k] != expected[k] for k in keys):
                raise ValueError("source identity changed before removal")
    state.update(status="RETIRING", retirement_started_utc=utc_now())
    atomic_write_json(destination / "status.json", state)
    for name in sorted(rows, key=lambda s: (s.count("/"), s), reverse=True):
        path = work.parent / name
        if not path.exists() and not path.is_symlink():
            continue
        if rows[name]["kind"] == "directory":
            path.rmdir()
        else:
            if identity(path) != {k: v for k, v in rows[name].items() if k != "sha256"}:
                raise ValueError("source changed during retirement")
            path.unlink()
    state.update(status="RETIRED", source_removed=True, retirement_ended_utc=utc_now())
    atomic_write_json(destination / "status.json", state)
    atomic_write_json(destination / "provenance.json", state)
    return state
