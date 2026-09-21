"""Immutable, dependency-bound masked-fMRI feature/calibration/downstream attempts."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import signal
import struct
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.pipeline.masked_auxiliary import acquire, read_member
from factorcon.pipeline.masked_features import (
    combine_partitions,
    estimate_ar1,
    linear_summary,
    run_design,
    validate_feature_plan,
)
from factorcon.pipeline.masked_timing import align_run, behavior_path
from factorcon.util import (
    atomic_write_json,
    ensure_within,
    hash_file,
    load_structured,
    safe_relative_path,
    utc_now,
)


def proof(
    root: Path, relative: str, *, phase: str | None = None, source: Path | None = None
) -> Path:
    """Verify a technical-success marker and all declared output hashes; no result threshold."""
    path = ensure_within(root, root / safe_relative_path(relative))
    value = load_structured(path)
    if (
        value.get("status") != "SUCCESS"
        or value.get("scientific_gate") is not None
        or (phase is not None and value.get("phase") != phase)
        or (source is not None and value.get("source_release") != str(source))
    ):
        raise ValueError(f"upstream technical status/identity mismatch: {relative}")
    if not value.get("outputs"):
        raise ValueError("upstream hashed output inventory missing")
    for name, digest in value["outputs"].items():
        if hash_file(ensure_within(path.parent, path.parent / safe_relative_path(name))) != digest:
            raise ValueError("upstream output bytes changed")
    return path.parent


def npz_bytes(**arrays: Any) -> bytes:
    """Serialize numeric/string arrays without pickle; compact per-run artifact in a subject ZIP."""
    stream = io.BytesIO()
    np.savez_compressed(stream, **arrays)
    return stream.getvalue()


def read_runs(
    root: Path, config: dict[str, Any], source: Path
) -> tuple[list[dict[str, Any]], dict[str, Any], Path]:
    """Verify prepared run inventory/partition and prior full raw integrity evidence."""
    from masked_neural_phase import source_integrity

    directory = proof(root, config["prepared"], phase="PREPARE")
    raw = source_integrity(
        root, source, root / config["p03"], root / config["p03_source"]
    ).data_root
    return (
        load_structured(directory / "runs.json")["runs"],
        load_structured(directory / "partition.json"),
        raw,
    )


def extract_subject(
    root: Path, source: Path, config: dict[str, Any], attempt: Path
) -> dict[str, Any]:
    """Verify scanner timing and extract unscaled series; select coverage by geometry only."""
    from factorcon.pipeline.masked_parcels import extract_parcels

    plan = load_structured(source / "conf/masked_feature_plan.yaml")
    runs, _, raw = read_runs(root, config, source)
    runs = sorted(
        [r for r in runs if r["subject"] == config["subject"]],
        key=lambda r: tuple(map(int, re.findall(r"(?:ses-|run-)(\d+)", r["run_id"]))),
    )
    preproc = proof(root, config["preprocessing"], phase="PREPROCESS")
    if load_structured(preproc / "status.json")["subject"] != config["subject"]:
        raise ValueError("preprocessing participant mismatch")
    hashes = load_structured(preproc / "derivative-hashes.json")
    aux = proof(root, config["auxiliary"], phase="AUX", source=source)
    record = load_structured(aux / "source-record.json")
    ledger, source_hashes = [], {}
    with (
        tarfile.open(aux / "behavior.tar") as behavior,
        zipfile.ZipFile(attempt / "runs.zip", "x") as packed,
    ):
        for index, run in enumerate(runs):
            prefix = f"derivatives/{run['subject']}/{run['session']}/func/{run['run_id']}"
            names = {
                "bold": prefix + "_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz",
                "mask": prefix + "_space-MNI152NLin2009cAsym_res-2_desc-brain_mask.nii.gz",
                "metadata": prefix + "_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.json",
                "confounds": prefix + "_desc-confounds_timeseries.tsv",
            }
            paths = {key: ensure_within(preproc, preproc / value) for key, value in names.items()}
            for key, path in paths.items():
                if hash_file(path) != hashes[names[key]]:
                    raise ValueError("preprocessed bytes differ from successful MRI receipt")
                source_hashes[names[key]] = hashes[names[key]]
            metadata = load_structured(paths["metadata"])
            if metadata.get("SliceTimingCorrected") is not True or "StartTime" not in metadata:
                raise ValueError("explicit corrected acquisition reference required")
            confounds = list(
                csv.DictReader(io.StringIO(paths["confounds"].read_text()), delimiter="\t")
            )
            event_file = ensure_within(raw, raw / safe_relative_path(run["events"]))
            if hash_file(event_file) != run["events_sha256"]:
                raise ValueError("source events changed")
            path = behavior_path(run)
            original = read_member(behavior, path, record["behavior"][path])
            timing = align_run(
                event_file.read_bytes(),
                original,
                volumes=len(confounds),
                tr_seconds=run["repetition_time_seconds"],
            )
            task, nuisance, qc = run_design(
                timing["trials"],
                confounds,
                run["repetition_time_seconds"],
                metadata["StartTime"],
                plan,
            )
            entry = {**run, "partition": index % 2, "timing": timing, "qc": qc}
            if not qc["excluded"]:
                series, coverage = extract_parcels(
                    paths["bold"], paths["mask"], aux / plan["atlas"]
                )
                if len(series) != len(confounds):
                    raise ValueError("preprocessed BOLD/confounds count mismatch")
                member = run["run_id"] + ".npz"
                packed.writestr(
                    member,
                    npz_bytes(series=series, coverage=coverage, task=task, nuisance=nuisance),
                )
                entry["member"] = member
            ledger.append(entry)
    atomic_write_json(
        attempt / "runs.json",
        {
            "subject": config["subject"],
            "runs": ledger,
            "preprocessing_sha256": hash_file(preproc / "status.json"),
            "source_derivative_sha256": source_hashes,
        },
    )
    return {
        "subject": config["subject"],
        "runs": len(runs),
        "included_runs": sum(not r["qc"]["excluded"] for r in ledger),
        "event_alignment_verified": True,
        "independent_noise_calibrated": False,
    }


def extracted(
    root: Path, source: Path, status: str
) -> tuple[list[dict[str, Any]], list[dict[str, np.ndarray]]]:
    """Read verified compact extraction artifacts; never execute or extract archive members."""
    directory = proof(root, status, phase="EXTRACT", source=source)
    rows = load_structured(directory / "runs.json")["runs"]
    records, arrays = [], []
    with zipfile.ZipFile(directory / "runs.zip") as archive:
        expected = {row["member"] for row in rows if not row["qc"]["excluded"]}
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise ValueError("packed neural run inventory mismatch")
        for row in rows:
            if row["qc"]["excluded"]:
                continue
            safe_relative_path(row["member"])
            with np.load(io.BytesIO(archive.read(row["member"])), allow_pickle=False) as values:
                arrays.append({k: values[k].copy() for k in values.files})
            records.append(row)
    return records, arrays


def calibrate_noise(
    root: Path, source: Path, config: dict[str, Any], attempt: Path
) -> dict[str, Any]:
    """Fit temporal AR and residual feature noise using only the two reserved participants."""
    prepared = proof(root, config["prepared"], phase="PREPARE")
    partition = load_structured(prepared / "partition.json")
    if set(config["extractions"]) != set(partition["calibration_subjects"]):
        raise ValueError("noise calibration must use exactly the reserved subjects")
    all_arrays, coverage = [], []
    for subject, status in config["extractions"].items():
        rows, arrays = extracted(root, source, status)
        if not rows or any(r["subject"] != subject for r in rows):
            raise ValueError("calibration extraction participant mismatch")
        all_arrays.extend(arrays)
        coverage.extend(a["coverage"] for a in arrays)
    plan = load_structured(source / "conf/masked_feature_plan.yaml")
    keep = np.min(coverage, axis=0) >= plan["minimum_parcel_coverage"]
    if keep.sum() < 3:
        raise ValueError("insufficient calibration parcel coverage")
    initial = [linear_summary(a["series"][:, keep], a["task"], a["nuisance"]) for a in all_arrays]
    rho = estimate_ar1([s["residual"] for s in initial])
    final = [linear_summary(a["series"], a["task"], a["nuisance"], rho) for a in all_arrays]
    # Scale residual rows for fitted degrees of freedom, independent of evaluation data.
    residuals = np.concatenate([s["residual"] * np.sqrt(s["rows"] / s["df"]) for s in final])
    with (attempt / "noise.npz").open("xb") as handle:
        np.savez_compressed(handle, residuals=residuals, coverage=np.min(coverage, axis=0))
    result = {
        "rho": rho,
        "calibration_ids": [f"masked_content_fmri:{s}" for s in sorted(config["extractions"])],
        "residual_rows": len(residuals),
        "source_units": "unscaled_fmriprep_intensity",
        "temporal_model": "pooled_AR1",
        "evaluation_neural_data_used": False,
    }
    atomic_write_json(attempt / "calibration.json", result)
    return result


def condition_design(
    rows: list[dict[str, Any]],
    posterior: dict[str, Any],
    image_ids: list[str],
    plan: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Map trial metadata to six condition designs using reserved-subject posterior draws only.

    Observed report defines a condition, not a truth label. E is external predicted
    report liability averaged within that condition; it is not a validated E measure.
    Exact-image frequency and fixed-unit nuisance kernels are shared by all models.
    """
    from factorcon.models.report_measurement import OrdinalPosterior, predict_reports

    payload = dict(posterior["posterior"])
    for name in ("beta", "subject_effects", "context_effects", "thresholds", "variances"):
        values = np.asarray(payload[name], dtype=float)
        flat = values.reshape((-1, *values.shape[2:]))
        indices = np.linspace(0, len(flat) - 1, plan["posterior_draws"], dtype=int)
        payload[name] = flat[indices][None]
    for name in ("subject_levels", "context_levels"):
        payload[name] = tuple(payload[name])
    model = OrdinalPosterior(**payload)
    trials = [
        (r, t)
        for r in rows
        for t in r["timing"]["trials"]
        if t["report"] >= 0 and t["trial"] not in r["qc"]["outside_scan_trials"]
    ]
    if not trials:
        raise ValueError("no observed condition metadata")
    x = np.asarray(
        [
            [1, (t["probe_frames"] or 0) / 10, t["nonliving"], int(t["probe_frames"] is None)]
            for _, t in trials
        ]
    )
    subjects = tuple(f"masked_content_fmri:{r['subject']}" for r, _ in trials)
    contexts = tuple(f"masked_content_fmri:{r['subject']}:{r['session']}" for r, _ in trials)
    predictive_seed = int.from_bytes(
        hashlib.sha256((str(plan["seed"]) + ":" + subjects[0]).encode()).digest()[:8], "big"
    )
    probabilities, _ = predict_reports(
        model, x, subjects=subjects, contexts=contexts, seed=predictive_seed
    )
    design = np.zeros((plan["posterior_draws"], 6, 3))
    sensory = np.zeros((6, len(image_ids) + 6))
    image_index = {name: i for i, name in enumerate(image_ids)}
    for condition in range(6):
        selected = [
            i for i, (_, t) in enumerate(trials) if t["nonliving"] * 3 + t["report"] == condition
        ]
        if not selected:
            raise ValueError("empty condition metadata; no invented design")
        design[:, condition, 0] = probabilities[:, selected].mean(axis=1)
        design[:, condition, 1] = np.mean([trials[i][1]["response"] == 2 for i in selected])
        design[:, condition, 2] = condition // 3
        for i in selected:
            trial = trials[i][1]
            sensory[condition, image_index[trial["stimulus_id"]]] += 1 / len(selected)
            correct = trial["correct"]
            correct_value = float(correct) if correct not in {"", "n/a", "nan"} else None
            if correct_value is not None and correct_value not in {0, 1}:
                raise ValueError("unknown accuracy coding")
            sensory[condition, -6:] += np.array(
                [
                    (trial["probe_frames"] or 0) / 10,
                    trial["probe_frames"] is None,
                    correct_value or 0,
                    correct_value is None,
                    trial["response"] is None,
                    1,
                ]
            ) / len(selected)
    return design, sensory


