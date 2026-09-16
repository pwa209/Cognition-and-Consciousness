"""Version-aware DREAM registry and public Figshare constituent resolution.

Access states and superseded rows are retained, never inferred from scientific results.
No downloaded code is executed. Network requests retrieve publisher metadata only.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from factorcon.acquire.net import request_json
from factorcon.acquire.records import FileRecord
from factorcon.errors import AccessRequired, IntegrityError
from factorcon.util import safe_relative_path


def current_registry(
    path: Path, *, expected_rows: int, expected_sets: int
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Select highest approved amendment per Set ID, preserving all historical rows.

    Counts are registry rows and contributing datasets, not participants or outcomes.
    Malformed/ambiguous identities stop resolution; no access default is assumed.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "Key ID",
            "Set ID",
            "Amendment",
            "Date approved",
            "Common name",
            "Accessibility",
            "Revoked",
            "Data URL",
        }
        if not required <= set(reader.fieldnames or []):
            raise IntegrityError("DREAM registry schema mismatch")
        rows = [{k: str(v or "").strip() for k, v in row.items()} for row in reader]
    if len(rows) != expected_rows or len({r["Set ID"] for r in rows}) != expected_sets:
        raise IntegrityError("DREAM registry expected row/set counts do not match")
    active = {}
    identities = set()
    keys = set()
    for row in rows:
        sid = row["Set ID"]
        amendment = int(row["Amendment"])
        if not sid.isdigit() or amendment < 0 or int(row["Date approved"]) <= 0:
            raise IntegrityError("DREAM unapproved or invalid registry identity")
        identity = (sid, amendment)
        if identity in identities or row["Key ID"] in keys:
            raise IntegrityError("DREAM duplicate amendment/key identity")
        identities.add(identity)
        keys.add(row["Key ID"])
        if row["Revoked"].casefold() not in {"true", "false"}:
            raise IntegrityError("DREAM unknown revocation state")
        if sid not in active or amendment > int(active[sid]["Amendment"]):
            active[sid] = row
    current = sorted(active.values(), key=lambda r: int(r["Set ID"]))
    selected = {r["Key ID"] for r in current}
    return current, [r for r in rows if r["Key ID"] not in selected]


def figshare_identity(url: str) -> tuple[int, int | None]:
    """Parse recognized Figshare/Monash DOI identifiers without following arbitrary URLs."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "doi.org" or parsed.query or parsed.fragment:
        raise IntegrityError("unsupported DREAM repository link")
    match = re.fullmatch(r"/(?:10\.6084/m9\.figshare\.|10\.26180/)(\d+)(?:\.v(\d+))?", parsed.path)
    if match is None:
        raise IntegrityError("DREAM link requires a separate repository adapter")
    return int(match[1]), int(match[2]) if match[2] else None


def resolve_figshare_row(
    row: dict[str, str], snapshot: str
) -> tuple[list[FileRecord], dict[str, Any]]:
    """Pin a public constituent version and require publisher sizes and MD5 digests.

    URLs come from the exact version API. An unversioned registry DOI is resolved once
    and that explicit version is recorded. Byte contents are checked by the downloader.
    """
    if row["Accessibility"].casefold() != "open" or row["Revoked"].casefold() != "false":
        raise AccessRequired("constituent is private, revoked or not explicitly open")
    article, version = figshare_identity(row["Data URL"])
    base = f"https://api.figshare.com/v2/articles/{article}"
    if version is None:
        latest = request_json(base, timeout=60, attempts=2)
        version = int(latest["version"])
    api = f"{base}/versions/{version}"
    document = request_json(api, timeout=60, attempts=2)
    if int(document.get("id", -1)) != article or int(document.get("version", -1)) != version:
        raise IntegrityError("Figshare article/version identity mismatch")
    if document.get("is_embargoed") is not False:
        raise AccessRequired("Figshare embargo/access status is not explicitly public")
    files = document.get("files")
    if not isinstance(files, list) or not files:
        raise IntegrityError("Figshare version has no file inventory")
    records = []
    seen = set()
    for item in files:
        name = str(item["name"])
        safe_relative_path(name)
        fid = int(item["id"])
        size = int(item["size"])
        digest = str(item.get("computed_md5") or "")
        url = str(item["download_url"])
        parsed = urlparse(url)
        if (
            item.get("is_link_only")
            or fid in seen
            or size < 0
            or re.fullmatch("[0-9a-fA-F]{32}", digest) is None
        ):
            raise IntegrityError("Figshare file lacks unique identity/size/checksum")
        if parsed.scheme != "https" or parsed.hostname not in {
            "ndownloader.figshare.com",
            "api.figshare.com",
        }:
            raise IntegrityError("unexpected Figshare download host")
        if (
            parsed.path != f"/files/{fid}"
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.port not in {None, 443}
        ):
            raise IntegrityError("Figshare download URL/file-ID mismatch")
        seen.add(fid)
        records.append(
            FileRecord(
                family="dream",
                snapshot=snapshot,
                relative_path=(
                    f"constituents/set-{row['Set ID']}/figshare-{article}-v{version}/{fid}-{name}"
                ),
                url=url,
                size=size,
                checksum_algorithm="md5",
                checksum=digest.lower(),
                source_id=str(fid),
                metadata={
                    "set_id": row["Set ID"],
                    "registry_key": row["Key ID"],
                    "article_id": article,
                    "article_version": version,
                    "doi": document.get("doi"),
                    "license": document.get("license"),
                },
            )
        )
    return records, {
        "set_id": row["Set ID"],
        "registry_key": row["Key ID"],
        "article_id": article,
        "version": version,
        "api": api,
        "files": len(records),
        "bytes": sum(r.size for r in records),
        "license": document.get("license"),
        "status": "RESOLVED",
    }


