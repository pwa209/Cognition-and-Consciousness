"""Synthetic BMVP conversion-pilot fixtures; no participant images or DICOM."""

from __future__ import annotations

import gzip
import io
import struct
import tarfile

import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.empirical import safe_tar_members
from scripts.alliance.bmvp_mri_pilot import nifti_shape_and_tr, select_dicom_members


def test_fixed_series_selects_expected_files_without_extracting(tmp_path) -> None:
    """Selection uses only safe TAR names and an explicit file-count expectation."""
    archive = tmp_path / "tiny.tar"
    with tarfile.open(archive, "w") as writer:
        for name in (
            "MRI_Data/sub_0006-0001-00001.dcm",
            "MRI_Data/sub_0006-0001-00002.dcm",
            "MRI_Data/sub_0007-0001-00001.dcm",
        ):
            member = tarfile.TarInfo(name)
            member.size = 1
            writer.addfile(member, io.BytesIO(b"x"))
    with tarfile.open(archive) as reader:
        selected = select_dicom_members(
            safe_tar_members(reader), series="sub_0006", expected_count=2
        )
    assert len(selected) == 2
    assert not (tmp_path / "MRI_Data").exists()
    with tarfile.open(archive) as reader:
        with pytest.raises(ValueError, match="count"):
            select_dicom_members(safe_tar_members(reader), series="sub_0006", expected_count=3)


def test_unsafe_tar_path_rejected_before_series_selection(tmp_path) -> None:
    """Traversal cannot be used to escape the job-specific extraction directory."""
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as writer:
        member = tarfile.TarInfo("../sub_0006-0001-00001.dcm")
        member.size = 1
        writer.addfile(member, io.BytesIO(b"x"))
    with tarfile.open(archive) as reader:
        with pytest.raises(IntegrityError):
            select_dicom_members(safe_tar_members(reader), series="sub_0006", expected_count=1)


def test_nifti_header_reads_four_dimensional_seconds(tmp_path) -> None:
    """A tiny NIfTI-1 fixture yields dimensions and TR, not voxel outcomes."""
    header = bytearray(348)
    struct.pack_into("<i", header, 0, 348)
    struct.pack_into("<8h", header, 40, 4, 10, 11, 12, 720, 1, 1, 1)
    struct.pack_into("<8f", header, 76, 1, 2, 2, 2, 1.25, 1, 1, 1)
    header[123] = 10  # millimetres and seconds
    image = tmp_path / "fixture.nii.gz"
    with gzip.open(image, "wb") as output:
        output.write(header)
    assert nifti_shape_and_tr(image) == ((10, 11, 12, 720), 1.25)
    header[123] = 2  # spatial units without declared time units
    with gzip.open(image, "wb") as output:
        output.write(header)
    with pytest.raises(ValueError, match="seconds"):
        nifti_shape_and_tr(image)
