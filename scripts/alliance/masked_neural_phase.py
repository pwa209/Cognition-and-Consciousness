"""Real masked MRI preprocessing and independent report calibration on personal scratch."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from empirical_phase import check_predecessor

from factorcon.alliance import ScratchQuotaGuard, read_source_record, validate_fresh_root
from factorcon.config import load_project
from factorcon.pipeline.empirical import resolve_acquired_input
from factorcon.pipeline.masked_neural import (
    calibration_input,
    discover_runs,
    fmriprep_arguments,
    trial_census,
    validate_plan,
)
from factorcon.pipeline.measurement import fit_report_file, load_report_calibration
from factorcon.util import (
    atomic_write_json,
    ensure_within,
    hash_file,
    load_structured,
    read_jsonl,
    utc_now,
)


def preparation(root: Path, source: Path, path: Path) -> dict[str, Any]:
    """Verify private preparation output hashes and source identity; no fitting."""
    ensure_within(root / "analysis/masked-neural/PREPARE", path)
    state = load_structured(path)
    if (
        state.get("status") != "SUCCESS"
        or state.get("source_release") != str(source)
        or state.get("phase") != "PREPARE"
    ):
        raise ValueError("successful same-release preparation required")
    required = {"runs.json", "partition.json", "calibration-input.json", "result.json"}
    if not required <= state["outputs"].keys():
        raise ValueError("preparation artifacts missing")
    for name, digest in state["outputs"].items():
        if hash_file(ensure_within(path.parent, path.parent / name)) != digest:
            raise ValueError("preparation artifact changed")
    return state


def source_integrity(root: Path, source: Path, p03: Path, producer: Path) -> Any:
    """Reuse named full-SHA P03 evidence, checking current byte lengths and mtimes.

    This is a technical input check, not an outcome gate. Source files are never
    rewritten. Changed raw bytes require renewed P03 verification before analysis.
    """
    dataset = next(
        d
        for d in load_project(source / "conf/base.yaml").datasets
        if d.family == "masked_content_fmri"
    )
    inputs = resolve_acquired_input(root, dataset)
    check_predecessor(root, source, dataset.family, inputs.manifest_sha256, p03, producer)
    records = list(read_jsonl(p03.parent / "verified-files.jsonl"))
    if {r["relative_path"] for r in records} != {r.relative_path for r in inputs.records}:
        raise ValueError("P03 raw path inventory mismatch")
    for record in records:
        path = ensure_within(inputs.data_root, inputs.data_root / record["relative_path"])
        st = path.stat()
        if st.st_size != record["bytes"] or st.st_mtime_ns != record["mtime_ns"]:
            raise ValueError("raw source changed since full SHA verification")
    return inputs


def runtime(root: Path, plan: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """Build isolated container invocation; every mutable path uses study personal scratch.

    The installed, version-checked CVMFS image is read-only shared software, not
    shared data storage. Licence bytes are never returned or logged.
    """
    licence = root / "private/freesurfer/license.txt"
    if not licence.is_file() or licence.stat().st_mode & 0o077:
        raise ValueError("owner-only FreeSurfer licence required")
    record = load_structured(root / "operations/masked-runtime/ready.json")
    if (
        record.get("status") != "SUCCESS"
        or record.get("fmriprep_version") != plan["fmriprep_version"]
    ):
        raise ValueError("completed template/runtime preparation required")
    for name, digest in record["template_files"].items():
        if (
            hash_file(
                ensure_within(root / "cache/templateflow", root / "cache/templateflow" / name)
            )
            != digest
        ):
            raise ValueError("template bytes changed")
    directories = {
        "tmp": root / "tmp/fmriprep",
        "cache": root / "cache/apptainer",
        "home": root / "private/container-home",
        "xdg": root / "cache/fmriprep-xdg",
    }
    for path in directories.values():
        ensure_within(root, path).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        APPTAINER_CACHEDIR=str(directories["cache"]),
        APPTAINER_TMPDIR=str(directories["tmp"]),
        APPTAINERENV_TEMPLATEFLOW_HOME=str(root / "cache/templateflow"),
        APPTAINERENV_TMPDIR=str(directories["tmp"]),
        APPTAINERENV_XDG_CACHE_HOME=str(directories["xdg"]),
        APPTAINERENV_NIPYPE_NO_ET="1",
        APPTAINERENV_TEMPLATEFLOW_USE_DATALAD="0",
    )
    command = [
        "apptainer",
        "exec",
        "--cleanenv",
        "--home",
        str(directories["home"]),
        "--bind",
        f"{root}:{root},{directories['tmp']}:/tmp,{directories['tmp']}:/var/tmp",
        plan["fmriprep_image"],
    ]
    return command, env


def preprocess(
    root: Path,
    plan: dict[str, Any],
    raw: Path,
    attempt: Path,
    subject: str,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run actual fMRIPrep and require every subject/run output; no score-based exclusions."""
    prefix, env = runtime(root, plan)
    version = subprocess.check_output(
        [*prefix, "fmriprep", "--version"], env=env, text=True, timeout=180
    )
    if plan["fmriprep_version"] not in version:
        raise ValueError("container version mismatch")
    output, work = attempt / "derivatives", attempt / "work"
    command = prefix + fmriprep_arguments(
        bids=raw,
        output=output,
        work=work,
        license_file=root / "private/freesurfer/license.txt",
        subject=subject,
        plan=plan,
    )
    atomic_write_json(attempt / "command.json", {"argv": command, "version": version.strip()})
    with (attempt / "fmriprep.log").open("x") as stream:
        subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
    selected = [r for r in runs if r["subject"] == subject]
    outputs = {}
    for run in selected:
        folder = output / subject / run["session"] / "func"
        for pattern in (
            f"{run['run_id']}_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz",
            f"{run['run_id']}_space-T1w_desc-preproc_bold.nii.gz",
            f"{run['run_id']}_desc-confounds_timeseries.tsv",
        ):
            file = folder / pattern
            if not file.is_file() or file.stat().st_size == 0:
                raise ValueError("fMRIPrep successful exit but required run output missing")
    for file in sorted(output.rglob("*")):
        if file.is_file():
            ensure_within(attempt, file)
            outputs[file.relative_to(attempt).as_posix()] = hash_file(file)
    if not selected or not outputs:
        raise ValueError("empty preprocessing output")
    atomic_write_json(attempt / "derivative-hashes.json", outputs)
    return {
        "subject": subject,
        "runs": len(selected),
        "derivative_files": len(outputs),
        "neural_patterns_ready": False,
        "event_alignment_verified": False,
        "raw_preprocessing_executed": True,
    }


