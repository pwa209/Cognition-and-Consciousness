"""Qualify 13 BMVP report MRI runs and stage event-aligned BIDS on personal scratch.

This is P04/P05 preparation, not neural preprocessing, calibration or P08.
Original archives and conversion attempts remain immutable; BOLD files are
hard-linked, so staging adds no second multi-GB image copy.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import shutil
import signal
import struct
import tarfile
from pathlib import Path
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.pipeline.bmvp_report_prepare import (
    bounded_member,
    report_event_rows,
    select_report_members,
)
from factorcon.pipeline.bmvp_timing import dicom_time_seconds
from factorcon.util import atomic_write_json, hash_file, load_structured, read_jsonl, utc_now


EXPECTED = (("191", ("0006", "0007", "0008", "0009")),
            ("223", ("0006", "0007", "0008", "0009", "0010")),
            ("238", ("0006", "0007", "0008", "0009")))
EVENT_COLUMNS = (
    "onset", "duration", "trial_type", "source_row", "face_shown",
    "face_opacity_source", "report_availability", "perception_answer",
    "perception_keypress",
)


def validate_plan(plan: dict[str, Any]) -> None:
    """Require fixed participants/runs and honest measurement scope, not outcomes."""
    if (
        plan.get("schema_version") != 1 or plan.get("family") != "bmvp"
        or plan.get("scope") != "three_participant_report_mri_bids_preparation_not_p08"
        or plan.get("scientific_gates") is not False
        or plan.get("selection_basis") != "first_three_complete_report_mri_logs_and_720_trigger_runs_before_neural_outcomes"
        or plan.get("expected_volumes_per_run") != 720
        or plan.get("expected_trials_per_run") != 32
        or plan.get("tr_seconds") != 1.0
        or plan.get("event_duration_seconds") != 0.0
        or plan.get("cross_family_e_scale_validated") is not False
        or plan.get("cross_family_feature_units_validated") is not False
        or plan.get("calibration_status") != "not_established"
        or plan.get("event_duration_interpretation") != "onset_impulse_only_source_duration_not_verified"
        or plan.get("fmriprep") != {
            "version": "25.1.3",
            "image": "/cvmfs/containers.computecanada.ca/content/containers/fmriprep-25.1.1",
            "nprocs": 8, "omp_nthreads": 4, "memory_mb": 56000,
            "output_spaces": ["MNI152NLin2009cAsym:res-2", "T1w"],
            "skull_strip_template": "OASIS30ANTs",
            "reconstruction": False, "spatial_smoothing": False,
        }
        or len(plan.get("participants", [])) != len(EXPECTED)
    ):
        raise ValueError("unsupported BMVP report preparation plan")
    for value, (participant, series) in zip(plan["participants"], EXPECTED, strict=True):
        if value.get("id") != participant or tuple(value.get("series", [])) != series:
            raise ValueError("BMVP cohort/series selection changed")
        jobs = value.get("conversion_jobs", [])
        if len(jobs) != len(series) or any(not re.fullmatch(r"\d+", str(j)) for j in jobs):
            raise ValueError("BMVP conversion job references invalid")


def structural_shape(path: Path) -> tuple[int, int, int]:
    """Check a T1w NIfTI-1 header's 3D voxel shape; no image data are fitted."""
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rb") as stream:
        header = stream.read(348)
    if len(header) != 348:
        raise ValueError("T1w NIfTI header truncated")
    little, big = struct.unpack("<i", header[:4])[0], struct.unpack(">i", header[:4])[0]
    endian = "<" if little == 348 else ">" if big == 348 else ""
    if not endian:
        raise ValueError("T1w NIfTI-1 header invalid")
    dim = struct.unpack(endian + "8h", header[40:56])
    if dim[0] != 3 or any(v < 16 for v in dim[1:4]):
        raise ValueError("defaced T1w is not a plausible 3D image")
    return tuple(int(v) for v in dim[1:4])


