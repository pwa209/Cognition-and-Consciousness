from __future__ import annotations

from argparse import Namespace
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

import factorcon.acquire.bmvp as bmvp_module
import factorcon.acquire.http as http_module
import factorcon.acquire.manager as manager_module
import factorcon.acquire.openneuro as openneuro_module
import factorcon.cli as cli_module
from factorcon.acquire.bmvp import resolve_bmvp
from factorcon.acquire.http import DownloadResult, download_many, download_one
from factorcon.acquire.manager import resolve_manifests
from factorcon.acquire.openneuro import resolve_openneuro
from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig
from factorcon.errors import CapacityError, IntegrityError, SourceError


class _Response(BytesIO):
    def __init__(self, data: bytes, status: int, headers: dict[str, str] | None = None) -> None:
        super().__init__(data)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def test_bmvp_resolver_separates_report_context_from_modality(monkeypatch) -> None:
    html = b"""
    <a href="https://bmvp.projects.nitrc.org/223_RP_EEG.tar">EEG</a>
    <input value="https://bmvp.projects.nitrc.org/223_RP_MRI.tar">
    <a href="https://bmvp.projects.nitrc.org/238_NRP.tar">no report</a>
    """
    monkeypatch.setattr(bmvp_module, "request_bytes", lambda *_args, **_kwargs: (html, {}, 200))
    config = DatasetConfig(
        Path("bmvp.yaml"),
        {
            "family": "bmvp",
            "source_type": "bmvp_nitrc",
            "source_id": "fixture",
            "access": "public",
            "snapshot_label": "fixture-v1",
            "index_url": "https://bmvp.projects.nitrc.org/download_all.html",
            "expected_archive_urls": 3,
        },
    )

    records = resolve_bmvp(config)
    by_name = {Path(record.relative_path).name: record for record in records}

    assert by_name["223_RP_EEG.tar"].metadata == {
        "report_context": "report",
        "archive_modality": "eeg",
        "retain_archive": True,
    }
    assert by_name["223_RP_MRI.tar"].metadata["archive_modality"] == "mri"
    assert by_name["238_NRP.tar"].metadata["report_context"] == "no_report"


def test_openneuro_resolver_requires_versioned_official_object_url(monkeypatch) -> None:
    document = {
        "data": {
            "snapshot": {
                "id": "snapshot-id",
                "tag": "1.0.0",
                "hexsha": "fixture-sha",
                "created": "2026-01-01T00:00:00Z",
                "size": 6,
                "files": [
                    {
                        "filename": "sub-01/events.tsv",
                        "id": "object-id",
                        "size": 6,
                        "directory": False,
                        "annexed": True,
                        "urls": [
                            "https://openneuro.s3.amazonaws.com/key?versionId=immutable-version"
                        ],
                    }
                ],
            }
        }
    }
    monkeypatch.setattr(openneuro_module, "request_json", lambda *_args, **_kwargs: document)
    config = DatasetConfig(
        Path("openneuro.yaml"),
        {
            "family": "fixture",
            "source_type": "openneuro",
            "source_id": "ds000001",
            "access": "public",
            "snapshot": "1.0.0",
            "git_sha": "fixture-sha",
            "snapshot_reported_bytes": 6,
            "expected_manifest_files": 1,
            "expected_manifest_bytes": 6,
        },
    )

    records = resolve_openneuro(config)

    assert records[0].relative_path == "sub-01/events.tsv"
    document["data"]["snapshot"]["files"][0]["urls"] = ["https://openneuro.s3.amazonaws.com/key"]
    with pytest.raises(IntegrityError, match="not object-version pinned"):
        resolve_openneuro(config)


