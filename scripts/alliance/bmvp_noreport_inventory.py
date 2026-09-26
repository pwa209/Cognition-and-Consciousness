"""Inventory all acquired BMVP no-report MRI metadata on a Slurm compute node.

This is source qualification, not P04 event alignment, E calibration, a neural
bundle, or a P08 cross-family fit. Raw TARs stay packed and unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import tarfile
from pathlib import Path
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.errors import IntegrityError
from factorcon.pipeline.bmvp_noreport_inventory import summarize_noreport_mri_archive
from factorcon.util import atomic_write_json, hash_file, load_structured, read_jsonl, utc_now


def validate_plan(plan: dict[str, Any]) -> None:
    """Require all-source metadata inventory counts and noninferential scope."""
    expected = {
        "schema_version": 1,
        "family": "bmvp",
        "scope": "metadata_only_all_verified_noreport_archives_not_P08",
        "selection_basis": "all_67_P03_verified_noreport_archives_before_neural_outcomes",
        "expected_noreport_archives": 67,
        "expected_report_mri_archives": 37,
        "expected_participant_overlap": 2,
        "max_csv_bytes": 2_000_000,
        "read_voxel_data": False,
        "infer_absent_experience_from_unrequested_report": False,
        "cross_family_calibration_validated": False,
        "scientific_gates": False,
    }
    if plan != expected:
        raise ValueError("unsupported BMVP no-report inventory plan")


def archive_rows(ledger_path: Path, plan: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Select all P03-verified NRP archives; metadata units bytes and file IDs."""
    validate_plan(plan)
    rows = list(read_jsonl(ledger_path))
    nrp = [
        row for row in rows
        if re.fullmatch(r"archives/no_report/[0-9]{3}_NRP\.tar", row["relative_path"])
    ]
    report = [
        row for row in rows
        if re.fullmatch(r"archives/report/[0-9]{3}_RP_MRI\.tar", row["relative_path"])
    ]
    no_ids = {row["relative_path"].split("/")[-1][:3] for row in nrp}
    rp_ids = {row["relative_path"].split("/")[-1][:3] for row in report}
    if (
        len(nrp) != plan["expected_noreport_archives"]
        or len(report) != plan["expected_report_mri_archives"]
        or len(no_ids) != len(nrp)
        or len(rp_ids) != len(report)
        or len(no_ids & rp_ids) != plan["expected_participant_overlap"]
    ):
        raise ValueError("BMVP P03 no-report/report archive identities changed")
    return tuple(sorted(nrp, key=lambda row: row["relative_path"]))


def inventory(root: Path, source: Path, *, job: str = "", dry_run: bool = False) -> dict[str, Any]:
    """Scan archive metadata on compute scratch; preserve holds and fresh attempts.

    Outputs are aggregate counts only, not participant rows or neural data.
    Retry uses a new Slurm job ID and never overwrites old status or inventory.
    """
    root = validate_fresh_root(root)
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("authorized intact source release required")
    plan_path = source / "conf/bmvp_noreport_inventory.yaml"
    plan = load_structured(plan_path)
    rows = archive_rows(root / "analysis/P03/bmvp/21409966/verified-files.jsonl", plan)
    predecessor = load_structured(root / "analysis/P03/bmvp/21409966/status.json")
    if predecessor.get("status") != "SUCCESS" or predecessor.get("family") != "bmvp":
        raise ValueError("successful BMVP P03 predecessor required")
    if dry_run:
        return {"dry_run": True, "archives": len(rows), "scope": plan["scope"]}
    if not job.isdigit() or os.environ.get("SLURM_JOB_ID") != job:
        raise ValueError("matching Slurm compute job required")
    attempt = root / "operations/bmvp-noreport-inventory" / job
    attempt.mkdir(parents=True, exist_ok=False, mode=0o700)
    state: dict[str, Any] = {
        "status": "RUNNING", "job": job, "source_release": str(source),
        "scope": plan["scope"], "started_utc": utc_now(), "scientific_gate": None,
        "plan_sha256": hash_file(plan_path), "p03_sha256": hash_file(root / "analysis/P03/bmvp/21409966/status.json"),
        "archives_expected": len(rows), "archives_scanned": 0,
        "cross_family_calibration_validated": False,
    }

    def save() -> None:
        atomic_write_json(attempt / "status.json", state)
        atomic_write_json(attempt / "provenance.json", state)

    def interrupted(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    save()
    previous = signal.signal(signal.SIGTERM, interrupted)
    results: list[dict[str, Any]] = []
    try:
        for row in rows:
            relative = row["relative_path"]
            participant = relative.rsplit("/", 1)[1][:3]
            archive = root / "data/raw/bmvp/website_inventory_2026-08-30" / relative
            if not archive.is_file() or archive.is_symlink():
                raise ValueError(f"verified archive absent: {relative}")
            stat = archive.stat()
            if stat.st_size != row["bytes"] or stat.st_mtime_ns != row["mtime_ns"]:
                raise ValueError(f"raw archive changed since P03: {relative}")
            try:
                with tarfile.open(archive, "r:") as handle:
                    summary = summarize_noreport_mri_archive(
                        handle, participant, max_csv_bytes=plan["max_csv_bytes"]
                    )
                summary["inventory_status"] = "INSPECTED"
            except (IntegrityError, OSError, ValueError, tarfile.TarError) as exc:
                summary = {
                    "participant": participant, "inventory_status": "HELD",
                    "hold_kind": type(exc).__name__,
                }
            results.append(summary)
            atomic_write_json(attempt / "inventory.json", {"archives": results})
            state["archives_scanned"] = len(results)
            save()
        held = sum(row["inventory_status"] == "HELD" for row in results)
        state.update(
            status="SUCCESS", ended_utc=utc_now(), archives_held=held,
            mri_archives=sum(row.get("bold_700_files", 0) > 0 for row in results),
            inventory_sha256=hash_file(attempt / "inventory.json"),
            event_alignment_validated=False, independent_calibration_validated=False,
            p08_ready=False,
        )
        save()
        return state
    except BaseException as exc:
        state.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        save()
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)


def main() -> int:
    """Run a bounded metadata audit or source/configuration-only dry run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = inventory(args.root, Path(__file__).resolve().parents[2], job=args.job, dry_run=args.dry_run)
    print(json.dumps({key: result[key] for key in ("status", "archives_scanned", "archives_held")}) if not args.dry_run else json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
