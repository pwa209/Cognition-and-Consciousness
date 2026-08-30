"""Resolver for the official BMVP per-subject archive index."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from factorcon.acquire.net import request_bytes
from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig
from factorcon.errors import IntegrityError


class _ArchiveParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() not in {"input", "a"}:
            return
        values = {key.lower(): value for key, value in attrs}
        candidate = values.get("value") if tag.lower() == "input" else values.get("href")
        if candidate and candidate.startswith("https://bmvp.projects.nitrc.org/") and candidate.endswith(".tar"):
            self.urls.append(candidate)


def resolve_bmvp(config: DatasetConfig) -> list[FileRecord]:
    """Parse and validate all official BMVP archive URLs."""

    body, _, _ = request_bytes(str(config.values["index_url"]), timeout=180)
    parser = _ArchiveParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    urls = sorted(set(parser.urls))
    expected = int(config.values.get("expected_archive_urls", 0))
    if expected and len(urls) != expected:
        raise IntegrityError(f"Expected {expected} BMVP archive URLs, found {len(urls)}")
    records: list[FileRecord] = []
    names: set[str] = set()
    for url in urls:
        parsed = urlparse(url)
        name = unquote(PurePosixPath(parsed.path).name)
        if name in names:
            raise IntegrityError(f"Duplicate BMVP archive basename: {name}")
        names.add(name)
        group = "unclassified"
        lowered = name.lower()
        if "nrp" in lowered:
            group = "no_report"
        elif "rp" in lowered:
            group = "report"
        elif "eeg" in lowered:
            group = "eeg"
        records.append(
            FileRecord(
                family=config.family,
                snapshot=config.snapshot_label,
                relative_path=f"archives/{group}/{name}",
                url=url,
                metadata={"archive_group": group, "retain_archive": True},
            )
        )
    return records