def test_subset_manifest_resolution_merges_the_global_index(monkeypatch, tmp_path: Path) -> None:
    datasets = tuple(
        DatasetConfig(
            Path(f"{family}.yaml"),
            {
                "family": family,
                "source_type": "fixture_source",
                "source_id": family,
                "access": "public",
                "snapshot_label": "v1",
            },
        )
        for family in ("family_a", "family_b")
    )
    project = SimpleNamespace(
        datasets=datasets,
        analysis_spec={"registration": None, "scientific_gates": False},
    )

    def resolve_fixture(config: DatasetConfig) -> list[FileRecord]:
        return [
            FileRecord(
                family=config.family,
                snapshot="v1",
                relative_path=f"{config.family}.dat",
                url=f"https://example.test/{config.family}.dat",
                size=1,
            )
        ]

    monkeypatch.setitem(manager_module.RESOLVERS, "fixture_source", resolve_fixture)
    resolve_manifests(project, tmp_path, families={"family_a"})
    index = resolve_manifests(project, tmp_path, families={"family_b"})

    assert set(index["families"]) == {"family_a", "family_b"}


def test_acquire_command_fails_phase_when_any_public_source_fails(
    monkeypatch, tmp_path: Path
) -> None:
    project = SimpleNamespace(server={"expected_hostname": "irrelevant"})
    monkeypatch.setattr(cli_module, "load_project", lambda _path: project)
    monkeypatch.setattr(
        cli_module,
        "acquire_families",
        lambda *_args, **_kwargs: {"families": {}, "all_public_success": False},
    )
    args = Namespace(
        command="acquire",
        config="conf/base.yaml",
        canonical_root=str(tmp_path),
        family=None,
        workers=None,
        no_resolve=False,
        eligible_only=True,
    )

    assert cli_module.dispatch(args) == 3


