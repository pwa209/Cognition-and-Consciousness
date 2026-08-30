"""DREAM registry and constituent-access resolver."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import urlparse

from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig
from factorcon.util import slug


def resolve_dream_registry(config: DatasetConfig) -> list[FileRecord]:
    """Return the fixed DREAM registry table object.

    The Monash object store currently presents an invalid/expired certificate on its
    final redirect from this host. TLS verification is never disabled automatically;
    the resulting operational failure remains explicit until the source repairs it or
    a checksum-authenticated mirror is configured.
    """

    file_id = int(config.values["registry_file_id"])
    return [
        FileRecord(
            family=config.family,
            snapshot=config.snapshot_label,
            relative_path="registry/Datasets.csv",
            url=f"https://ndownloader.figshare.com/files/{file_id}",
            source_id=str(file_id),
            metadata={"registry_version": config.values.get("registry_version")},
        )
    ]


_URL_RE = re.compile(r"https?://[^\s,;]+")
_DIRECT_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".7z", ".edf", ".bdf")


def parse_dream_registry(path: str | Path, config: DatasetConfig) -> tuple[list[FileRecord], list[dict[str, str]]]:
    """Resolve directly downloadable open constituent URLs and retain unresolved rows."""

    direct: list[FileRecord] = []
    unresolved: list[dict[str, str]] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = {str(key).strip().casefold(): str(value or "").strip() for key, value in row.items()}
            access = normalized.get("accessibility", "").casefold()
            revoked = normalized.get("revoked", "").casefold()
            name = normalized.get("common name") or f"set-{normalized.get('set id', 'unknown')}"
            urls = _URL_RE.findall(normalized.get("data url", ""))
            if revoked in {"yes", "true", "1"} or "open" not in access or not urls:
                unresolved.append(
                    {"dataset": name, "accessibility": access, "status": "waiting_access_or_no_url"}
                )
                continue
            for index, url in enumerate(urls, start=1):
                clean_url = url.rstrip(".)]")
                pathname = urlparse(clean_url).path.casefold()
                if not pathname.endswith(_DIRECT_SUFFIXES):
                    unresolved.append(
                        {"dataset": name, "accessibility": access, "status": "manual_url_resolution", "url": clean_url}
                    )
                    continue
                basename = Path(urlparse(clean_url).path).name or f"download-{index}"
                direct.append(
                    FileRecord(
                        family=config.family,
                        snapshot=config.snapshot_label,
                        relative_path=f"constituents/{slug(name)}/{basename}",
                        url=clean_url,
                        metadata={"dream_dataset": name, "accessibility": access},
                    )
                )
    return direct, unresolved

