"""Run fMRIPrep for one fixed BMVP report participant, archiving only work files.

This does not infer E or establish a cross-family transfer scale. Fitted neural
features and independent calibration are separate, later outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured, utc_now
from factorcon.work_archive import pack, retire

from scripts.alliance.bmvp_report_prepare import validate_plan


def command_for_subject(
    root: Path, plan: dict[str, Any], bids: Path, output: Path, work: Path, participant: str
) -> tuple[list[str], dict[str, str]]:
    """Build subject-only fMRIPrep command; time/space units follow fixed plan.

    Container caches, home and temporary files remain in personal scratch.
    No evaluation reports or neural outcomes enter the runtime settings.
    """
    validate_plan(plan)
    if participant not in {"191", "223", "238"}:
        raise ValueError("participant outside fixed BMVP report cohort")
    settings = plan["fmriprep"]
    licence = root / "private/freesurfer/license.txt"
    if not licence.is_file() or licence.stat().st_mode & 0o077:
        raise ValueError("owner-only FreeSurfer licence required")
    ready = load_structured(root / "operations/masked-runtime/ready.json")
    if ready.get("status") != "SUCCESS" or ready.get("fmriprep_version") != settings["version"]:
        raise ValueError("fMRIPrep runtime/templates not qualified")
    for relative, digest in ready["template_files"].items():
        cache = root / "cache/templateflow"
        if hash_file(ensure_within(cache, cache / relative)) != digest:
            raise ValueError("qualified TemplateFlow bytes changed")
    directories = {
        "tmp": root / "tmp/fmriprep", "cache": root / "cache/apptainer",
        "home": root / "private/container-home", "xdg": root / "cache/fmriprep-xdg",
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "APPTAINER_CACHEDIR": str(directories["cache"]),
        "APPTAINER_TMPDIR": str(directories["tmp"]),
        "APPTAINERENV_TEMPLATEFLOW_HOME": str(root / "cache/templateflow"),
        "APPTAINERENV_TMPDIR": str(directories["tmp"]),
        "APPTAINERENV_XDG_CACHE_HOME": str(directories["xdg"]),
        "APPTAINERENV_NIPYPE_NO_ET": "1",
        "APPTAINERENV_TEMPLATEFLOW_USE_DATALAD": "0",
    })
    prefix = [
        "apptainer", "exec", "--cleanenv", "--home", str(directories["home"]),
        "--bind", f"{root}:{root},{directories['tmp']}:/tmp,{directories['tmp']}:/var/tmp",
        settings["image"],
    ]
    arguments = [
        "fmriprep", str(bids), str(output), "participant", "--participant-label", participant,
        "--fs-license-file", str(licence), "--fs-no-reconall", "--notrack",
        "--nprocs", str(settings["nprocs"]),
        "--omp-nthreads", str(settings["omp_nthreads"]),
        "--mem", str(settings["memory_mb"]),
        "--output-spaces", *settings["output_spaces"],
        "--skull-strip-template", settings["skull_strip_template"],
        "--skull-strip-fixed-seed", "--random-seed", "260830", "--stop-on-first-crash",
        "-w", str(work),
    ]
    return prefix + arguments, env


def preprocessed_files(output: Path, participant: str, run_count: int) -> dict[str, str]:
    """Require all fixed run outputs and hash derivatives; no score-based selection."""
    func = output / f"sub-{participant}" / "func"
    for index in range(1, run_count + 1):
        stem = f"sub-{participant}_task-bmvpReport_run-{index:02d}"
        for suffix in (
            "_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz",
            "_space-T1w_desc-preproc_bold.nii.gz",
            "_desc-confounds_timeseries.tsv",
        ):
            path = func / f"{stem}{suffix}"
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"required BMVP fMRIPrep derivative missing: {path.name}")
    outputs = {
        path.relative_to(output).as_posix(): hash_file(path)
        for path in sorted(output.rglob("*")) if path.is_file()
    }
    if not outputs:
        raise ValueError("fMRIPrep emitted no files")
    return outputs


def preprocess(
    root: Path, source: Path, *, prepared_job: str, participant: str, job: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Process one participant's 4/5 report runs on a Slurm node.

    Success means fMRIPrep derivatives were checked and work files were packed,
    byte-verified and retired to control file count. It does not mean P06/P08
    features, noise calibration or common E/R measurement are ready.
    """
    root = validate_fresh_root(root)
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("authorized intact Rorqual source required")
    plan = load_structured(source / "conf/bmvp_report_preprocess.yaml")
    validate_plan(plan)
    if participant not in {"191", "223", "238"} or not prepared_job.isdigit():
        raise ValueError("fixed participant and numeric preparation job required")
    prepared_path = root / "analysis/bmvp-report/PREPARE" / prepared_job / "status.json"
    if dry_run:
        return {"dry_run": True, "participant": participant,
                "prepared_ready": prepared_path.is_file(), "scope": "raw_fmriprep_only"}
    if not job.isdigit() or os.environ.get("SLURM_JOB_ID") != job:
        raise ValueError("matching Slurm compute job required")
    prepared = load_structured(prepared_path)
    if (
        prepared.get("status") != "SUCCESS" or prepared.get("runs") != 13
        or prepared.get("source_release") != str(source)
    ):
        raise ValueError("successful 13-run preparation required")
    for name, digest in prepared["outputs"].items():
        path = prepared_path.parent / name
        if not path.is_file() or hash_file(path) != digest:
            raise ValueError("prepared event/T1w artifact changed")
    for series, digest in prepared["bold_links"].items():
        subject_id, suffix = series.split("_RP_MRI_")
        if subject_id != participant:
            continue
        item = next(x for x in plan["participants"] if x["id"] == subject_id)
        run = item["series"].index(suffix) + 1
        image = prepared_path.parent / "bids" / f"sub-{subject_id}" / "func" / (
            f"sub-{subject_id}_task-bmvpReport_run-{run:02d}_bold.nii.gz"
        )
        if not image.is_file() or hash_file(image) != digest:
            raise ValueError(f"prepared BOLD link changed: {series}")
    run_count = len(next(x["series"] for x in plan["participants"] if x["id"] == participant))
    bids = prepared_path.parent / "bids"
    attempt = root / "analysis/bmvp-report/PREPROCESS" / f"{job}-{participant}"
    attempt.mkdir(parents=True, exist_ok=False, mode=0o700)
    state: dict[str, Any] = {
        "status": "RUNNING", "phase": "BMVP_REPORT_PREPROCESS", "job": job,
        "participant": participant, "source_release": str(source),
        "prepared_status_sha256": hash_file(prepared_path),
        "configuration_sha256": hash_file(source / "conf/bmvp_report_preprocess.yaml"),
        "started_utc": utc_now(), "scientific_gate": None,
        "cross_family_e_scale_validated": False,
    }

    def save() -> None:
        atomic_write_json(attempt / "status.json", state)
        atomic_write_json(attempt / "provenance.json", state)

    def interrupted(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    save()
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        command, env = command_for_subject(
            root, plan, bids, attempt / "derivatives", attempt / "work", participant
        )
        prefix = command[:8]
        version = subprocess.check_output(prefix + ["fmriprep", "--version"],
                                          env=env, text=True, timeout=180).strip()
        if plan["fmriprep"]["version"] not in version:
            raise ValueError("fMRIPrep container version mismatch")
        atomic_write_json(attempt / "command.json", {"argv": command, "version": version})
        with (attempt / "fmriprep.log").open("x") as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        derivatives = preprocessed_files(attempt / "derivatives", participant, run_count)
        atomic_write_json(attempt / "derivative-hashes.json", derivatives)
        state.update(raw_preprocessing_complete=True, derivative_files=len(derivatives))
        save()
        work = attempt / "work"
        destination = root / "archives/bmvp-work" / attempt.name
        archive = pack(root, work, destination, category="bmvp-work")
        if archive["status"] != "VERIFIED":
            raise ValueError("BMVP work archive verification failed")
        retired = retire(root, work, destination, category="bmvp-work")
        if retired["status"] != "RETIRED":
            raise ValueError("BMVP work was not safely retired")
        state.update(
            status="SUCCESS", ended_utc=utc_now(), runs=run_count,
            outputs={"derivative-hashes.json": hash_file(attempt / "derivative-hashes.json"),
                     "command.json": hash_file(attempt / "command.json")},
            archived_work_status_sha256=hash_file(destination / "status.json"),
            raw_preprocessing_complete=True,
            independent_neural_noise_calibration=False,
            independent_cross_family_calibration=False,
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
    """Execute one scheduled participant or dry-run configuration checks."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prepared-job", required=True)
    parser.add_argument("--participant", required=True)
    parser.add_argument("--job", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = preprocess(
        args.root, Path(__file__).resolve().parents[2],
        prepared_job=args.prepared_job, participant=args.participant,
        job=args.job, dry_run=args.dry_run,
    )
    print(json.dumps({"status": result.get("status"), "participant": args.participant,
                      "runs": result.get("runs"), "dry_run": args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
