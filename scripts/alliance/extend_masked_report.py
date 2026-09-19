"""A fixed larger Monte Carlo budget; preserve the initial unconverged posterior."""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path
from typing import Any

from masked_neural_phase import preparation

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.config import load_analysis_spec
from factorcon.pipeline.measurement import fit_report_file, load_report_calibration
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now


def extended_spec(source: Path) -> dict[str, Any]:
    """Change only Monte Carlo counts; probit units, prior and neural leakage boundary persist."""
    settings = load_structured(source / "conf/masked_report_sampling_extension.yaml")
    if (
        settings.get("schema_version") != 1
        or settings.get("family") != "masked_content_fmri"
        or settings.get("scientific_gates") is not False
        or settings.get("select_best_run_by_scientific_score") is not False
    ):
        raise ValueError("invalid computational extension")
    spec = load_analysis_spec(source / "conf/analysis_spec.yaml")
    for key in ("chains", "draws", "warmup"):
        if type(settings[key]) is not int or settings[key] < spec["report_measurement"][key]:
            raise ValueError("fixed larger sampling budget required")
        spec["report_measurement"][key] = settings[key]
    return spec


def run_extension(
    root: Path,
    source: Path,
    producer: Path,
    prepared: Path,
    attempt: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Refit the same private calibration trials with more iterations, never evaluation data.

    Returns diagnostic flags, not a scientific go/no-go decision. All old attempts
    remain; failed retries require new Slurm IDs. Dry-run reads only metadata/input.
    """
    ensure_within(root / "analysis/masked-neural/CALIBRATE_EXTENDED", attempt)
    spec = extended_spec(source)

    def inputs() -> Path:
        preparation(root, producer, prepared)
        for name in (
            "analysis_spec.yaml",
            "masked_neural_plan.yaml",
            "construct_maps/masked_content_fmri.yaml",
        ):
            if hash_file(source / "conf" / name) != hash_file(producer / "conf" / name):
                raise ValueError("model/cohort design changed; not a sampling-only extension")
        path = prepared.parent / "calibration-input.json"
        load_report_calibration(path)
        return path

    if dry_run:
        path = inputs()
        return {
            "dry_run": True,
            "input_sha256": hash_file(path),
            "sampling": spec["report_measurement"],
        }
    attempt.mkdir(parents=True, exist_ok=False)
    details = {
        "status": "RUNNING",
        "started_utc": utc_now(),
        "source_release": str(source),
        "preparation_source": str(producer),
        "preparation_sha256": hash_file(prepared),
        "phase": "CALIBRATE_EXTENDED",
        "scientific_gate": None,
        "extension_plan_sha256": hash_file(source / "conf/masked_report_sampling_extension.yaml"),
    }

    def state() -> None:
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    state()
    old = signal.signal(signal.SIGTERM, stop)
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        path = inputs()
        atomic_write_json(attempt / "analysis-spec.json", spec)
        posterior = fit_report_file(
            path,
            attempt / "posterior.json",
            analysis_spec=attempt / "analysis-spec.json",
            seed=load_structured(source / "conf/masked_report_sampling_extension.yaml")["seed"],
        )
        result = {
            "diagnostic_flags": posterior["diagnostic_flags"],
            "diagnostics": posterior["posterior"]["diagnostics"],
            "calibration_participants": len(posterior["calibration_ids"]),
            "neural_noise_calibration": False,
            "universal_E_scale_validated": False,
            "initial_posterior_preserved": True,
        }
        atomic_write_json(attempt / "result.json", result)
        details.update(
            status="SUCCESS",
            ended_utc=utc_now(),
            outputs={
                p.name: hash_file(p)
                for p in attempt.iterdir()
                if p.is_file()
                and p.name not in {"status.json", "provenance.json", "personal-quota.json"}
            },
        )
        state()
        return result
    except BaseException as exc:
        details.update(status="FAILED", error=f"{type(exc).__name__}: {exc}", ended_utc=utc_now())
        state()
        raise
    finally:
        signal.signal(signal.SIGTERM, old)


def main() -> int:
    """Verify both immutable releases, owner/root and Slurm identity before private fitting."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    for release in (source, args.producer):
        record = read_source_record(root, release)
        if not record.get("analysis_execution_authorized") or any(
            hash_file(release / p) != h for p, h in record["files"].items()
        ):
            raise ValueError("authorized intact consumer and producer required")
    job = os.environ.get("SLURM_JOB_ID", "")
    if not args.dry_run and not job.isdigit():
        raise ValueError("numeric Slurm ID required")
    os.umask(0o077)
    print(
        json.dumps(
            run_extension(
                root,
                source,
                args.producer,
                args.prepared,
                root / "analysis/masked-neural/CALIBRATE_EXTENDED" / (job or "dry-run"),
                dry_run=args.dry_run,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
