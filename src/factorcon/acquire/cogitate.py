"""Validate an owner-authorized private catalog; never store account credentials."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from factorcon.acquire.records import FileRecord
from factorcon.errors import AccessRequired, IntegrityError


def catalog_records(catalog: dict[str, Any]) -> list[FileRecord]:
    """Bind official Experiment 1 bundles to modality, bytes and strong HTTP ETag.

    The catalog is private operational metadata obtained after owner login. ETag is
    a server identity validator, NOT a publisher cryptographic checksum. Downloaded
    bytes receive local SHA-256. No labels or participant outcomes enter selection.
    """
    if catalog.get("owner_access_ready") is not True:
        raise AccessRequired("owner must complete account/access requirements")
    records = []
    seen = set()
    for item in catalog["bundles"]:
        url = urlparse(item["url"])
        key = (item["format"], item["modality"])
        pattern = rf"/20231231_cog_exp1_{item['format']}_{item['modality']}_[0-9a-f-]{{36}}\.zip"
        if (
            key in seen
            or key[0] not in {"raw", "bids"}
            or key[1] not in {"meeg", "ecog", "fmri"}
            or url.scheme != "https"
            or url.netloc != "cogitate-bundles.ae.mpg.de"
            or url.query
            or url.fragment
            or re.fullmatch(pattern, url.path) is None
        ):
            raise IntegrityError("duplicate, mislabeled or nonofficial COGITATE bundle")
        if int(item["bytes"]) <= 0 or re.fullmatch(r'"[^"\r\n]+"', item["etag"]) is None:
            raise IntegrityError("COGITATE requires byte count and strong ETag")
        seen.add(key)
        records.append(
            FileRecord(
                family="cogitate",
                snapshot="exp1_20231231",
                relative_path=url.path.lstrip("/"),
                url=item["url"],
                size=int(item["bytes"]),
                metadata={
                    "format": key[0],
                    "modality": key[1],
                    "http_etag": item["etag"],
                    "publisher_checksum_available": False,
                    "catalog_observed_utc": catalog["observed_utc"],
                },
            )
        )
    if not records:
        raise IntegrityError("empty COGITATE catalog")
    return records