def write_events(path: Path, rows: tuple[dict[str, Any], ...]) -> None:
    """Write scanner-relative second onsets; report missingness stays explicit."""
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVENT_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def conversion_inputs(root: Path, item: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Rehash every converted BOLD/sidecar against immutable SUCCESS receipts."""
    found = []
    for suffix, job in zip(item["series"], item["conversion_jobs"], strict=True):
        series = f"{item['id']}_RP_MRI_{suffix}"
        base = root / "operations/bmvp-mri-pilot" / str(job)
        status_path = base / "status.json"
        state = load_structured(status_path)
        if (
            state.get("status") != "SUCCESS" or state.get("job") != job
            or state.get("series") != series
            or state.get("archive") != f"report/{item['id']}_RP_MRI.tar"
            or state.get("nifti_shape") != [110, 110, 64, 720]
            or state.get("repetition_time_seconds") != 1.0
        ):
            raise ValueError(f"conversion identity/geometry mismatch: {series}")
        expected = {"converted/bmvp-pilot.nii.gz", "converted/bmvp-pilot.json"}
        if set(state.get("outputs", {})) != expected:
            raise ValueError(f"conversion outputs incomplete: {series}")
        for name in sorted(expected):
            path = base / name
            if not path.is_file() or path.is_symlink() or hash_file(path) != state["outputs"][name]:
                raise ValueError(f"conversion output hash mismatch: {series}/{name}")
        metadata = load_structured(base / "converted/bmvp-pilot.json")
        acquisition_seconds = dicom_time_seconds(str(metadata["AcquisitionTime"]))
        found.append({
            "series": series, "job": job, "image": base / "converted/bmvp-pilot.nii.gz",
            "status": status_path, "image_sha256": state["outputs"]["converted/bmvp-pilot.nii.gz"],
            "archive_sha256": state["archive_sha256"],
            "acquisition_seconds": acquisition_seconds,
        })
    return tuple(found)


def prepare(root: Path, source: Path, *, job: str, dry_run: bool = False) -> dict[str, Any]:
    """Stage a fixed BMVP report-only BIDS cohort with restart-safe Slurm receipts.

    All event timing is derived from each subject's log/CSV, in scanner seconds.
    No neural outcomes or evaluation labels influence selection or calibration.
    Retry uses a new job ID; partial failures are retained for diagnosis.
    """
    root = validate_fresh_root(root)
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / name) != digest for name, digest in record["files"].items()
    ):
        raise ValueError("authorized intact Rorqual source required")
    config_path = source / "conf/bmvp_report_preprocess.yaml"
    plan = load_structured(config_path)
    validate_plan(plan)
    if dry_run:
        return {"dry_run": True, "participants": 3, "runs": 13, "scope": plan["scope"]}
    if not job.isdigit() or os.environ.get("SLURM_JOB_ID") != job:
        raise ValueError("matching Slurm compute job required")
    p03 = root / "analysis/P03/bmvp/21409966/status.json"
    predecessor = load_structured(p03)
    if predecessor.get("status") != "SUCCESS" or predecessor.get("family") != "bmvp":
        raise ValueError("successful BMVP P03 predecessor required")
    ledger = {row["relative_path"]: row for row in read_jsonl(p03.parent / "verified-files.jsonl")}
    attempt = root / "analysis/bmvp-report/PREPARE" / job
    attempt.mkdir(parents=True, exist_ok=False, mode=0o700)
    state: dict[str, Any] = {
        "status": "RUNNING", "phase": "BMVP_REPORT_PREPARE", "job": job,
        "scope": plan["scope"], "source_release": str(source),
        "started_utc": utc_now(), "scientific_gate": None,
        "configuration_sha256": hash_file(config_path), "p03_sha256": hash_file(p03),
        "cross_family_e_scale_validated": False,
        "neural_preprocessing_validated": False,
    }

    def save() -> None:
        atomic_write_json(attempt / "status.json", state)
        atomic_write_json(attempt / "provenance.json", state)

    def interrupted(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    save()
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        bids = attempt / "bids"
        bids.mkdir(mode=0o700)
        atomic_write_json(bids / "dataset_description.json", {
            "Name": "BMVP fixed report-MRI technical preparation",
            "BIDSVersion": "1.9.0", "DatasetType": "raw",
            "GeneratedBy": [{"Name": "factorcon", "Version": source.parent.name}],
        })
        outputs: dict[str, str] = {
            "bids/dataset_description.json": hash_file(bids / "dataset_description.json")
        }
        run_rows = []
        for item in plan["participants"]:
            participant = item["id"]
            relative = f"archives/report/{participant}_RP_MRI.tar"
            archive = root / "data/raw/bmvp/website_inventory_2026-08-30" / relative
            evidence = ledger.get(relative)
            if not evidence or not archive.is_file() or archive.is_symlink():
                raise ValueError(f"verified raw archive absent: {relative}")
            stat = archive.stat()
            if stat.st_size != evidence["bytes"] or stat.st_mtime_ns != evidence["mtime_ns"]:
                raise ValueError(f"raw archive changed since P03: {relative}")
            converted = conversion_inputs(root, item)
            if {c["archive_sha256"] for c in converted} != {evidence["sha256"]}:
                raise ValueError(f"conversion/P03 archive hashes differ: {relative}")
            with tarfile.open(archive, "r:") as handle:
                members = select_report_members(handle, participant)
                log = bounded_member(handle, members["log"], 1_000_000)
                csv_payload = bounded_member(handle, members["csv"], 2_000_000)
                timing, events = report_event_rows(
                    log, csv_payload, expected_runs=len(converted),
                    volumes=plan["expected_volumes_per_run"],
                    tr_seconds=plan["tr_seconds"],
                    trials_per_run=plan["expected_trials_per_run"],
                )
                scan = [value["acquisition_seconds"] for value in converted]
                trigger = [value.first_trigger_seconds for value in timing]
                residuals = [
                    (right_scan - left_scan) - (right_trigger - left_trigger)
                    for left_scan, right_scan, left_trigger, right_trigger
                    in zip(scan, scan[1:], trigger, trigger[1:])
                ]
                if any(abs(value) > 0.5 for value in residuals):
                    raise ValueError("DICOM and trigger inter-run intervals differ by >0.5 s")
                subject = bids / f"sub-{participant}"
                anat = subject / "anat"
                func = subject / "func"
                anat.mkdir(parents=True, mode=0o700)
                func.mkdir(mode=0o700)
                member = members["anat"]
                extension = ".nii.gz" if member.name.endswith(".nii.gz") else ".nii"
                structural = anat / f"sub-{participant}_T1w{extension}"
                stream = handle.extractfile(member)
                if stream is None or member.size > 100_000_000:
                    raise ValueError("defaced T1w missing or unexpectedly large")
                with stream, structural.open("xb") as destination:
                    shutil.copyfileobj(stream, destination, length=8 << 20)
                if structural.stat().st_size != member.size:
                    raise ValueError("defaced T1w extraction length mismatch")
                shape = structural_shape(structural)
                outputs[structural.relative_to(attempt).as_posix()] = hash_file(structural)
            for index, (run, image, trial_rows) in enumerate(zip(timing, converted, events, strict=True), start=1):
                stem = f"sub-{participant}_task-bmvpReport_run-{index:02d}"
                bold = func / f"{stem}_bold.nii.gz"
                os.link(image["image"], bold)
                sidecar = func / f"{stem}_bold.json"
                atomic_write_json(sidecar, {
                    "TaskName": "bmvpReport", "RepetitionTime": plan["tr_seconds"],
                    "SourceDICOMSeries": image["series"],
                    "EventTimeOrigin": "first_scanner_trigger",
                    "EventDurationInterpretation": plan["event_duration_interpretation"],
                })
                event_file = func / f"{stem}_events.tsv"
                write_events(event_file, trial_rows)
                for path in (sidecar, event_file):
                    outputs[path.relative_to(attempt).as_posix()] = hash_file(path)
                run_rows.append({
                    "participant": participant, "run": index, "series": image["series"],
                    "conversion_job": image["job"], "conversion_status_sha256": hash_file(image["status"]),
                    "bold_sha256": image["image_sha256"], "structural_shape": shape,
                    "first_trigger_seconds": run.first_trigger_seconds,
                    "first_trial_onset_seconds": run.first_trial_onset_seconds,
                    "trials": len(trial_rows),
                    "interrun_scan_minus_trigger_seconds": residuals[index - 2] if index > 1 else None,
                })
        if len(run_rows) != 13 or len(outputs) != 1 + 3 + 13 * 2:
            raise ValueError("fixed BMVP BIDS output count mismatch")
        atomic_write_json(attempt / "runs.json", {"runs": run_rows})
        outputs["runs.json"] = hash_file(attempt / "runs.json")
        state.update(
            status="SUCCESS", ended_utc=utc_now(), participants=3, runs=13,
            task_trials=13 * 32, outputs=outputs,
            bold_links={row["series"]: row["bold_sha256"] for row in run_rows},
            event_alignment_verified=True, neural_preprocessing_validated=False,
            independent_cross_family_calibration=False, p08_ready=False,
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
    """Execute a compute-node BMVP technical preparation or side-effect-free dry run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = prepare(args.root, Path(__file__).resolve().parents[2], job=args.job, dry_run=args.dry_run)
    print(json.dumps({k: result[k] for k in ("status", "participants", "runs")}) if not args.dry_run else json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
