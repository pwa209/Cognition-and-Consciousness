"""Immutable sampler qualification and same-model calibration repair on personal scratch."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from masked_neural_phase import preparation

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.config import load_analysis_spec
from factorcon.models.report_nuts import arviz_diagnostics, fit_ordinal_nuts, grouped_reports
from factorcon.models.report_nuts_validation import validate_sampling
from factorcon.pipeline.measurement import load_report_calibration
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now


def plan(source: Path) -> dict[str, Any]:
    """Validate fixed sampler settings and original prior/anchor; no outcome selection."""
    value = load_structured(source / "conf/masked_report_nuts_plan.yaml")
    expected = {
        "schema_version": 1,
        "family": "masked_content_fmri",
        "sampler": "pymc_nuts_marginal_probit_noncentered",
        "probability_model_changed": False,
        "scientific_gates": False,
        "initialization": "jitter+adapt_full",
        "exact_repeated_likelihood_compression": True,
        "universal_E_scale_validated": False,
        "pymc_version": "5.24.0",
        "arviz_version": "0.22.0",
        "environment": "report-pymc-5.24.0-arviz-0.22.0-v1",
        "prior": "unchanged_N0_2.5_beta_InvGamma2_1_variances_N1_2_positive_upper_cut",
        "rhat_flag": 1.01,
        "bulk_ess_flag": 400,
        "tail_ess_flag": 400,
    }
    if any(value.get(k) != v for k, v in expected.items()):
        raise ValueError("unsupported sampler plan")
    for k in (
        "draws",
        "warmup",
        "chains",
        "cores",
        "seed",
        "qualification_synthetic_draws",
        "qualification_synthetic_warmup",
        "qualification_synthetic_seed",
    ):
        if type(value.get(k)) is not int or value[k] < 1:
            raise ValueError("positive integer sampling settings required")
    if (
        value["chains"] != 4
        or value["cores"] != 4
        or value["draws"] < 1000
        or not 0.8 <= value["target_accept"] < 1
    ):
        raise ValueError("four chains/cores and valid NUTS settings required")
    spec = load_analysis_spec(source / "conf/analysis_spec.yaml")["report_measurement"]
    if (
        spec["context_specific_thresholds"]
        or spec["prior_version"]
        != "beta_normal_sd2.5_variance_invgamma2_1_threshold_normal_index_sd2"
    ):
        raise ValueError("unsupported probability model")
    return value


def verify_release(root: Path, source: Path) -> None:
    """Check authorization and every immutable source hash; no participant access."""
    record = read_source_record(root, source)
    if not record.get("analysis_execution_authorized") or any(
        hash_file(ensure_within(source, source / p)) != h for p, h in record["files"].items()
    ):
        raise ValueError("authorized intact release required")


def verified_outputs(path: Path, source: Path, phase: str) -> dict[str, Any]:
    """Verify a completed attempt and all output hashes before consuming its private data."""
    state = load_structured(path)
    if (
        state.get("status") != "SUCCESS"
        or state.get("source_release") != str(source)
        or state.get("phase") != phase
    ):
        raise ValueError("successful matching-source attempt required")
    if not state.get("outputs"):
        raise ValueError("hashed outputs required")
    for name, digest in state["outputs"].items():
        if hash_file(ensure_within(path.parent, path.parent / name)) != digest:
            raise ValueError("attempt output changed")
    return state


def check_inputs(root: Path, source: Path, producer: Path, prepared: Path) -> Path:
    """Use only the original reserved report trials and unchanged model/cohort specification."""
    preparation(root, producer, prepared)
    for name in (
        "analysis_spec.yaml",
        "masked_neural_plan.yaml",
        "datasets/masked_content_fmri.yaml",
        "construct_maps/masked_content_fmri.yaml",
    ):
        if hash_file(source / "conf" / name) != hash_file(producer / "conf" / name):
            raise ValueError("model/cohort design changed")
    path = prepared.with_name("calibration-input.json")
    data = load_report_calibration(path)
    partition = load_structured(prepared.with_name("partition.json"))
    # Preparation verifies partition and calibration-input hashes. The original
    # preparation routine enforces disjoint allocation; reassert its trial count here.
    expected = load_structured(source / "conf/masked_neural_plan.yaml")["calibration_participants"]
    reserved = {f"masked_content_fmri:{s}" for s in partition["calibration_subjects"]}
    evaluation = {f"masked_content_fmri:{s}" for s in partition["evaluation_subjects"]}
    if (
        len(set(data.subjects)) != expected
        or set(data.subjects) != reserved
        or reserved & evaluation
    ):
        raise ValueError("reserved calibration cohort mismatch")
    grouped_reports(data)
    return path


def action(
    root: Path,
    source: Path,
    producer: Path,
    prepared: Path,
    attempt: Path,
    phase: str,
    settings: dict[str, Any],
    qualification: Path | None,
) -> dict[str, Any]:
    """Execute synthetic verification or independent empirical report fitting, in probit units."""
    for package in ("pymc", "arviz"):
        if version(package) != settings[package + "_version"]:
            raise ValueError("runtime version mismatch")
    atomic_write_json(
        attempt / "runtime.json",
        {p: version(p) for p in ("pymc", "arviz", "pytensor", "numpy", "scipy")},
    )
    if phase == "QUALIFY_NUTS":
        with (attempt / "pytest.log").open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp",
                    str(attempt / "pytest-tmp"),
                ],
                cwd=source,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
            )
        return validate_sampling(settings)
    if qualification is None:
        raise ValueError("sampler qualification required")
    ensure_within(root / "analysis/masked-neural/QUALIFY_NUTS", qualification)
    verified_outputs(qualification, source, "QUALIFY_NUTS")
    path = check_inputs(root, source, producer, prepared)
    data = load_report_calibration(path)
    atomic_write_json(
        attempt / "input-record.json",
        {"path": str(path), "sha256": hash_file(path), "preparation_sha256": hash_file(prepared)},
    )
    # Old chains remain untouched and are independently audited, never used as truth.
    audits = []
    for oldphase, job in (("CALIBRATE", "21417198"), ("CALIBRATE_EXTENDED", "21417467")):
        oldstatus = root / "analysis/masked-neural" / oldphase / job / "status.json"
        oldsource = Path(load_structured(oldstatus)["source_release"])
        verify_release(root, oldsource)
        verified_outputs(oldstatus, oldsource, oldphase)
        old = load_structured(oldstatus.with_name("posterior.json"))
        audit = arviz_diagnostics(old["posterior"])
        atomic_write_json(attempt / (oldphase + "-audit.json"), audit)
        audits.append(
            {
                "phase": oldphase,
                "job": job,
                "max_rhat": audit["max_rank_folded_split_rhat"],
                "min_bulk_ess": audit["min_bulk_ess_estimate"],
            }
        )
    posterior, diagnostic, idata = fit_ordinal_nuts(
        data,
        **{k: settings[k] for k in ("draws", "warmup", "chains", "seed", "cores", "target_accept")},
    )
    payload = {
        k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in asdict(posterior).items()
    }
    atomic_write_json(
        attempt / "posterior.json",
        {
            "schema_version": 1,
            "implementation": "hierarchical_ordinal_probit_v1",
            "sampler": settings["sampler"],
            "posterior": payload,
            "calibration_ids": sorted(set(data.subjects)),
            "operational_E": "probability_report_liability_exceeds_first_threshold",
            "universal_consciousness_probability": False,
            "diagnostic_flags": diagnostic["flags"],
            "calibration_neural_overlap_check": "required_globally_when_patterns_are_loaded",
        },
    )
    atomic_write_json(attempt / "diagnostics.json", diagnostic)
    np.savez_compressed(
        attempt / "sampler-traces.npz",
        **{
            f"{group}__{name}": value.values
            for group in ("posterior", "sample_stats")
            for name, value in getattr(idata, group).data_vars.items()
        },
    )
    return {
        "diagnostics": {k: v for k, v in diagnostic.items() if k != "parameters"},
        "old_attempts": audits,
        "old_posteriors_preserved": True,
        "calibration_participants": len(set(data.subjects)),
        "probability_model_changed": False,
        "neural_noise_calibration": False,
        "universal_E_scale_validated": False,
    }


def run(
    root: Path,
    source: Path,
    producer: Path,
    prepared: Path,
    attempt: Path,
    phase: str,
    *,
    qualification: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Atomic attempt lifecycle; retries use new directories, unfavorable diagnostics persist."""
    if phase not in {"QUALIFY_NUTS", "CALIBRATE_NUTS"}:
        raise ValueError("unsupported phase")
    ensure_within(root / "analysis/masked-neural" / phase, attempt)
    settings = plan(source)
    if dry_run:
        path = check_inputs(root, source, producer, prepared)
        return {"dry_run": True, "settings": settings, "input_sha256": hash_file(path)}
    attempt.mkdir(parents=True, exist_ok=False)
    details = {
        "status": "RUNNING",
        "phase": phase,
        "source_release": str(source),
        "started_utc": utc_now(),
        "settings": settings,
        "scientific_gate": None,
    }

    def state() -> None:
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    state()
    previous = signal.signal(signal.SIGTERM, stop)
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(1_000_000_000)
        result = action(root, source, producer, prepared, attempt, phase, settings, qualification)
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
        details.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        state()
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)


def main() -> int:
    """Run authorized, checksum-verified source on Slurm only; dry-run does no fitting."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--phase", choices=["QUALIFY_NUTS", "CALIBRATE_NUTS"], required=True)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root, source = validate_fresh_root(args.root), Path(__file__).resolve().parents[2]
    for release in (source, args.producer):
        verify_release(root, release)
    job = os.environ.get("SLURM_JOB_ID", "")
    if not args.dry_run and not job.isdigit():
        raise ValueError("numeric Slurm job required")
    os.umask(0o077)
    result = run(
        root,
        source,
        args.producer,
        args.prepared,
        root / "analysis/masked-neural" / args.phase / (job or "dry-run"),
        args.phase,
        qualification=args.qualification,
        dry_run=args.dry_run,
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
