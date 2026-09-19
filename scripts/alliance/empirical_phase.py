"""Rorqual empirical P03/P04 execution, versioned attempts and technical dependencies."""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path
from typing import Any

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.config import load_project
from factorcon.pipeline.cogitate_events import harmonize_cogitate_fmri
from factorcon.pipeline.empirical import inventory_sources, resolve_acquired_input, verify_downloads
from factorcon.pipeline.harmonize import harmonize_family
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now


def validate_plan(plan: dict[str, Any], phase: str, family: str) -> None:
    """Validate configured phase/family and no scientific gates, without data fitting."""
    if (
        plan.get("schema_version") != 1
        or plan.get("scientific_gates") is not False
        or family not in plan["families"]
        or phase not in {"P03", "P04"}
    ):
        raise ValueError("invalid empirical plan/phase/family")
    if phase == "P04" and family not in plan["harmonization_ready"]:
        raise ValueError("source-specific harmonizer not validated")
    if plan["integrity"]["mode"] != "sha256_against_acquisition_ledger":
        raise ValueError("unknown empirical integrity mode")


def run_phase(
    source: Path,
    root: Path,
    phase: str,
    family: str,
    attempt: Path,
    predecessor: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute counts/byte validation or observed-event normalization, no model fitting.

    An attempt directory is immutable after completion. Retry with a new Slurm ID;
    failed outputs remain. A predecessor must bind the same manifest and source.
    Dry-run validates identities/configuration/dependency without creating outputs.
    """
    plan = load_structured(source / "conf/empirical_plan.yaml")
    validate_plan(plan, phase, family)
    project = load_project(source / "conf/base.yaml")
    dataset = next(d for d in project.datasets if d.family == family)
    if dry_run:
        inputs = resolve_acquired_input(root, dataset)
        if phase == "P04":
            check_predecessor(root, source, family, inputs.manifest_sha256, predecessor)
        return {
            "dry_run": True,
            "family": family,
            "phase": phase,
            "files": len(inputs.records),
            "manifest_sha256": inputs.manifest_sha256,
        }
    attempt.mkdir(parents=True, exist_ok=False)
    details: dict[str, Any] = {
        "phase": phase,
        "family": family,
        "status": "RUNNING",
        "started_utc": utc_now(),
        "source_release": str(source),
        "scientific_gate": None,
        "scope": "byte_integrity_and_schema" if phase == "P03" else "observed_event_harmonization",
    }

    def state() -> None:
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)

    state()
    old_handler = signal.getsignal(signal.SIGTERM)

    def interrupted(signum: int, frame: object) -> None:
        raise InterruptedError(f"scheduler/user signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        configs = [
            "analysis_spec.yaml",
            "empirical_plan.yaml",
            "base.yaml",
            f"datasets/{family}.yaml",
            f"construct_maps/{family}.yaml",
        ]
        details["configuration_sha256"] = {p: hash_file(source / "conf" / p) for p in configs}
        inputs = resolve_acquired_input(root, dataset)
        details.update(
            manifest_sha256=inputs.manifest_sha256,
            acquisition_identity=inputs.acquisition_identity,
            ledger_sha256=hash_file(inputs.ledger),
            holds=list(inputs.holds),
        )
        state()
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        if phase == "P03":

            def progress(value: dict[str, Any]) -> None:
                atomic_write_json(attempt / "progress.json", {**value, "updated_utc": utc_now()})

            # Schema census first: this remains useful if a later byte check fails.
            inventory_sources(
                inputs,
                attempt / "inventory.jsonl",
                max_metadata_bytes=plan["integrity"]["max_metadata_bytes"],
            )
            result = verify_downloads(inputs, attempt / "verified-files.jsonl", progress=progress)
            result.update(schema_census="inventory.jsonl", full_archive_crc_checked=False)
        else:
            check_predecessor(root, source, family, inputs.manifest_sha256, predecessor)
            details["predecessor"] = str(predecessor)
            details["predecessor_sha256"] = hash_file(predecessor)
            if family == "cogitate":
                result = harmonize_cogitate_fmri(
                    inputs,
                    attempt / "trials.jsonl",
                    expected_participants=dataset.values["expected_participants"]["fmri"],
                    expected_event_files=dataset.values["exp1_bids_event_files"]["fmri"],
                )
            else:
                result = harmonize_family(
                    project, root, family, attempt / "trials.jsonl", attempt / "report.json"
                )
            if result.get("status") != "harmonized" or not result.get("records"):
                raise ValueError("no valid source-specific event records produced")
        atomic_write_json(attempt / "report.json", result)
        details.update(
            status="SUCCESS",
            ended_utc=utc_now(),
            outputs={
                p.name: hash_file(p)
                for p in attempt.iterdir()
                if p.name
                in {
                    "report.json",
                    "inventory.jsonl",
                    "inventory.summary.json",
                    "trials.jsonl",
                    "verified-files.jsonl",
                }
            },
        )
        state()
        return {
            k: v for k, v in result.items() if k in {"files", "bytes", "records", "participants"}
        }
    except BaseException as exc:
        details.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        state()
        raise
    finally:
        signal.signal(signal.SIGTERM, old_handler)


def check_predecessor(
    root: Path, source: Path, family: str, manifest_hash: str, predecessor: Path | None
) -> None:
    """Require same-run P03 SUCCESS identity, not a scientific effect threshold."""
    if predecessor is None:
        raise ValueError("P03 predecessor required")
    ensure_within(root / "analysis/P03" / family, predecessor)
    data = json.loads(predecessor.read_text())
    if (
        data.get("status") != "SUCCESS"
        or data.get("phase") != "P03"
        or data.get("family") != family
        or data.get("source_release") != str(source)
        or data.get("manifest_sha256") != manifest_hash
    ):
        raise ValueError("P03 predecessor identity/status mismatch")


def main() -> int:
    """Validate owner/host/release, execute a Slurm attempt or read-only dry run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", choices=["P03", "P04"], required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--predecessor", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True:
        raise ValueError("Compute Canada analysis authorization required")
    for relative, digest in record["files"].items():
        if hash_file(source / relative) != digest:
            raise ValueError("immutable source file changed")
    job = os.environ.get("SLURM_JOB_ID", "")
    if not args.dry_run and not job.isdigit():
        raise ValueError("numeric Slurm job ID required")
    os.umask(0o077)
    attempt = ensure_within(root, root / "analysis" / args.phase / args.family / (job or "dry-run"))
    print(
        json.dumps(
            run_phase(
                source,
                root,
                args.phase,
                args.family,
                attempt,
                args.predecessor,
                dry_run=args.dry_run,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
