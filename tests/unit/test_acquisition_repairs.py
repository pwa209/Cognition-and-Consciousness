"""Tiny publisher-identity fixtures; no participant data or network requests."""

from copy import deepcopy
from pathlib import Path
from typing import ClassVar

import pytest

import factorcon.acquire.dream_constituents as dream
from factorcon.acquire.cogitate import catalog_records
from factorcon.acquire.openneuro import select_object_url
from factorcon.errors import AccessRequired, IntegrityError


def test_content_addressed_url_binds_sha_and_size():
    url = "https://openneuro.org/crn/datasets/ds006623/objects/SHA256E-s3--" + "a" * 64 + ".nii.gz"
    assert select_object_url([url], "ds006623", 3) == (url, "sha256", "a" * 64)
    for dataset, size in [("ds000001", 3), ("ds006623", 4), ("ds006623", None)]:
        with pytest.raises(IntegrityError):
            select_object_url([url], dataset, size)
    for bad in [
        url.replace("https:", "http:"),
        url.replace("openneuro.org", "evil.test"),
        url.replace("SHA256E", "../SHA256E"),
    ]:
        with pytest.raises(IntegrityError):
            select_object_url([bad], "ds006623", 3)


def test_considers_all_urls_and_rejects_fake_version_parameters():
    valid = "https://openneuro.s3.amazonaws.com/file?versionId=immutable"
    assert select_object_url(["https://evil.test/file", valid], "ds006623", 3)[0] == valid
    for query in ["xversionId=foo", "versionId=", "versionId=null", "versionId=a&versionId=b"]:
        with pytest.raises(IntegrityError):
            select_object_url(["https://openneuro.s3.amazonaws.com/file?" + query], "ds006623", 3)


def test_registry_amendments_counts_and_duplicate(tmp_path):
    fixture = Path(__file__).parents[1] / "fixtures/dream_registry_amendments.csv"
    current, old = dream.current_registry(fixture, expected_rows=3, expected_sets=2)
    assert [r["Key ID"] for r in current] == ["2", "3"]
    assert [r["Key ID"] for r in old] == ["1"]
    with pytest.raises(IntegrityError):
        dream.current_registry(fixture, expected_rows=4, expected_sets=2)
    bad = tmp_path / "bad.csv"
    bad.write_text(fixture.read_text().replace("2,4,1,", "2,4,0,"))
    with pytest.raises(IntegrityError, match="duplicate"):
        dream.current_registry(bad, expected_rows=3, expected_sets=2)


def test_figshare_version_file_identity_and_access(monkeypatch):
    row = {
        "Set ID": "1",
        "Key ID": "1",
        "Accessibility": "Open",
        "Revoked": "FALSE",
        "Data URL": "https://doi.org/10.6084/m9.figshare.123.v2",
    }
    doc = {
        "id": 123,
        "version": 2,
        "is_embargoed": False,
        "license": {"name": "CC BY 4.0"},
        "files": [
            {
                "id": 456,
                "name": "fixture.zip",
                "size": 3,
                "computed_md5": "a" * 32,
                "download_url": "https://ndownloader.figshare.com/files/456",
            }
        ],
    }
    calls = []

    def fetch(url, **kwargs):
        calls.append(url)
        return doc

    monkeypatch.setattr(dream, "request_json", fetch)
    records, info = dream.resolve_figshare_row(row, "v6")
    assert calls == ["https://api.figshare.com/v2/articles/123/versions/2"]
    assert info["files"] == 1 and info["bytes"] == 3
    assert records[0].checksum == "a" * 32
    for name in ["../bad.zip", "/bad.zip", "..\\bad.zip"]:
        doc["files"][0]["name"] = name
        with pytest.raises(IntegrityError):
            dream.resolve_figshare_row(row, "v6")
    doc["files"][0]["name"] = "fixture.zip"
    doc["version"] = 3
    with pytest.raises(IntegrityError, match="version"):
        dream.resolve_figshare_row(row, "v6")
    calls.clear()
    for field, value in [("Accessibility", "Private"), ("Revoked", "TRUE")]:
        with pytest.raises(AccessRequired):
            dream.resolve_figshare_row({**row, field: value}, "v6")
    assert calls == []


