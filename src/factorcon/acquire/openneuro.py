"""Version-pinned OpenNeuro GraphQL inventory resolver."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from factorcon.acquire.net import request_json
from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig
from factorcon.errors import IntegrityError, SourceError

GRAPHQL_URL = "https://openneuro.org/crn/graphql"


def select_object_url(
    urls: list[str], dataset_id: str, size: int | None
) -> tuple[str, str | None, str | None]:
    """Select pinned HTTPS retrieval; content keys bind exact bytes and SHA-256.

    Only API-supplied URLs for the pinned snapshot are considered. This does not
    alter scientific labels. Sizes are bytes; unknown or mismatched identities fail.
    """
    candidates = []
    for url in urls:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
            or parsed.fragment
        ):
            continue
        if parsed.hostname in {"s3.amazonaws.com", "openneuro.s3.amazonaws.com"}:
            versions = parse_qs(parsed.query).get("versionId", [])
            if len(versions) == 1 and versions[0] and versions[0] != "null":
                candidates.append((0, url, None, None))
        elif parsed.hostname == "openneuro.org":
            prefix = f"/crn/datasets/{dataset_id}/objects/"
            if not parsed.path.startswith(prefix):
                continue
            key = unquote(parsed.path[len(prefix) :])
            match = re.fullmatch(r"SHA256E-s(\d+)--([0-9a-f]{64})(?:\.[A-Za-z0-9._-]+)?", key)
            if match is None or size is None or int(match[1]) != size:
                continue
            candidates.append((1, url, "sha256", match[2]))
    if not candidates:
        raise IntegrityError("URL is not object-version pinned and has no verified SHA256E key")
    _, url, algorithm, digest = min(candidates, key=lambda value: value[0])
    return url, algorithm, digest


def resolve_openneuro(config: DatasetConfig) -> list[FileRecord]:
    """Resolve immutable, versioned object URLs for one OpenNeuro snapshot."""

    dataset_id = str(config.values["source_id"])
    snapshot = str(config.values["snapshot"])
    query = """
    query SnapshotFiles($datasetId: ID!, $tag: String!) {
      snapshot(datasetId: $datasetId, tag: $tag) {
        id
        tag
        hexsha
        created
        size
        files(recursive: true) {
          filename
          id
          size
          directory
          annexed
          urls
        }
      }
    }
    """
    document = request_json(
        GRAPHQL_URL,
        method="POST",
        payload={"query": query, "variables": {"datasetId": dataset_id, "tag": snapshot}},
        timeout=900,
        attempts=5,
    )
    if document.get("errors"):
        raise SourceError(f"OpenNeuro GraphQL errors: {document['errors']}")
    snapshot_record = (document.get("data") or {}).get("snapshot")
    if not isinstance(snapshot_record, dict):
        raise SourceError(f"OpenNeuro snapshot not found: {dataset_id} {snapshot}")
    if str(snapshot_record.get("tag")) != snapshot:
        raise IntegrityError(
            f"OpenNeuro tag mismatch: expected {snapshot}, got {snapshot_record.get('tag')}"
        )
    expected_sha = config.values.get("git_sha")
    if expected_sha is not None and str(snapshot_record.get("hexsha")) != str(expected_sha):
        raise IntegrityError(
            f"OpenNeuro Git SHA mismatch for {dataset_id} {snapshot}: "
            f"configured {expected_sha}, API {snapshot_record.get('hexsha')}"
        )
    expected_snapshot_bytes = config.values.get("snapshot_reported_bytes")
    if expected_snapshot_bytes is not None and int(snapshot_record.get("size") or -1) != int(
        expected_snapshot_bytes
    ):
        raise IntegrityError(
            f"OpenNeuro snapshot-size mismatch for {dataset_id} {snapshot}: "
            f"configured {expected_snapshot_bytes}, API {snapshot_record.get('size')}"
        )
    files = snapshot_record.get("files")
    if not isinstance(files, list):
        raise SourceError("OpenNeuro snapshot has no recursive file inventory")

    paths: set[str] = set()
    records: list[FileRecord] = []
    for item in files:
        if not isinstance(item, dict) or item.get("directory"):
            continue
        relative = str(item.get("filename") or "")
        if not relative:
            raise SourceError("OpenNeuro returned a file without filename")
        if relative in paths:
            raise IntegrityError(f"Duplicate OpenNeuro path: {relative}")
        paths.add(relative)
        urls = item.get("urls") or []
        if not urls:
            raise SourceError(f"OpenNeuro file has no retrieval URL: {relative}")
        size_value = item.get("size")
        size = int(size_value) if size_value is not None else None
        url, algorithm, digest = select_object_url([str(u) for u in urls], dataset_id, size)
        records.append(
            FileRecord(
                family=config.family,
                snapshot=snapshot,
                relative_path=relative,
                url=url,
                size=int(size_value) if size_value is not None else None,
                checksum_algorithm=algorithm,
                checksum=digest,
                source_id=str(item.get("id") or ""),
                annexed=bool(item.get("annexed")),
                metadata={
                    "snapshot_id": snapshot_record.get("id"),
                    "snapshot_created": snapshot_record.get("created"),
                },
            )
        )
    records.sort(key=lambda item: item.relative_path)
    expected_files = config.values.get("expected_manifest_files")
    if expected_files is not None and len(records) != int(expected_files):
        raise IntegrityError(
            f"OpenNeuro file-count mismatch for {dataset_id} {snapshot}: "
            f"configured {expected_files}, API {len(records)}"
        )
    expected = config.values.get("expected_manifest_bytes")
    known_total = sum(item.size or 0 for item in records)
    if expected is not None and known_total != int(expected):
        raise IntegrityError(
            f"OpenNeuro manifest-size mismatch for {dataset_id} {snapshot}: "
            f"configured {expected}, API {known_total}"
        )
    return records
