"""Geometry-only Schaefer parcel extraction; nibabel is imported only for imaging jobs."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def extract_parcels(
    bold: Path, mask: Path, atlas: Path, *, parcels: int = 400
) -> tuple[np.ndarray, np.ndarray]:
    """Return time x parcel means in original intensity and mask coverage fractions.

    All images must already share MNI152NLin2009cAsym; nearest-neighbour label
    resampling reconciles grids only, never template spaces. No smoothing or fitted
    scaling; uncovered parcels remain zero pending geometry-only campaign selection.
    """
    import nibabel as nib
    from nibabel.processing import resample_from_to

    image, brain, labels = nib.load(bold), nib.load(mask), nib.load(atlas)
    if len(image.shape) != 4 or len(brain.shape) != 3 or len(labels.shape) != 3:
        raise ValueError("BOLD 4D and masks/atlas 3D required")
    if brain.shape != image.shape[:3] or not np.allclose(brain.affine, image.affine):
        raise ValueError("brain mask/BOLD grid mismatch")
    label_values = labels.get_fdata()
    if set(np.unique(label_values)) != set(range(parcels + 1)):
        raise ValueError("atlas label expected-count mismatch")
    if labels.shape != image.shape[:3] or not np.allclose(labels.affine, image.affine):
        labels = resample_from_to(labels, (image.shape[:3], image.affine), order=0)
    indices = np.asarray(labels.dataobj).astype(np.int32).reshape(-1)
    inside = np.asarray(brain.dataobj).reshape(-1) > 0
    full_count = np.bincount(indices, minlength=parcels + 1)[1:]
    count = np.bincount(indices[inside], minlength=parcels + 1)[1:]
    coverage = np.divide(
        count, full_count, out=np.zeros(parcels, dtype=float), where=full_count > 0
    )
    # One decompression per run, bounded by the requested Slurm memory allocation.
    data = image.get_fdata(dtype=np.float32).reshape(-1, image.shape[-1])
    selected = inside & (indices > 0)
    if not np.isfinite(data[selected]).all():
        raise ValueError("nonfinite masked BOLD")
    values = np.stack(
        [
            np.bincount(indices[selected], weights=data[selected, i], minlength=parcels + 1)[1:]
            for i in range(data.shape[1])
        ]
    )
    values = np.divide(values, count, out=np.zeros_like(values), where=count > 0)
    return values, coverage
