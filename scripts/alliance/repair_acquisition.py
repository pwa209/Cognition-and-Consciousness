"""Isolated repair campaign: preserve the active acquisition release and its summaries."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import signal
import uuid
from pathlib import Path

from factorcon.acquire.cogitate import catalog_records
from factorcon.acquire.dream_constituents import (
    current_registry,
    resolve_figshare_row,
    resolve_freidata_row,
)
from factorcon.acquire.http import download_many
from factorcon.acquire.manager import _fingerprint
from factorcon.acquire.openneuro import resolve_openneuro
from factorcon.acquire.records import FileRecord
from factorcon.alliance import (
    ScratchQuotaGuard,
    read_source_record,
    scratch_environment,
    validate_fresh_root,
)
from factorcon.config import load_project
from factorcon.util import (
    atomic_write_json,
    ensure_within,
    hash_file,
    read_jsonl,
    utc_now,
    write_jsonl,
)


def main() -> int:
    """Resolve or acquire one affected family, using byte-bound manifests and one worker.

    No scientific analysis is run. Status and provenance are separate from the original
    campaign. Restart uses the frozen manifest and original file ledger/partials.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--family", choices=["dream", "cogitate", "propofol_volition_fmri", "bmvp"], required=True
    )
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    release = read_source_record(root, source)
    project = load_project(source / "conf/base.yaml")
    dataset = next(d for d in project.datasets if d.family == args.family)
    for relative, digest in release["files"].items():
        if hash_file(source / relative) != digest:
            raise ValueError(f"release file changed: {relative}")
    if args.catalog:
        ensure_within(root, args.catalog)
        catalog_records(json.loads(args.catalog.read_text()))
    if args.family == "cogitate" and args.catalog is None:
        raise ValueError("private owner-authorized catalog required")
    run = root / "operations/acquisition-repair-v1" / args.family
    guard = ScratchQuotaGuard(run / "personal-quota.json")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "family": args.family,
                    "root": str(root),
                    "source": str(source),
                    "workers": 1,
                    "writes_original_summary": False,
                }
            )
        )
        return 0
    os.umask(0o077)
    for key, value in scratch_environment(root).items():
        Path(value).mkdir(parents=True, exist_ok=True)
        os.environ[key] = value
    run.mkdir(parents=True, exist_ok=True)
    attempt = uuid.uuid4().hex
    manifest = run / "manifest.jsonl"
    summary_path = run / "resolution.json"
    holds = []

    def state(status: str, **details: object) -> None:
        value = {
            "status": status,
            "updated_utc": utc_now(),
            "attempt": attempt,
            "pid": os.getpid(),
            "family": args.family,
            "source_release": str(source),
            "root": str(root),
            "scientific_gates": False,
            "holds": holds,
            **details,
        }
        atomic_write_json(run / f"attempt-{attempt}.json", value)
        atomic_write_json(run / "status.json", value)

    def interrupted(signum: int, frame: object) -> None:
        state("INTERRUPTED", signal=signum)
        raise SystemExit(128 + signum)

    with contextlib.ExitStack() as stack:
        lock = stack.enter_context((run / "campaign.lock").open("a+"))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.family == "bmvp":
            original_lock = stack.enter_context(
                (root / "operations/acquisition/campaign.lock").open("a+")
            )
            fcntl.flock(original_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        state("RESOLVING")
        try:
            guard(0)
            if manifest.exists() and summary_path.exists():
                resolution = json.loads(summary_path.read_text())
                if resolution["manifest_sha256"] != hash_file(manifest):
                    raise ValueError("frozen repair manifest changed")
                records = [FileRecord.from_dict(r) for r in read_jsonl(manifest)]
                holds = resolution["holds"]
            else:
                records = []
                details = {}
                if args.family == "dream":
                    registry = (
                        root / "data/raw/dream" / dataset.snapshot_label / "registry/Datasets.csv"
                    )
                    current, old = current_registry(registry, expected_rows=22, expected_sets=20)
                    details = {
                        "registry_sha256": hash_file(registry),
                        "superseded_rows": old,
                        "sets": [],
                    }
                    for row in current:
                        try:
                            resolver = (
                                resolve_freidata_row
                                if row["Set ID"] == "19"
                                else resolve_figshare_row
                            )
                            found, info = resolver(row, dataset.snapshot_label)
                            records.extend(found)
                            details["sets"].append(info)
                        except Exception as exc:
                            holds.append(
                                {
                                    "set_id": row["Set ID"],
                                    "registry_key": row["Key ID"],
                                    "reason": f"{type(exc).__name__}: {exc}",
                                }
                            )
                elif args.family == "bmvp":
                    original = root / "manifests/generated/bmvp" / f"{dataset.snapshot_label}.jsonl"
                    records = [FileRecord.from_dict(r) for r in read_jsonl(original)]
                    if len(records) != int(dataset.values["expected_archive_urls"]):
                        raise ValueError("BMVP frozen archive count mismatch")
                    ledger = (
                        root / "run_state/P02" / f"bmvp.{dataset.snapshot_label}.downloads.json"
                    )
                    previous = json.loads(ledger.read_text())
                    fingerprint = _fingerprint(records)
                    if previous["source_manifest_sha256"] != fingerprint:
                        raise ValueError("BMVP original manifest/ledger identity mismatch")
                    details = {
                        "download_manifest_sha256": fingerprint,
                        "original_manifest_sha256": hash_file(original),
                        "resume_original_ledger": str(ledger),
                    }
                elif args.family == "cogitate":
                    catalog = json.loads(args.catalog.read_text())
                    records = catalog_records(catalog)
                    holds = catalog.get("holds", [])
                    details = {"catalog_sha256": hash_file(args.catalog)}
                else:
                    records = resolve_openneuro(dataset)
                if not records:
                    raise ValueError("no downloadable objects; inspect source/access holds")
                write_jsonl(manifest, (r.as_dict() for r in records))
                resolution = {
                    "manifest_sha256": hash_file(manifest),
                    "files": len(records),
                    "bytes": sum(r.size or 0 for r in records),
                    "holds": holds,
                    **details,
                }
                atomic_write_json(summary_path, resolution)
            if args.resolve_only:
                state("RESOLVED_WITH_HOLDS" if holds else "RESOLVED", resolution=resolution)
                return 0
            state("DOWNLOADING", files=len(records), manifest_sha256=hash_file(manifest))
            snapshot = "exp1_20231231" if args.family == "cogitate" else dataset.snapshot_label
            ledger = (
                root / "run_state/P02" / f"bmvp.{snapshot}.downloads.json"
                if args.family == "bmvp"
                else run / "downloads.json"
            )
            result = download_many(
                records,
                root / "data/raw" / args.family / snapshot,
                ledger,
                workers=1,
                source_manifest_sha256=resolution.get(
                    "download_manifest_sha256", hash_file(manifest)
                ),
                storage_guard=guard,
            )
            state("FINISHED_WITH_HOLDS" if holds else "SUCCESS", downloads=result)
            return 3 if holds else 0
        except Exception as exc:
            state("FAILED", error=f"{type(exc).__name__}: {exc}")
            raise


if __name__ == "__main__":
    raise SystemExit(main())
