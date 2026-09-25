"""Versioned, compute-node-only report-MRI trigger/event alignment pilot."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import tarfile
from pathlib import Path
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.pipeline.bmvp_timing import align_report_mri_timing
from factorcon.pipeline.empirical import safe_tar_members
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def dicom_time_seconds(value: str) -> float:
    """Parse a dcm2niix AcquisitionTime into seconds after midnight; no neural data."""
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError("invalid colon DICOM time")
        hour, minute, second = int(parts[0]), int(parts[1]), float(parts[2])
    else:
        head, dot, frac = value.partition(".")
        head = head.zfill(6)
        if len(head) != 6:
            raise ValueError("invalid compact DICOM time")
        hour = int(head[:2])
        minute = int(head[2:4])
        second = float(head[4:] + (dot + frac if dot else ""))
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError("DICOM time outside clock range")
    return 3600 * hour + 60 * minute + second


def run_pilot(root: Path, *, job: str) -> dict[str, Any]:
    """Validate one report exemplar, seconds relative to 4 scanner runs.

    Leakage boundary: behavior/log timing and DICOM metadata only; BOLD voxels,
    E labels, participant-level calibration and any scientific scores are unused.
    Original TARs remain packed; only small metadata/receipts are written.
    """
    root = validate_fresh_root(root)
    if not re.fullmatch(r"\d+", job) or os.environ.get("SLURM_JOB_ID") != job:
        raise ValueError("matching compute-node Slurm job ID required")
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if any(hash_file(source / name) != digest for name, digest in record["files"].items()):
        raise ValueError("immutable source release changed")
    attempt = root / "operations/bmvp-timing-pilot" / job
    attempt.mkdir(parents=True, exist_ok=False, mode=0o700)
    state: dict[str, Any] = {
        "status": "RUNNING",
        "scope": "report exemplar clock alignment only; not P04/P06/P08 completion",
        "job": job,
        "source_release": str(source),
        "started_utc": utc_now(),
        "scientific_gate": None,
    }
    for name in ("status.json", "provenance.json"):
        atomic_write_json(attempt / name, state)
    try:
        p03 = load_structured(root / "analysis/P03/bmvp/21409966/status.json")
        if p03.get("status") != "SUCCESS" or p03.get("family") != "bmvp":
            raise ValueError("BMVP P03 inventory not verified")
        archive = root / "data/raw/bmvp/website_inventory_2026-08-30/archives/report/191_RP_MRI.tar"
        if not archive.is_file() or archive.is_symlink():
            raise ValueError("fixed report exemplar archive missing/redirected")
        with tarfile.open(archive, "r:") as handle:
            members = safe_tar_members(handle)
            csv_members = [m for m in members if m.isfile() and m.name.lower().endswith(".csv")]
            log_members = [m for m in members if m.isfile() and m.name.lower().endswith(".log")]
            if len(csv_members) != 1 or len(log_members) != 1:
                raise ValueError("expected exactly one trial CSV and one PsychoPy log")
            payloads: list[bytes] = []
            for member, limit in ((log_members[0], 1_000_000), (csv_members[0], 2_000_000)):
                if member.size > limit:
                    raise ValueError("timing member exceeds byte limit")
                stream = handle.extractfile(member)
                if stream is None:
                    raise ValueError("timing member is not regular")
                payload = stream.read(limit + 1)
                if len(payload) != member.size:
                    raise ValueError("timing member size mismatch")
                payloads.append(payload)
        alignments = align_report_mri_timing(payloads[0], payloads[1])
        expected_series = [f"191_RP_MRI_000{i}" for i in range(6, 10)]
        conversions: dict[str, tuple[str, float]] = {}
        for status_path in (root / "operations/bmvp-mri-pilot").glob("*/status.json"):
            converted = load_structured(status_path)
            series = converted.get("series")
            if series not in expected_series:
                continue
            if series in conversions or converted.get("status") != "SUCCESS":
                raise ValueError("duplicate or unsuccessful fixed DICOM conversion")
            if converted.get("nifti_shape", [None] * 4)[3] != 720:
                raise ValueError("converted image volume count disagrees with triggers")
            if abs(float(converted.get("repetition_time_seconds", 0)) - 1.0) > 0.001:
                raise ValueError("converted image TR disagrees with triggers")
            metadata = status_path.parent / "converted/bmvp-pilot.json"
            if hash_file(metadata) != converted.get("outputs", {}).get("converted/bmvp-pilot.json"):
                raise ValueError("converted DICOM metadata hash mismatch")
            info = load_structured(metadata)
            conversions[series] = (converted["job"], dicom_time_seconds(str(info["AcquisitionTime"])))
        if set(conversions) != set(expected_series):
            raise ValueError("four fixed report DICOM conversions are required")
        scan = [conversions[series][1] for series in expected_series]
        trigger = [entry.first_trigger_seconds for entry in alignments]
        residuals = [(b - a) - (d - c) for a, b, c, d in zip(scan, scan[1:], trigger, trigger[1:])]
        if any(abs(value) > 0.5 for value in residuals):
            raise ValueError("DICOM-run and trigger-train intervals disagree by over 0.5 s")
        state.update(
            status="SUCCESS",
            archive_sha256=hash_file(archive),
            log_sha256=hashlib.sha256(payloads[0]).hexdigest(),
            csv_sha256=hashlib.sha256(payloads[1]).hexdigest(),
            converted_jobs={series: conversions[series][0] for series in expected_series},
            runs=[
                {
                    "block": entry.block,
                    "series": expected_series[entry.block - 1],
                    "first_trigger_seconds": entry.first_trigger_seconds,
                    "first_trial_onset_seconds": entry.first_trial_onset_seconds,
                    "task_trials": entry.task_trials,
                    "trigger_count": entry.trigger_count,
                    "median_trigger_interval_seconds": entry.median_trigger_interval_seconds,
                    "max_trigger_interval_seconds": entry.max_trigger_interval_seconds,
                }
                for entry in alignments
            ],
            interrun_scan_minus_trigger_seconds=residuals,
            timing_validated_for_fixed_exemplar=True,
            neural_preprocessing_validated=False,
            cross_family_anchor_validated=False,
        )
    except BaseException as exc:
        state.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        state["ended_utc"] = utc_now()
        for name in ("status.json", "provenance.json"):
            atomic_write_json(attempt / name, state)
    return state


def main() -> int:
    """Execute the fixed pilot under a Slurm allocation on personal scratch."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    state = run_pilot(args.root, job=args.job)
    print("BMVP_TIMING_PILOT", state["status"], len(state["runs"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
