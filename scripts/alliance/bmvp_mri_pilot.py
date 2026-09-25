"""Bounded BMVP DICOM-to-NIfTI pilot on Rorqual compute nodes.

This is imaging preparation, not P04 event alignment, P06 calibration, or P08.
Original TAR archives remain unchanged and DICOM extraction is temporary within
the owner's personal scratch. The released script never executes archive files.
"""

from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.pipeline.empirical import safe_tar_members
from factorcon.util import atomic_write_json, hash_file, load_structured, safe_relative_path, utc_now


def select_dicom_members(
    members: list[tarfile.TarInfo], *, series: str, expected_count: int
) -> list[tarfile.TarInfo]:
    """Select exactly one DICOM series by filename; count is files, no patient inference.

    Call only after ``safe_tar_members`` has validated all TAR paths and types.
    No neural outcomes or behavior are examined, and no series is chosen by score.
    """
    if not re.fullmatch(r"[A-Za-z0-9_]+", series) or expected_count < 1:
        raise ValueError("invalid series identity/count")
    pattern = re.compile(rf"^{re.escape(series)}-\d{{4}}-\d{{5}}\.dcm$", re.I)
    selected = [
        member
        for member in members
        if member.isfile() and pattern.fullmatch(Path(member.name).name)
    ]
    if len(selected) != expected_count or len({Path(m.name).name for m in selected}) != len(selected):
        raise ValueError("DICOM series file count or basename identity mismatch")
    return sorted(selected, key=lambda member: member.name)


def nifti_shape_and_tr(path: Path) -> tuple[tuple[int, ...], float]:
    """Read NIfTI-1 dimensions and TR (seconds) without loading voxel data.

    This checks conversion geometry only; it cannot validate scan/event alignment
    or the scientific meaning of a volume. No scaling or fitting occurs here.
    """
    opener = gzip.open if path.name.lower().endswith(".gz") else open
    with opener(path, "rb") as stream:
        header = stream.read(348)
    if len(header) != 348:
        raise ValueError("truncated NIfTI header")
    endian = "<" if struct.unpack("<i", header[:4])[0] == 348 else ">"
    if struct.unpack(endian + "i", header[:4])[0] != 348:
        raise ValueError("unsupported NIfTI header")
    dim = struct.unpack(endian + "8h", header[40:56])
    pixdim = struct.unpack(endian + "8f", header[76:108])
    if dim[0] != 4 or any(n < 1 for n in dim[1:5]):
        raise ValueError("converted image is not a 4D time series")
    time_unit = header[123] & 0x38
    if time_unit != 8 or pixdim[4] <= 0:
        raise ValueError("NIfTI repetition time must be positive seconds")
    return tuple(int(x) for x in dim[1:5]), float(pixdim[4])


def run_pilot(
    root: Path, *, archive_relative: str, series: str, expected_count: int, job: str
) -> dict[str, Any]:
    """Convert one fixed BMVP DICOM series on personal scratch, with atomic receipts.

    Input is an immutable public TAR archive; output is one participant's
    conversion-only NIfTI/JSON in a unique Slurm attempt. Leakage boundary:
    no behavior, calibration subjects, or neural scores are consulted. DICOM
    intermediates are deleted when the attempt ends; originals are preserved.
    """
    root = validate_fresh_root(root)
    if not re.fullmatch(r"\d+", job) or os.environ.get("SLURM_JOB_ID") != job:
        raise ValueError("matching compute-node Slurm job ID required")
    relative = safe_relative_path(archive_relative)
    if len(relative.parts) != 2 or relative.parts[0] not in {"report", "no_report"}:
        raise ValueError("expected report/no_report archive path")
    if not relative.name.endswith(("RP_MRI.tar", "NRP.tar")):
        raise ValueError("expected MRI-containing BMVP TAR")
    archive = root / "data/raw/bmvp/website_inventory_2026-08-30/archives" / relative
    if not archive.is_file() or archive.is_symlink():
        raise ValueError("original BMVP TAR missing or redirected")
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if any(hash_file(source / name) != digest for name, digest in record["files"].items()):
        raise ValueError("immutable source release changed")
    p03 = load_structured(root / "analysis/P03/bmvp/21409966/status.json")
    if p03.get("status") != "SUCCESS" or p03.get("family") != "bmvp":
        raise ValueError("BMVP P03 byte/schema inventory has not succeeded")
    converter = shutil.which("dcm2niix")
    if not converter or not converter.startswith("/cvmfs/soft.computecanada.ca/"):
        raise ValueError("trusted Alliance dcm2niix module required")
    attempt = root / "operations/bmvp-mri-pilot" / job
    attempt.mkdir(parents=True, exist_ok=False, mode=0o700)
    state: dict[str, Any] = {
        "status": "RUNNING",
        "scope": "one-series DICOM conversion pilot; not event alignment or P08",
        "source_release": str(source),
        "archive": archive_relative,
        "series": series,
        "expected_dicom_files": expected_count,
        "job": job,
        "started_utc": utc_now(),
        "scientific_gate": None,
    }
    for name in ("status.json", "provenance.json"):
        atomic_write_json(attempt / name, state)
    try:
        state["archive_sha256"] = hash_file(archive)
        with tarfile.open(archive, "r:*") as tar:
            members = select_dicom_members(
                safe_tar_members(tar), series=series, expected_count=expected_count
            )
            with tempfile.TemporaryDirectory(prefix="dicom-", dir=attempt) as temporary:
                dicom = Path(temporary)
                for member in members:
                    stream = tar.extractfile(member)
                    if stream is None:
                        raise ValueError("DICOM member is not regular")
                    with stream, (dicom / Path(member.name).name).open("xb") as destination:
                        shutil.copyfileobj(stream, destination, length=8 << 20)
                output = attempt / "converted"
                output.mkdir(mode=0o700)
                completed = subprocess.run(
                    [converter, "-z", "y", "-b", "y", "-f", "bmvp-pilot", "-o", str(output), str(dicom)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1800,
                )
                if completed.returncode:
                    raise RuntimeError(f"dcm2niix exited {completed.returncode}")
        images = sorted((attempt / "converted").glob("*.nii.gz"))
        if len(images) != 1:
            raise ValueError("expected exactly one converted 4D NIfTI")
        shape, tr = nifti_shape_and_tr(images[0])
        if not 100 <= shape[3] <= 1000:
            raise ValueError("converted volume count outside pilot bounds")
        state.update(
            status="SUCCESS",
            dicom_files=len(members),
            nifti_shape=shape,
            repetition_time_seconds=tr,
            outputs={str(p.relative_to(attempt)): hash_file(p) for p in sorted((attempt / "converted").iterdir()) if p.is_file()},
            event_alignment_verified=False,
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
    """Run a single conversion attempt from a Slurm allocation; no login work."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--series", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    state = run_pilot(
        args.root,
        archive_relative=args.archive,
        series=args.series,
        expected_count=args.expected_count,
        job=args.job,
    )
    print("BMVP_MRI_PILOT", state["status"], state["nifti_shape"], state["repetition_time_seconds"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