def test_download_many_writes_compact_summary_and_per_file_events(
    monkeypatch, tmp_path: Path
) -> None:
    records = [
        FileRecord(
            family="fixture",
            snapshot="v1",
            relative_path=f"files/{index}.dat",
            url=f"https://example.test/{index}.dat",
            size=index + 1,
        )
        for index in range(20)
    ]

    calls: list[str] = []

    def fake_download(record: FileRecord, destination: Path, **_kwargs) -> DownloadResult:
        calls.append(record.relative_path)
        final = destination / record.relative_path
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(b"x" * (record.size or 0))
        return DownloadResult(
            relative_path=record.relative_path,
            status="downloaded",
            bytes=record.size or 0,
            sha256=f"{record.size:064x}",
            mtime_ns=final.stat().st_mtime_ns,
            completed_utc="2026-08-30T00:00:00Z",
            attempts=1,
        )

    monkeypatch.setattr(http_module, "download_one", fake_download)
    ledger = tmp_path / "downloads.json"
    manifest_sha = "a" * 64
    summary = download_many(
        records,
        tmp_path / "raw",
        ledger,
        workers=3,
        source_manifest_sha256=manifest_sha,
    )

    assert summary["success"] is True
    assert summary["complete"] == 20
    assert "results" not in ledger.read_text(encoding="utf-8")
    events = (tmp_path / "downloads.events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(events) == 22
    assert sum('"event":"file_complete"' in line for line in events) == 20
    resumed = download_many(
        records,
        tmp_path / "raw",
        ledger,
        workers=3,
        source_manifest_sha256=manifest_sha,
    )
    assert resumed["cache_verified"] == 20
    assert len(calls) == 20


def test_download_one_resumes_and_verifies_checksum(monkeypatch, tmp_path: Path) -> None:
    content = b"abcdef"
    record = FileRecord(
        family="fixture",
        snapshot="v1",
        relative_path="nested/file.dat",
        url="https://example.test/file.dat",
        size=len(content),
        checksum_algorithm="sha256",
        checksum=sha256(content).hexdigest(),
    )
    partial = tmp_path / "nested" / "file.dat.part"
    partial.parent.mkdir()
    partial.write_bytes(content[:3])

    def fake_urlopen(request, **_kwargs):
        assert request.headers["Range"] == "bytes=3-"
        return _Response(
            content[3:],
            206,
            {"Content-Length": "3", "Content-Range": "bytes 3-5/6"},
        )

    monkeypatch.setattr(http_module.urllib.request, "urlopen", fake_urlopen)
    result = download_one(record, tmp_path)

    assert result.status == "downloaded"
    assert result.sha256 == record.checksum
    assert (tmp_path / "nested" / "file.dat").read_bytes() == content


def test_download_one_restarts_when_server_ignores_range(monkeypatch, tmp_path: Path) -> None:
    content = b"abcdef"
    record = FileRecord(
        family="fixture",
        snapshot="v1",
        relative_path="file.dat",
        url="https://example.test/file.dat",
        size=len(content),
    )
    (tmp_path / "file.dat.part").write_bytes(content[:3])
    responses = iter((_Response(content, 200), _Response(content, 200)))
    monkeypatch.setattr(
        http_module.urllib.request, "urlopen", lambda *_args, **_kwargs: next(responses)
    )
    monkeypatch.setattr(http_module.time, "sleep", lambda _seconds: None)

    result = download_one(record, tmp_path, attempts=2)

    assert result.attempts == 2
    assert (tmp_path / "file.dat").read_bytes() == content


def test_download_one_recovers_complete_unknown_size_partial_from_416(
    monkeypatch, tmp_path: Path
) -> None:
    content = b"abcdef"
    record = FileRecord(
        family="fixture",
        snapshot="v1",
        relative_path="file.dat",
        url="https://example.test/file.dat",
    )
    (tmp_path / "file.dat.part").write_bytes(content)

    def range_not_satisfiable(*_args, **_kwargs):
        raise http_module.urllib.error.HTTPError(
            record.url,
            416,
            "Range Not Satisfiable",
            {"Content-Range": "bytes */6"},
            None,
        )

    monkeypatch.setattr(http_module.urllib.request, "urlopen", range_not_satisfiable)

    result = download_one(record, tmp_path, attempts=1)

    assert result.status == "resumed_verified"
    assert (tmp_path / "file.dat").read_bytes() == content


def test_download_one_never_promotes_checksum_mismatch(monkeypatch, tmp_path: Path) -> None:
    record = FileRecord(
        family="fixture",
        snapshot="v1",
        relative_path="file.dat",
        url="https://example.test/file.dat",
        size=3,
        checksum_algorithm="sha256",
        checksum=sha256(b"expected").hexdigest(),
    )
    monkeypatch.setattr(
        http_module.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(b"bad", 200),
    )
    monkeypatch.setattr(http_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(SourceError, match="Failed to download"):
        download_one(record, tmp_path, attempts=2)

    assert not (tmp_path / "file.dat").exists()
    assert not (tmp_path / "file.dat.part").exists()


def test_download_one_never_promotes_truncated_unknown_size_body(
    monkeypatch, tmp_path: Path
) -> None:
    record = FileRecord(
        family="fixture",
        snapshot="v1",
        relative_path="file.dat",
        url="https://example.test/file.dat",
    )
    monkeypatch.setattr(
        http_module.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(b"abc", 200, {"Content-Length": "6"}),
    )

    with pytest.raises(SourceError, match="Failed to download"):
        download_one(record, tmp_path, attempts=1)

    assert not (tmp_path / "file.dat").exists()


def test_download_one_preserves_partial_when_storage_reserve_is_reached(
    monkeypatch, tmp_path: Path
) -> None:
    record = FileRecord(
        family="fixture",
        snapshot="v1",
        relative_path="file.dat",
        url="https://example.test/file.dat",
    )
    monkeypatch.setattr(
        http_module.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(b"abcdef", 200),
    )
    monkeypatch.setattr(
        http_module.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100, used=94, free=6),
    )

    with pytest.raises(CapacityError, match="reserve reached"):
        download_one(
            record,
            tmp_path,
            chunk_size=3,
            reserve_bytes=5,
            space_check_interval=1,
        )

    assert (tmp_path / "file.dat.part").exists()


def test_download_one_can_verify_existing_file_at_storage_reserve(
    monkeypatch, tmp_path: Path
) -> None:
    content = b"already complete"
    record = FileRecord(
        family="fixture",
        snapshot="v1",
        relative_path="file.dat",
        url="https://example.test/file.dat",
        size=len(content),
        checksum_algorithm="sha256",
        checksum=sha256(content).hexdigest(),
    )
    (tmp_path / "file.dat").write_bytes(content)
    monkeypatch.setattr(
        http_module.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100, used=100, free=0),
    )

    result = download_one(record, tmp_path, reserve_bytes=5)

    assert result.status == "already_verified"
