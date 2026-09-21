"""Tiny real-NIfTI parcel test inside the existing fMRIPrep image, not empirical evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

from factorcon.pipeline.masked_parcels import extract_parcels


def main(directory: Path) -> None:
    """Create three tiny images, verify exact parcel units and report a technical result."""
    directory.mkdir(parents=True, exist_ok=False)
    atlas = np.asarray([0, 1, 1, 1, 2, 2, 2, 2], dtype=np.int16).reshape(2, 2, 2)
    bold = np.repeat(atlas[..., None], 3, axis=3).astype(np.float32) * 7
    for name, value in (("bold", bold), ("mask", np.ones_like(atlas)), ("atlas", atlas)):
        nib.save(nib.Nifti1Image(value, np.eye(4)), directory / (name + ".nii.gz"))
    values, coverage = extract_parcels(
        directory / "bold.nii.gz", directory / "mask.nii.gz", directory / "atlas.nii.gz", parcels=2
    )
    assert np.allclose(values, [[7, 14]] * 3) and np.all(coverage == 1)
    print(
        json.dumps(
            {
                "status": "SUCCESS",
                "scope": "synthetic_NIfTI_geometry_and_units_only",
                "nibabel": nib.__version__,
            }
        )
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
