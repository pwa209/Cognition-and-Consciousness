"""High-level source-manifest and acquisition orchestration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from factorcon.acquire.bmvp import resolve_bmvp
from factorcon.acquire.dream import parse_dream_registry, resolve_dream_registry
from factorcon.acquire.http import download_many
from factorcon.acquire.openneuro import resolve_openneuro
from factorcon.acquire.osf import resolve_osf
from factorcon.acquire.records import FileRecord
from factorcon.config import DatasetConfig, ProjectConfig
from factorcon.errors import AccessRequired, ConfigError, IntegrityError
from factorcon.util import atomic_write_json, hash_file, read_jsonl, slug, utc_now, write_jsonl

Resolver = Callable[[DatasetConfig], list[FileRecord]]

RESOLVERS: dict[str, Resolver] = {
    "osf": resolve_osf,
    "openneuro": resolve_openneuro,
    "bmvp_nitrc": resolve_bmvp,
    "dream_registry": resolve_dream_registry,
}


def _selected(project: ProjectConfig, families: set[str] | None) -> list[DatasetConfig]:
    records = [item for item in project.datasets if families is None or item.family in families]
    if families:
        missing = families - {item.family for item in records}
        if missing:
            raise ConfigError(f"Unknown dataset families: {sorted(missing)}")
    return records


def _manifest_paths(root: Path, dataset: DatasetConfig) -> tuple[Path, Path]:
    directory = root / "manifests" / "generated" / slug(dataset.family)
    stem = slug(dataset.snapshot_label)
    return directory / f"{stem}.jsonl", directory / f"{stem}.summary.json"


def _fingerprint(records: list[FileRecord]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(json.dumps(record.as_dict(), sort_keys=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def resolve_manifests(
    project: ProjectConfig,
    root: str | Path,
    *,
    families: set[str] | None = None,
) -> dict[str, Any]:
    """Resolve and atomically write normalized per-file source manifests."""

    output_root = Path(root)
    summaries: dict[str, Any] = {}
    for dataset in _selected(project, families):
        manifest_path, summary_path = _manifest_paths(output_root, dataset)
        if dataset.access == "account_and_terms_required":
            summary = {
                "family": dataset.family,
                "status": "waiting_access",
                "reason": "owner-created account and terms acceptance required",
                "credentials_policy": dataset.values.get("credentials_policy"),
                "resolved_utc": utc_now(),
                "file_count": 0,
                "known_bytes": 0,
            }
            atomic_write_json(summary_path, summary)
            summaries[dataset.family] = summary
            continue
        resolver = RESOLVERS.get(dataset.source_type)
        if resolver is None:
            raise ConfigError(f"No resolver for source_type={dataset.source_type}")
        records = resolver(dataset)
        relative_paths = [item.relative_path for item in records]
        if len(relative_paths) != len(set(relative_paths)):
            raise IntegrityError(f"Duplicate paths in {dataset.family} manifest")
        write_jsonl(manifest_path, (item.as_dict() for item in records))
        summary = {
            "family": dataset.family,
            "status": "resolved",
            "source_type": dataset.source_type,
            "source_id": dataset.values["source_id"],
            "snapshot": dataset.snapshot_label,
            "access": dataset.access,
            "license": dataset.values.get("license"),
            "resolved_utc": utc_now(),
            "file_count": len(records),
            "known_bytes": sum(item.size or 0 for item in records),
            "unknown_size_files": sum(item.size is None for item in records),
            "manifest": str(manifest_path),
            "manifest_sha256": hash_file(manifest_path),
            "record_fingerprint_sha256": _fingerprint(records),
        }
        atomic_write_json(summary_path, summary)
        summaries[dataset.family] = summary
    index = {
        "generated_utc": utc_now(),
        "families": summaries,
        "registration": project.analysis_spec["registration"],
        "scientific_gates": project.analysis_spec["scientific_gates"],
    }
    atomic_write_json(output_root / "manifests" / "generated" / "index.json", index)
    return index


def acquire_families(
    project: ProjectConfig,
    root: str | Path,
    *,
    families: set[str] | None = None,
    workers: int | None = None,
    resolve: bool = True,
) -> dict[str, Any]:
    """Download every eligible manifest object directly beneath the canonical root."""

    output_root = Path(root)
    if resolve:
        resolve_manifests(project, output_root, families=families)
    statuses: dict[str, Any] = {}
    for dataset in _selected(project, families):
        manifest_path, summary_path = _manifest_paths(output_root, dataset)
        if dataset.access == "account_and_terms_required":
            statuses[dataset.family] = {"status": "waiting_access", "summary": str(summary_path)}
            continue
        if not manifest_path.is_file():
            raise ConfigError(f"Missing manifest for {dataset.family}: {manifest_path}")
        records = [FileRecord.from_dict(value) for value in read_jsonl(manifest_path)]
        destination = output_root / "data" / "raw" / slug(dataset.family) / slug(dataset.snapshot_label)
        ledger = output_root / "run_state" / "P02" / f"{slug(dataset.family)}.downloads.json"
        family_workers = int(
            workers
            or dataset.values.get("max_parallel_downloads")
            or project.server.get("max_parallel_downloads", 4)
        )
        try:
            result = download_many(records, destination, ledger, workers=family_workers)
        except Exception as exc:
            status = {
                "family": dataset.family,
                "status": "failed_integrity_or_source",
                "error": f"{type(exc).__name__}: {exc}",
                "updated_utc": utc_now(),
            }
            atomic_write_json(output_root / "run_state" / "P02" / f"{slug(dataset.family)}.FAILED.json", status)
            statuses[dataset.family] = status
            continue

        if dataset.source_type == "dream_registry":
            registry_path = destination / "registry" / "Datasets.csv"
            direct, unresolved = parse_dream_registry(registry_path, dataset)
            constituent_manifest = manifest_path.with_name(manifest_path.stem + ".constituents.jsonl")
            write_jsonl(constituent_manifest, (item.as_dict() for item in direct))
            atomic_write_json(
                constituent_manifest.with_suffix(".unresolved.json"),
                {"updated_utc": utc_now(), "records": unresolved},
            )
            if direct:
                result["constituents"] = download_many(
                    direct,
                    destination,
                    output_root / "run_state" / "P02" / "dream.constituents.downloads.json",
                    workers=family_workers,
                )
            result["unresolved_constituents"] = len(unresolved)
        status = {
            "family": dataset.family,
            "status": "success",
            "updated_utc": utc_now(),
            **result,
        }
        atomic_write_json(output_root / "run_state" / "P02" / f"{slug(dataset.family)}.SUCCESS.json", status)
        statuses[dataset.family] = status
    summary = {
        "updated_utc": utc_now(),
        "families": statuses,
        "all_public_success": all(
            value.get("status") in {"success", "waiting_access"} for value in statuses.values()
        ),
    }
    atomic_write_json(output_root / "run_state" / "P02" / "SUMMARY.json", summary)
    return summary