def resolve_freidata_row(
    row: dict[str, str], snapshot: str
) -> tuple[list[FileRecord], dict[str, Any]]:
    """Resolve the registry's exact FreiData v1 record with publisher MD5 and byte counts.

    Restricted/changed records fail closed. No participant labels or outcomes are read.
    """
    if row["Accessibility"].casefold() != "open" or row["Revoked"].casefold() != "false":
        raise AccessRequired("FreiData constituent is not explicitly open")
    rid = "31mg4-mfq53"
    if row["Set ID"] != "19" or row["Data URL"] != f"https://doi.org/10.60493/{rid}":
        raise IntegrityError("unrecognized FreiData registry identity")
    api = f"https://freidata.uni-freiburg.de/api/records/{rid}"
    doc = request_json(api, timeout=60, attempts=2)
    if (
        doc.get("id") != rid
        or doc["pids"]["doi"]["identifier"] != f"10.60493/{rid}"
        or doc["versions"]["index"] != 1
    ):
        raise IntegrityError("FreiData record/version mismatch")
    if (
        doc["access"]["files"] != "public"
        or doc["access"]["record"] != "public"
        or doc["access"]["embargo"]["active"] is not False
    ):
        raise AccessRequired("FreiData files are restricted")
    files = doc["files"]
    if files["count"] != 1 or files["total_bytes"] != 46588397863 or len(files["entries"]) != 1:
        raise IntegrityError("FreiData expected inventory changed")
    records = []
    for name, item in files["entries"].items():
        safe_relative_path(name)
        url = urlparse(item["links"]["content"])
        if (
            url.scheme != "https"
            or url.netloc != "freidata.uni-freiburg.de"
            or unquote(url.path) != f"/api/records/{rid}/files/{name}/content"
            or url.query
            or url.fragment
            or item["key"] != name
            or item["access"]["hidden"] is not False
            or item["size"] != files["total_bytes"]
            or item["checksum"] != "md5:dc6d0768de5f521218d13c9768504e24"
        ):
            raise IntegrityError("FreiData file identity mismatch")
        records.append(
            FileRecord(
                family="dream",
                snapshot=snapshot,
                relative_path=f"constituents/set-19/freidata-{rid}-v1/{name}",
                url=item["links"]["content"],
                size=item["size"],
                checksum_algorithm="md5",
                checksum=item["checksum"].split(":")[1],
                source_id=item["id"],
                metadata={
                    "set_id": "19",
                    "registry_key": row["Key ID"],
                    "version": 1,
                    "license": doc["metadata"]["rights"],
                },
            )
        )
    return records, {
        "set_id": "19",
        "registry_key": row["Key ID"],
        "version": 1,
        "api": api,
        "files": 1,
        "bytes": files["total_bytes"],
        "status": "RESOLVED",
        "license": doc["metadata"]["rights"],
    }
