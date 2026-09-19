"""Tiny synthetic acquisition fixtures; no recordings or network access."""

import io
import json
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from factorcon.acquire.manager import _fingerprint
from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig
from factorcon.errors import IntegrityError
from factorcon.pipeline.empirical import (
    completion_records,
    inventory_sources,
    resolve_acquired_input,
    safe_tar_members,
    safe_zip_members,
    summarize_metadata,
    verify_downloads,
)
from factorcon.util import atomic_write_json, hash_file, read_jsonl, write_jsonl


def fixture(tmp_path, family="masked_content_fmri", *, repaired=False, archive=False):
    snapshot = "exp1_20231231" if family == "cogitate" else "1.0.0"
    data = tmp_path / "data/raw" / family / snapshot
    data.mkdir(parents=True)
    name = "fixture.zip" if archive else "sub-fixture_events.tsv"
    path = data / name
    if archive:
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("sub-fixture/func/sub-fixture_events.tsv", "onset\tduration\n0\t1\n")
    else:
        path.write_text("onset\tduration\n0\t1\n")
    record = FileRecord(family, snapshot, name, "https://example.org/fixture", path.stat().st_size)
    if repaired:
        manifest = tmp_path / "operations/acquisition-repair-v1" / family / "manifest.jsonl"
        ledger = manifest.parent / "downloads.json"
    else:
        manifest = tmp_path / "manifests/generated" / family / f"{snapshot}.jsonl"
        ledger = tmp_path / "run_state/P02" / f"{family}.{snapshot}.downloads.json"
    write_jsonl(manifest, [record.as_dict()])
    identity = hash_file(manifest) if repaired else _fingerprint([record])
    if repaired:
        atomic_write_json(
            manifest.parent / "resolution.json", {"manifest_sha256": identity, "holds": []}
        )
    atomic_write_json(
        ledger,
        {
            "success": True,
            "failed": 0,
            "complete": 1,
            "total": 1,
            "source_manifest_sha256": identity,
        },
    )
    write_jsonl(
        ledger.with_suffix(".events.jsonl"),
        [
            {
                "event": "file_complete",
                "relative_path": name,
                "source_manifest_sha256": identity,
                "bytes": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "sha256": hash_file(path),
            }
        ],
    )
    dataset = DatasetConfig(
        Path("fixture"), {"family": family, "snapshot": snapshot, "expected_manifest_files": 1}
    )
    return dataset, path, ledger


@pytest.mark.parametrize(
    "family,repaired",
    [
        ("masked_content_fmri", False),
        ("cogitate", True),
        ("dream", True),
        ("propofol_volition_fmri", True),
    ],
)
def test_original_and_repaired_identity(tmp_path, family, repaired):
    dataset, _, _ = fixture(tmp_path, family, repaired=repaired)
    inputs = resolve_acquired_input(tmp_path, dataset)
    result = verify_downloads(inputs, tmp_path / "verified.jsonl")
    assert result["files"] == 1
    assert len(completion_records(inputs)) == 1
    assert next(read_jsonl(tmp_path / "verified.jsonl"))["sha256"]


def test_manifest_count_and_ledger_identity(tmp_path):
    dataset, _, ledger = fixture(tmp_path)
    bad = DatasetConfig(dataset.path, {**dataset.values, "expected_manifest_files": 2})
    with pytest.raises(IntegrityError, match="count"):
        resolve_acquired_input(tmp_path, bad)
    value = json.loads(ledger.read_text())
    value["source_manifest_sha256"] = "wrong"
    atomic_write_json(ledger, value)
    with pytest.raises(IntegrityError, match="same-manifest"):
        resolve_acquired_input(tmp_path, dataset)


def test_same_size_corruption_rejected_even_when_timestamp_preserved(tmp_path):
    import os

    dataset, path, _ = fixture(tmp_path)
    inputs = resolve_acquired_input(tmp_path, dataset)
    old = path.stat()
    path.write_bytes(path.read_bytes().replace(b"0", b"9"))
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    with pytest.raises(IntegrityError, match="SHA-256"):
        verify_downloads(inputs, tmp_path / "verified.jsonl")


def test_changed_file_during_hash_rejected(tmp_path, monkeypatch):
    from factorcon.pipeline import empirical

    dataset, path, _ = fixture(tmp_path)
    inputs = resolve_acquired_input(tmp_path, dataset)
    original = empirical.hash_file

    def changing(p):
        value = original(p)
        path.write_text("changed during hash")
        return value

    monkeypatch.setattr(empirical, "hash_file", changing)
    with pytest.raises(IntegrityError, match="changed"):
        verify_downloads(inputs, tmp_path / "verified.jsonl")


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/outside", "x/../../outside"])
def test_archive_traversal_rejected(name):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, "x")
    with zipfile.ZipFile(buf) as z, pytest.raises(IntegrityError):
        safe_zip_members(z)


def test_archive_symlink_and_duplicate_rejected():
    for kind in ["link", "duplicate"]:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            if kind == "link":
                info = zipfile.ZipInfo("link")
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(info, "../outside")
            else:
                z.writestr("a/b", "1")
                z.writestr("a\\b", "2")
        with zipfile.ZipFile(buf) as z, pytest.raises(IntegrityError):
            safe_zip_members(z)


def test_inventory_reads_schema_not_rows_and_preserves_archive(tmp_path):
    dataset, path, _ = fixture(tmp_path, archive=True)
    before = hash_file(path)
    inputs = resolve_acquired_input(tmp_path, dataset)
    report = inventory_sources(inputs, tmp_path / "inventory.jsonl", max_metadata_bytes=10000)
    rows = list(read_jsonl(tmp_path / "inventory.jsonl"))
    assert rows[1]["schema"] == {"kind": "table", "fields": ["onset", "duration"], "rows": 1}
    assert report["inventory_rows"] == 2 and report["full_archive_crc_checked"] is False
    assert hash_file(path) == before
    assert not (tmp_path / "sub-fixture").exists()


def test_schema_width_duplicate_headers_and_metadata_limit(tmp_path):
    with pytest.raises(IntegrityError):
        summarize_metadata("a.tsv", b"x\tx\n1\t2\n")
    with pytest.raises(IntegrityError):
        summarize_metadata("a.tsv", b"x\ty\n1\n")
    dataset, _, _ = fixture(tmp_path)
    inventory_sources(
        resolve_acquired_input(tmp_path, dataset), tmp_path / "i.jsonl", max_metadata_bytes=1
    )
    assert next(read_jsonl(tmp_path / "i.jsonl"))["schema_status"] == "over_metadata_byte_limit"


def test_resolved_file_escape_rejected(tmp_path, monkeypatch):
    dataset, path, _ = fixture(tmp_path)
    inputs = resolve_acquired_input(tmp_path, dataset)
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda p, *a, **kw: tmp_path.parent / "outside" if p == path else original(p, *a, **kw),
    )
    with pytest.raises(IntegrityError, match="escapes"):
        verify_downloads(inputs, tmp_path / "checked.jsonl")


@pytest.mark.parametrize("kind", ["normal", "traversal", "link"])
def test_tar_member_safety(kind):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo("../outside" if kind == "traversal" else "./data.tsv")
        if kind == "link":
            info.type = tarfile.SYMTYPE
            info.linkname = "../outside"
        tar.addfile(info)
    buf.seek(0)
    with tarfile.open(fileobj=buf) as tar:
        if kind == "normal":
            assert len(safe_tar_members(tar)) == 1
        else:
            with pytest.raises(IntegrityError):
                safe_tar_members(tar)
