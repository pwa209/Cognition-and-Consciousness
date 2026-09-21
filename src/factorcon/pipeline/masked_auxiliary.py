"""Pinned, packed publisher timing and same-space atlas acquisition on personal scratch."""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from factorcon.pipeline.masked_timing import behavior_path, git_blob_sha
from factorcon.util import atomic_write_json, hash_file, safe_relative_path


def fetch(url: str) -> bytes:
    """Read a bounded HTTPS source object, never execute downloaded contents."""
    if not url.startswith("https://"):
        raise ValueError("HTTPS required")
    request = urllib.request.Request(
        url, headers={"User-Agent": "factorcon-reproducible-source-audit"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise ValueError("auxiliary object exceeds 32 MiB bound")
    return data


def select_behavior(
    tree: dict[str, Any], runs: list[dict[str, Any]], plan: dict[str, Any]
) -> dict[str, str]:
    """Match each BIDS run to exactly one pinned Git blob; no report/neural selection."""
    if tree.get("truncated") is not False or not tree.get("sha"):
        raise ValueError("complete pinned publisher tree required")
    candidates = {
        r["path"]: r["sha"]
        for r in tree["tree"]
        if r["type"] == "blob"
        and r["path"].startswith("data/behavioral/")
        and r["path"].endswith(".csv")
    }
    if (
        len(candidates) != plan["expected_source_behavior_files"]
        or len(runs) != plan["expected_runs"]
    ):
        raise ValueError("publisher/acquired run expected-count mismatch")
    paths = [behavior_path(r) for r in runs]
    if len(set(paths)) != len(paths) or not set(paths) <= candidates.keys():
        raise ValueError("source/run mapping is missing or nonunique")
    for path in paths:
        safe_relative_path(path)
    return {p: candidates[p] for p in paths}


def acquire(
    attempt: Path,
    runs: list[dict[str, Any]],
    plan: dict[str, Any],
    *,
    reader: Callable[[str], bytes] = fetch,
) -> dict[str, Any]:
    """Download 380 matched CSVs into one tar, preserving upstream bytes and Git/SHA-256 identities.

    The caller owns a fresh study-scratch attempt and its status/provenance markers.
    No extraction, credentials, execution or participant data in the source repository.
    """
    revision = plan["publisher_revision"]
    base = f"https://raw.githubusercontent.com/nmningmei/unconfeats/{revision}/"
    tree = json.loads(
        reader(
            f"https://api.github.com/repos/nmningmei/unconfeats/git/trees/{revision}?recursive=1"
        )
    )
    selected = select_behavior(tree, runs, plan)
    records = {}
    with tarfile.open(attempt / "behavior.tar", "x") as archive:
        for path, identity in [
            *selected.items(),
            ("LICENSE", next(r["sha"] for r in tree["tree"] if r["path"] == "LICENSE")),
        ]:
            content = reader(base + urllib.parse.quote(path))
            if git_blob_sha(content) != identity:
                raise ValueError("upstream Git blob identity mismatch")
            info = tarfile.TarInfo(path)
            info.size, info.mode, info.mtime = len(content), 0o600, 0
            archive.addfile(info, io.BytesIO(content))
            records[path] = {
                "git_blob": identity,
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
    atlas_base = f"https://raw.githubusercontent.com/templateflow/tpl-MNI152NLin2009cAsym/{plan['atlas_revision']}/"
    atlas_records = {}
    for name in ("LICENSE", "template_description.json"):
        content = reader(atlas_base + name)
        with (attempt / ("template-" + name)).open("xb") as handle:
            handle.write(content)
    for name in (plan["atlas"], plan["atlas_labels"]):
        safe_relative_path(name)
        content = reader(atlas_base + name)
        if name.endswith(".nii.gz"):
            pointer = content.decode()
            match = re.search(r"(SHA256E|MD5E)-s(\d+)--([a-f0-9]+)\.nii\.gz", pointer)
            if not match:
                raise ValueError("pinned atlas must expose its annex identity")
            content = reader(
                f"https://templateflow.s3.amazonaws.com/tpl-MNI152NLin2009cAsym/{name}"
            )
            digest = hashlib.sha256 if match[1] == "SHA256E" else hashlib.md5
            if (
                len(content) != int(match[2])
                or digest(content).hexdigest() != match[3]
                or hashlib.sha256(content).hexdigest() != plan["atlas_sha256"]
            ):
                raise ValueError("atlas annex size/hash mismatch")
        with (attempt / name).open("xb") as handle:
            handle.write(content)
        atlas_records[name] = {"sha256": hash_file(attempt / name), "bytes": len(content)}
    record = {
        "publisher_revision": revision,
        "atlas_revision": plan["atlas_revision"],
        "behavior": records,
        "atlas": atlas_records,
        "unused_behavior_files": sorted(
            r["path"]
            for r in tree["tree"]
            if r["path"].startswith("data/behavioral/")
            and r["path"].endswith(".csv")
            and r["path"] not in selected
        ),
    }
    atomic_write_json(attempt / "source-record.json", record)
    return {
        "behavior_runs": len(selected),
        "archive_sha256": hash_file(attempt / "behavior.tar"),
        "downloaded_to_personal_scratch": True,
    }


def read_member(archive: tarfile.TarFile, name: str, expected: dict[str, Any]) -> bytes:
    """Read one regular tar member without extracting; reject escape, links and altered bytes."""
    safe_relative_path(name)
    member = archive.getmember(name)
    if not member.isfile() or member.size != expected["bytes"]:
        raise ValueError("unexpected archive member type/size")
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError("missing archive member")
    data = handle.read()
    if hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise ValueError("packed source bytes changed")
    return data