def build_bundle(root: Path, source: Path, config: dict[str, Any], attempt: Path) -> dict[str, Any]:
    """Assemble five held-out groups with independent noise/report draws; no model selection."""
    from factorcon.pipeline.neural_bundle import load_campaign

    plan = load_structured(source / "conf/masked_feature_plan.yaml")
    prepared = proof(root, config["prepared"], phase="PREPARE")
    partition = load_structured(prepared / "partition.json")
    if set(config["extractions"]) != set(partition["evaluation_subjects"]):
        raise ValueError("bundle must use exactly the evaluation cohort")
    noise_dir = proof(root, config["noise"], phase="NOISE", source=source)
    noise_record = load_structured(noise_dir / "calibration.json")
    reports = proof(root, config["reports"])
    posterior = load_structured(reports / "posterior.json")
    if set(posterior["calibration_ids"]) != set(noise_record["calibration_ids"]):
        raise ValueError("report/noise reserved cohort mismatch")
    collected = {
        subject: extracted(root, source, path)
        for subject, path in sorted(config["extractions"].items())
    }
    with np.load(noise_dir / "noise.npz", allow_pickle=False) as archive:
        residuals, coverage = archive["residuals"], archive["coverage"]
    all_coverage = [coverage, *[a["coverage"] for _, arrays in collected.values() for a in arrays]]
    keep = np.min(all_coverage, axis=0) >= plan["minimum_parcel_coverage"]
    if keep.sum() < 3:
        raise ValueError("insufficient campaign coverage; no outcome-selected replacement atlas")
    image_ids = sorted(
        {
            t["stimulus_id"]
            for rows, _ in collected.values()
            for r in rows
            for t in r["timing"]["trials"]
        }
    )
    patterns, noise, designs, sensory = [], [], [], []
    for subject, (rows, arrays) in collected.items():
        if not rows or any(r["subject"] != subject for r in rows):
            raise ValueError("evaluation participant identity mismatch")
        summaries = [
            linear_summary(a["series"][:, keep], a["task"], a["nuisance"], noise_record["rho"])
            for a in arrays
        ]
        p, n = combine_partitions(summaries, [r["partition"] for r in rows])
        d, s = condition_design(rows, posterior, image_ids, plan)
        patterns.append(p)
        noise.append(n)
        designs.append(d)
        sensory.append(s)
    features = np.asarray([f"Schaefer400:{i + 1:03d}" for i in np.flatnonzero(keep)])
    with (attempt / "bundle.npz").open("xb") as handle:
        np.savez_compressed(
            handle,
            patterns=np.asarray(patterns),
            noise=np.asarray(noise),
            design_draws=np.stack(designs, axis=1),
            sensory=np.asarray(sensory),
            names=np.asarray(["E", "R", "K_content"]),
            group_ids=np.asarray([f"masked_content_fmri:{s}" for s in collected]),
            calibration_ids=np.asarray(noise_record["calibration_ids"]),
            design_calibration_ids=np.asarray(posterior["calibration_ids"]),
            feature_ids=features,
            calibration_feature_ids=features,
            calibration_residuals=residuals[:, keep],
            condition_ids=np.asarray(plan["conditions"]),
            partition_ids=np.asarray(["alternating-0", "alternating-1"]),
        )

    def record(path: Path, role: str | None = None) -> dict[str, str]:
        value = {"path": path.relative_to(root).as_posix(), "sha256": hash_file(path)}
        return {**value, "role": role} if role else value

    mapping = {
        "status": "SUCCESS",
        "scientific_gate": None,
        "plan_sha256": hash_file(source / "conf/masked_feature_plan.yaml"),
        "retained_parcels": int(keep.sum()),
        "excluded_parcels": [int(i + 1) for i in np.flatnonzero(~keep)],
        "limitations": plan["limitations"],
        "universal_E_validated": False,
        "image_ids": image_ids,
    }
    atomic_write_json(attempt / "mapping.json", mapping)
    proofs = [record(root / path, "preprocessing") for path in config["extractions"].values()]
    proofs.extend(
        [
            record(noise_dir / "status.json", "noise_calibration"),
            record(reports / "status.json", "report_or_construct_calibration"),
            record(attempt / "mapping.json", "condition_mapping"),
        ]
    )
    manifest = {
        "schema_version": 1,
        "source_kind": "derived_neural_patterns",
        "family": "masked_content_fmri",
        "anchor_id": posterior["posterior"]["anchor_id"],
        "modality": "fmri",
        "source_units": "unscaled_fmriprep_intensity",
        "feature_definition": (
            "fixed_Schaefer400_parcel_means_geometry_coverage_0.8_"
            "no_smoothing_initial_cortical_lane"
        ),
        "noise_definition": (
            "participant_specific_run_design_GLS_AR1_and_feature_covariance_reserved_subjects_only"
        ),
        "condition_definition": "category_x_observed_ordinal_report_unknown_report_nuisance",
        "partition_definition": plan["partitions"],
        "independent_unit": "participant",
        "design_source": "external_calibration",
        "noise_source": "independent_calibration",
        "selection_basis": "design_and_technical_integrity_only",
        "provenance": proofs,
        "arrays": record(attempt / "bundle.npz"),
        "limitations": plan["limitations"],
    }
    atomic_write_json(attempt / "bundle.json", manifest)
    campaign = {
        "schema_version": 1,
        "scientific_gates": False,
        "bundles": [record(attempt / "bundle.json")],
    }
    atomic_write_json(attempt / "campaign.json", campaign)
    load_campaign(root, attempt / "campaign.json", ridge_fraction=0.1)
    return {
        "groups": len(collected),
        "conditions": 6,
        "partitions": 2,
        "features": int(keep.sum()),
        "campaign": str(attempt / "campaign.json"),
        "P08": "not_applicable_single_family",
        "scope": plan["scope"],
    }