def test_cogitate_rejects_mislabeled_duplicate_and_unapproved_catalog():
    bundle = {
        "format": "bids",
        "modality": "meeg",
        "bytes": 3,
        "etag": '"abc"',
        "url": "https://cogitate-bundles.ae.mpg.de/20231231_cog_exp1_bids_meeg_"
        "00000000-0000-0000-0000-000000000000.zip",
    }
    catalog = {"owner_access_ready": True, "observed_utc": "fixture", "bundles": [bundle]}
    assert catalog_records(catalog)[0].metadata["http_etag"] == '"abc"'
    for field, value in [
        ("modality", "ecog"),
        ("format", "raw"),
        ("etag", 'W/"abc"'),
        ("bytes", 0),
    ]:
        bad = deepcopy(catalog)
        bad["bundles"][0][field] = value
        with pytest.raises(IntegrityError):
            catalog_records(bad)
    with pytest.raises(AccessRequired):
        catalog_records({**catalog, "owner_access_ready": False})
    with pytest.raises(IntegrityError):
        catalog_records({**catalog, "bundles": [bundle, bundle]})


def test_freidata_counts_checksum_and_traversal(monkeypatch):
    rid = "31mg4-mfq53"
    row = {
        "Set ID": "19",
        "Key ID": "21",
        "Accessibility": "Open",
        "Revoked": "FALSE",
        "Data URL": f"https://doi.org/10.60493/{rid}",
    }
    item = {
        "key": "fixture.zip",
        "id": "fixture",
        "size": 46588397863,
        "access": {"hidden": False},
        "checksum": "md5:dc6d0768de5f521218d13c9768504e24",
        "links": {
            "content": f"https://freidata.uni-freiburg.de/api/records/{rid}/files/fixture.zip/content"
        },
    }
    doc = {
        "id": rid,
        "pids": {"doi": {"identifier": f"10.60493/{rid}"}},
        "versions": {"index": 1},
        "access": {"files": "public", "record": "public", "embargo": {"active": False}},
        "metadata": {"rights": []},
        "files": {"count": 1, "total_bytes": 46588397863, "entries": {"fixture.zip": item}},
    }
    monkeypatch.setattr(dream, "request_json", lambda *a, **k: doc)
    records, info = dream.resolve_freidata_row(row, "v6")
    assert len(records) == 1 and info["bytes"] == 46588397863
    doc["files"]["count"] = 2
    with pytest.raises(IntegrityError):
        dream.resolve_freidata_row(row, "v6")
    doc["files"]["count"] = 1
    doc["files"]["entries"] = {"../bad.zip": item}
    with pytest.raises(IntegrityError):
        dream.resolve_freidata_row(row, "v6")


def test_etag_pinned_download_and_reject_changed_object(monkeypatch, tmp_path):
    from io import BytesIO

    from factorcon.acquire import http
    from factorcon.acquire.records import FileRecord
    from factorcon.errors import SourceError

    class Response(BytesIO):
        status = 200
        headers: ClassVar[dict[str, str]] = {"ETag": '"version1"', "Content-Length": "3"}

    requests = []

    def fetch(request, **kwargs):
        requests.append(request)
        return Response(b"abc")

    monkeypatch.setattr(http.urllib.request, "urlopen", fetch)
    record = FileRecord(
        "fixture", "v1", "x.bin", "https://example.test/x", 3, metadata={"http_etag": '"version1"'}
    )
    result = http.download_one(record, tmp_path / "good", attempts=1)
    assert result.bytes == 3 and requests[0].get_header("If-match") == '"version1"'
    Response.headers = {"ETag": '"changed"', "Content-Length": "3"}
    with pytest.raises(SourceError, match="ETag"):
        http.download_one(record, tmp_path / "bad", attempts=1)
    assert not (tmp_path / "bad/x.bin").exists()
