"""P03 integrity and P04 schema normalization for the acquired working-memory family.

No model fitting, consciousness relabeling, source-code execution or archive extraction.
Raw PAS ratings remain ordinal observations; missing reports remain unknown.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path
from typing import Any

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.config import load_project
from factorcon.pipeline.harmonize import harmonize_family
from factorcon.pipeline.validation import validate_family
from factorcon.util import atomic_write_json, hash_file, slug, utc_now

FAMILY = "multisite_working_memory"


def run_phase(project: Any, root: Path, phase: str, attempt: Path) -> dict[str, Any]:
    """Run one private artifact attempt; technical failures retain markers and reports.

    Counts are rows/files/bytes, never effect-based selection. Caller must verify the
    completed acquisition and, for P04, the P03 success artifact before entering here.
    """
    if phase not in {"P03", "P04"}:
        raise ValueError("only validated WM P03/P04 are implemented by this runner")
    attempt.mkdir(parents=True, exist_ok=False)
    source = project.root
    inputs = [
        source / "conf/analysis_spec.yaml",
        source / "conf/base.yaml",
        source / f"conf/datasets/{FAMILY}.yaml",
        source / f"conf/construct_maps/{FAMILY}.yaml",
    ]
    details = {
        "phase": phase,
        "family": FAMILY,
        "status": "RUNNING",
        "started_utc": utc_now(),
        "source_release": str(source),
        "scientific_gate": None,
        "inputs": {str(p): hash_file(p) for p in inputs},
    }
    atomic_write_json(attempt / "provenance.json", details)
    atomic_write_json(attempt / "status.json", details)

    def interrupted(signum: int, frame: object) -> None:
        raise InterruptedError(f"scheduler/user signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        if phase == "P03":
            result = validate_family(project, root, FAMILY, attempt / "report.json", deep_hash=True)
            # Historical validator records ZIP CRC results; explicitly enforce them.
            bad_crc = any(
                v.get("test_result") is not None for v in result.get("archives", {}).values()
            )
            if result["status"] != "valid" or bad_crc:
                raise ValueError(
                    "download/archive technical validation failed; see retained report"
                )
        else:
            result = harmonize_family(
                project, root, FAMILY, attempt / "trials.jsonl", attempt / "report.json"
            )
            if result["status"] != "harmonized" or not result.get("records"):
                raise ValueError("no technically valid working-memory records produced")
    except BaseException as exc:
        details.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)
        raise
    details.update(
        status="SUCCESS",
        ended_utc=utc_now(),
        outputs={
            p.name: hash_file(p)
            for p in attempt.iterdir()
            if p.name in {"report.json", "trials.jsonl"}
        },
    )
    atomic_write_json(attempt / "status.json", details)
    atomic_write_json(attempt / "provenance.json", details)
    return {
        k: result[k]
        for k in ("status", "files", "bytes", "records", "participants", "laboratories")
        if k in result
    }


def main() -> int:
    """Verify fixed inputs and Slurm identity, then run or dry-run without data output."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", choices=["P03", "P04"], required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    marker = read_source_record(root, source)
    if marker.get("analysis_execution_authorized") is not True:
        raise ValueError("analysis execution not authorized")
    project = load_project(source / "conf/base.yaml")
    dataset = next(d for d in project.datasets if d.family == FAMILY)
    ledger = root / "run_state/P02" / f"{FAMILY}.{slug(dataset.snapshot_label)}.downloads.json"
    receipt = json.loads(ledger.read_text())
    manifest = root / "manifests/generated" / FAMILY / f"{slug(dataset.snapshot_label)}.jsonl"
    if receipt.get("success") is not True or receipt["source_manifest_sha256"] != hash_file(
        manifest
    ):
        raise ValueError("same-manifest acquisition completion required")
    if args.phase == "P04":
        predecessor = os.environ.get("FACTORCON_VALIDATION_JOB", "")
        if not predecessor.isdigit():
            raise ValueError("numeric P03 predecessor job required")
        status = root / "analysis/P03" / FAMILY / predecessor / "status.json"
        if json.loads(status.read_text())["status"] != "SUCCESS":
            raise ValueError("P03 technical integrity success required before harmonization")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "phase": args.phase,
                    "family": FAMILY,
                    "source_manifest_sha256": hash_file(manifest),
                }
            )
        )
        return 0
    job = os.environ.get("SLURM_JOB_ID", "")
    if not job.isdigit():
        raise ValueError("numeric Slurm job ID required")
    result = run_phase(project, root, args.phase, root / "analysis" / args.phase / FAMILY / job)
    print(json.dumps({"phase": args.phase, "family": FAMILY, **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