def run(
    root: Path, source: Path, config: dict[str, Any], attempt: Path, *, dry_run: bool = False
) -> dict[str, Any]:
    """Atomic immutable stage lifecycle, failure provenance and fresh-attempt-only restart."""
    stage = config["stage"]
    plan = load_structured(source / "conf/masked_feature_plan.yaml")
    validate_feature_plan(plan)
    if stage not in {"AUX", "EXTRACT", "NOISE", "BUNDLE"}:
        raise ValueError("unknown masked lane stage")
    ensure_within(root / "analysis/masked-lane" / stage, attempt)
    if dry_run:
        proof(root, config["prepared"], phase="PREPARE")
        return {
            "dry_run": True,
            "phase": stage,
            "predecessors_may_be_pending": True,
            "outputs_created": False,
        }
    attempt.mkdir(parents=True, exist_ok=False)
    details = {
        "status": "RUNNING",
        "phase": stage,
        "source_release": str(source),
        "started_utc": utc_now(),
        "scientific_gate": None,
        "configuration": config,
        "plan_sha256": hash_file(source / "conf/masked_feature_plan.yaml"),
    }

    def state() -> None:
        for name in ("status.json", "provenance.json"):
            atomic_write_json(attempt / name, details)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    old = signal.signal(signal.SIGTERM, stop)
    state()
    try:
        ScratchQuotaGuard(attempt / "personal-quota.json")(0)
        if stage == "AUX":
            runs, _, raw = read_runs(root, config, source)
            result = acquire(attempt, runs, plan)
            source_record = load_structured(attempt / "source-record.json")
            audit = []
            with tarfile.open(attempt / "behavior.tar") as archive:
                for item in runs:
                    with gzip.open(
                        ensure_within(raw, raw / safe_relative_path(item["bold"])), "rb"
                    ) as stream:
                        header = stream.read(56)
                    endian = "<" if struct.unpack("<i", header[:4])[0] == 348 else ">"
                    if struct.unpack(endian + "i", header[:4])[0] != 348:
                        raise ValueError("expected source NIfTI-1 header")
                    dimensions = struct.unpack(endian + "8h", header[40:56])
                    path = behavior_path(item)
                    events = ensure_within(raw, raw / safe_relative_path(item["events"]))
                    if hash_file(events) != item["events_sha256"]:
                        raise ValueError("source events changed during timing audit")
                    value = align_run(
                        events.read_bytes(),
                        read_member(archive, path, source_record["behavior"][path]),
                        volumes=dimensions[4],
                        tr_seconds=item["repetition_time_seconds"],
                    )
                    audit.append(
                        {
                            "run_id": item["run_id"],
                            **{k: v for k, v in value.items() if k != "trials"},
                        }
                    )
            atomic_write_json(attempt / "timing-audit.json", {"runs": audit})
            result["aligned_runs"] = len(audit)
        elif stage == "EXTRACT":
            from masked_neural_phase import runtime

            prefix, env = runtime(root, load_structured(source / "conf/masked_neural_plan.yaml"))
            # Host retains quota/lifecycle handling; imaging child uses the qualified CVMFS runtime.
            atomic_write_json(attempt / "input.json", config)
            env["APPTAINERENV_PYTHONPATH"] = str(source / "src")
            env["APPTAINERENV_PYTHONDONTWRITEBYTECODE"] = "1"
            for key in ("SLURM_JOB_ID", "SLURM_CLUSTER_NAME"):
                env["APPTAINERENV_" + key] = os.environ[key]
            subprocess.run(
                [
                    *prefix,
                    "python",
                    str(source / "scripts/alliance/masked_lane_phase.py"),
                    "--root",
                    str(root),
                    "--input",
                    str(attempt / "input.json"),
                    "--input-sha256",
                    hash_file(attempt / "input.json"),
                    "--attempt",
                    str(attempt),
                    "--extract-child",
                ],
                env=env,
                check=True,
            )
            result = load_structured(attempt / "child-result.json")
        elif stage == "NOISE":
            result = calibrate_noise(root, source, config, attempt)
        else:
            result = build_bundle(root, source, config, attempt)
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
        signal.signal(signal.SIGTERM, old)


def main() -> int:
    """Verify personal host/root, committed source and immutable job input before execution."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--extract-child", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / p) != h for p, h in record["files"].items()
    ):
        raise ValueError("authorized immutable source required")
    ensure_within(root, args.input)
    if hash_file(args.input) != args.input_sha256:
        raise ValueError("submitted input bytes changed")
    config = load_structured(args.input)
    os.umask(0o077)
    if args.extract_child:
        if config["stage"] != "EXTRACT" or not os.environ.get("SLURM_JOB_ID", "").isdigit():
            raise ValueError("imaging child must run in a Slurm extraction allocation")
        ensure_within(root / "analysis/masked-lane/EXTRACT", args.attempt)
        atomic_write_json(
            args.attempt / "child-result.json", extract_subject(root, source, config, args.attempt)
        )
    else:
        if (
            config["stage"] != "AUX"
            and not args.dry_run
            and not os.environ.get("SLURM_JOB_ID", "").isdigit()
        ):
            raise ValueError("analysis requires a Slurm allocation")
        print(json.dumps(run(root, source, config, args.attempt, dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