def run_phase(
    root: Path,
    source: Path,
    phase: str,
    attempt: Path,
    *,
    p03: Path,
    producer: Path,
    prepared: Path | None = None,
    subject_index: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute private immutable attempts; dry-run/failure/success/retry are distinct.

    All data units are trials or subject/run volumes. Calibration consumes only the
    ID-hash reserved cohort. Retries require a new attempt, preserving old failures.
    """
    if phase not in {"PREPARE", "CALIBRATE", "PREPROCESS"}:
        raise ValueError("unknown masked neural phase")
    ensure_within(root / "analysis/masked-neural" / phase, attempt)
    plan = load_structured(source / "conf/masked_neural_plan.yaml")
    validate_plan(plan)

    def inputs() -> tuple[Any, list[dict[str, Any]], dict[str, Any]]:
        acquired = source_integrity(root, source, p03, producer)
        if phase == "PREPARE":
            runs, partition = discover_runs(acquired.data_root, plan)
        else:
            if prepared is None:
                raise ValueError("preparation required")
            preparation(root, source, prepared)
            runs = load_structured(prepared.parent / "runs.json")["runs"]
            partition = load_structured(prepared.parent / "partition.json")
            if phase == "CALIBRATE":
                load_report_calibration(prepared.parent / "calibration-input.json")
            elif subject_index not in range(plan["expected_participants"]):
                raise ValueError("subject index outside configured range")
        return acquired, runs, partition

    if dry_run:
        _, runs, _ = inputs()
        return {"dry_run": True, "phase": phase, "runs": len(runs)}
    attempt.mkdir(parents=True, exist_ok=False)
    details: dict[str, Any] = {
        "phase": phase,
        "status": "RUNNING",
        "source_release": str(source),
        "started_utc": utc_now(),
        "scientific_gate": None,
        "independent_neural_noise_calibration": False,
        "configuration_sha256": {
            p: hash_file(source / "conf" / p)
            for p in (
                "masked_neural_plan.yaml",
                "analysis_spec.yaml",
                "construct_maps/masked_content_fmri.yaml",
            )
        },
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
        acquired, runs, partition = inputs()
        details.update(manifest_sha256=acquired.manifest_sha256, p03_sha256=hash_file(p03))
        if prepared is not None:
            details["preparation_sha256"] = hash_file(prepared)
        state()
        if phase == "PREPARE":
            result = trial_census(acquired.data_root, runs, plan)
            data = calibration_input(acquired.data_root, runs, partition, plan)
            atomic_write_json(attempt / "runs.json", {"runs": runs})
            atomic_write_json(attempt / "partition.json", partition)
            atomic_write_json(attempt / "calibration-input.json", data)
            load_report_calibration(attempt / "calibration-input.json")
            result.update(
                calibration_trials=len(data["reports"]), participants=plan["expected_participants"]
            )
        elif phase == "CALIBRATE":
            posterior = fit_report_file(
                prepared.parent / "calibration-input.json",
                attempt / "posterior.json",
                analysis_spec=source / "conf/analysis_spec.yaml",
                seed=plan["partition_seed"],
            )
            result = {
                "calibration_participants": len(posterior["calibration_ids"]),
                "diagnostic_flags": posterior["diagnostic_flags"],
                "universal_E_scale_validated": False,
                "independent_report_calibration": True,
                "neural_noise_calibration": False,
            }
        else:
            subject = sorted({r["subject"] for r in runs})[subject_index]
            details["subject"] = subject
            state()
            result = preprocess(root, plan, acquired.data_root, attempt, subject, runs)
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
    """Validate Rorqual ownership/release and dispatch a numeric Slurm attempt."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", choices=["PREPARE", "CALIBRATE", "PREPROCESS"], required=True)
    parser.add_argument("--p03", type=Path, required=True)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--subject-index", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if not record.get("analysis_execution_authorized") or any(
        hash_file(source / p) != h for p, h in record["files"].items()
    ):
        raise ValueError("authorized intact release required")
    job = os.environ.get("SLURM_ARRAY_JOB_ID", os.environ.get("SLURM_JOB_ID", ""))
    if not args.dry_run and not job.isdigit():
        raise ValueError("numeric Slurm job ID required")
    suffix = f"{job}-{args.subject_index}" if args.phase == "PREPROCESS" else job
    os.umask(0o077)
    print(
        json.dumps(
            run_phase(
                root,
                source,
                args.phase,
                root / "analysis/masked-neural" / args.phase / (suffix or "dry-run"),
                p03=args.p03,
                producer=args.producer,
                prepared=args.prepared,
                subject_index=args.subject_index,
                dry_run=args.dry_run,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
