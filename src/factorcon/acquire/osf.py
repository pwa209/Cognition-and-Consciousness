"""OSF recursive file-inventory resolver."""

from __future__ import annotations

from collections import deque
from typing import Any

from factorcon.acquire.net import request_json
from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig
from factorcon.errors import IntegrityError, SourceError


def _next_url(document: dict[str, Any]) -> str | None:
    links = document.get("links") or {}
    value = links.get("next")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        href = value.get("href")
        return str(href) if href else None
    return None


def _folder_url(item: dict[str, Any]) -> str | None:
    relationships = item.get("relationships") or {}
    files = relationships.get("files") or {}
    links = files.get("links") or {}
    related = links.get("related")
    if isinstance(related, str):
        return related
    if isinstance(related, dict):
        href = related.get("href")
        return str(href) if href else None
    return None


def resolve_osf(config: DatasetConfig) -> list[FileRecord]:
    """Resolve every file under an OSF project's primary storage provider."""

    node = str(config.values["source_id"])
    queue: deque[str] = deque([f"https://api.osf.io/v2/nodes/{node}/files/osfstorage/"])
    visited: set[str] = set()
    records: list[FileRecord] = []
    paths: set[str] = set()
    while queue:
        page_url = queue.popleft()
        if page_url in visited:
            continue
        visited.add(page_url)
        while page_url:
            document = request_json(page_url, timeout=180)
            data = document.get("data")
            if not isinstance(data, list):
                raise SourceError(f"OSF listing lacks data array: {page_url}")
            for item in data:
                if not isinstance(item, dict):
                    continue
                attributes = item.get("attributes") or {}
                kind = attributes.get("kind")
                if kind == "folder":
                    nested = _folder_url(item)
                    if nested:
                        queue.append(nested)
                    continue
                if kind != "file":
                    continue
                links = item.get("links") or {}
                url = links.get("download")
                relative = str(
                    attributes.get("materialized_path")
                    or attributes.get("path")
                    or attributes.get("name")
                    or ""
                ).lstrip("/")
                if not url or not relative:
                    raise SourceError(f"OSF file lacks path/download link: {item.get('id')}")
                if relative in paths:
                    raise IntegrityError(f"Duplicate OSF path: {relative}")
                paths.add(relative)
                extra = attributes.get("extra") or {}
                hashes = extra.get("hashes") or {}
                algorithm: str | None = None
                checksum: str | None = None
                if hashes.get("sha256"):
                    algorithm, checksum = "sha256", str(hashes["sha256"])
                elif hashes.get("md5"):
                    algorithm, checksum = "md5", str(hashes["md5"])
                size_value = attributes.get("size")
                records.append(
                    FileRecord(
                        family=config.family,
                        snapshot=config.snapshot_label,
                        relative_path=relative,
                        url=str(url),
                        size=int(size_value) if size_value is not None else None,
                        checksum_algorithm=algorithm,
                        checksum=checksum,
                        source_id=str(item.get("id") or ""),
                        metadata={
                            "date_modified": attributes.get("date_modified"),
                            "provider": (item.get("relationships") or {}).get("provider"),
                        },
                    )
                )
            page_url = _next_url(document) or ""
    records.sort(key=lambda item: item.relative_path)
    return records

