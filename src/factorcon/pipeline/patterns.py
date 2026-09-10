"""Versioned pattern input contract and provenance-backed local prediction stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.config import load_analysis_spec
from factorcon.models.generative import PatternData
from factorcon.models.pattern_cv import evaluate_patterns, validate_collection
from factorcon.pipeline.canonical import DEFAULT_SPEC
from factorcon.provenance import analysis_artifact
from factorcon.util import atomic_write_json


def load_pattern_data(path: str | Path) -> PatternData:
    """Read non-pickled NPZ v1 in fixed calibrated units; reject undeclared fitting.

    The metadata assertions are necessary provenance contracts, not evidence that an
    upstream method is scientifically valid. Acquisition/feature QC remains separate.
    No filesystem paths from metadata are opened or executed.
    """
    with np.load(path, allow_pickle=False) as archive:
        required = {
            "metadata",
            "group_ids",
            "names",
            "patterns",
            "design_draws",
            "sensory",
            "noise",
        }
        if set(archive.files) != required:
            raise ValueError("pattern NPZ v1 requires exactly the documented array keys")
        arrays = {k: archive[k].copy() for k in required}
    meta = json.loads(str(arrays.pop("metadata").item()))
    if meta.get("schema_version") != 1:
        raise ValueError("unknown pattern schema version")
    if meta.get("source_kind") not in {"synthetic_fixture", "derived_neural_patterns"}:
        raise ValueError("explicit synthetic versus empirical source kind required")
    if meta.get("design_source") not in {"fixed_by_design", "external_calibration"}:
        raise ValueError("all-subject empirical designs are not fold safe")
    for key in ("units", "anchor_id", "family", "feature_definition", "noise_definition"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise ValueError(f"missing declared {key}")
    for key in ("group_ids", "names"):
        if arrays[key].ndim != 1 or arrays[key].dtype.kind not in "US":
            raise ValueError(f"{key} must be a one-dimensional string array")
    calibration = meta.get("calibration_ids", [])
    if not isinstance(calibration, list) or any(
        not isinstance(g, str) or not g for g in calibration
    ):
        raise ValueError("calibration_ids must be a list of nonempty global subject IDs")
    if meta["design_source"] == "external_calibration" and not calibration:
        raise ValueError("external calibration requires auditable calibration subject IDs")
    if meta["source_kind"] != "synthetic_fixture":
        if "E" in arrays["names"] and meta["design_source"] != "external_calibration":
            raise ValueError("empirical E cannot be assigned as a ground-truth design label")
        if meta.get("feature_scaling") != "independent_calibration":
            raise ValueError("this contract requires independent feature/noise calibration")
        if not calibration or not meta.get("source_sha256"):
            raise ValueError(
                "empirical features require independent calibration IDs and source hashes"
            )
    data = PatternData(
        meta["family"],
        tuple(arrays["group_ids"].tolist()),
        tuple(arrays["names"].tolist()),
        arrays["patterns"].astype(float),
        arrays["design_draws"].astype(float),
        arrays["sensory"].astype(float),
        arrays["noise"].astype(float),
        meta["anchor_id"],
        tuple(calibration),
    )
    data.validate()
    return data


def validate_pattern_inputs(
    paths: list[str | Path], analysis_spec: str | Path = DEFAULT_SPEC, *, mode: str | None = None
) -> tuple[tuple[PatternData, ...], dict[str, Any]]:
    """Validate inputs/specification without output writes or numerical fitting."""
    spec = load_analysis_spec(analysis_spec)
    datasets = tuple(load_pattern_data(p) for p in paths)
    validate_collection(datasets)
    if "pattern_evaluation" not in spec:
        raise ValueError("pattern_evaluation configuration is required")
    if any(len(d.group_ids) < 3 for d in datasets):
        raise ValueError("nested evaluation needs >=3 independent groups per family")
    if mode == "lofo" and len(datasets) < 2:
        raise ValueError("LOFO needs >=2 families")
    return datasets, spec


@analysis_artifact("P07_generative_patterns_local")
def score_pattern_files(
    paths: list[str | Path],
    output: str | Path,
    *,
    mode: str,
    analysis_spec: str | Path = DEFAULT_SPEC,
    seed: int = 260830,
    bootstrap_replicates: int = 0,
) -> dict[str, Any]:
    """Score NPZ families locally; preserve failures and provenance, no server dispatch."""
    datasets, spec = validate_pattern_inputs(paths, analysis_spec, mode=mode)
    settings = spec["pattern_evaluation"]
    options = dict(
        mode=mode,
        penalties=tuple(settings["penalties"]),
        interactions=tuple(tuple(i.split(":")) for i in spec["interactions"]),
        shape_options={k: settings[k] for k in ("unitary_rank", "gate_floor", "report_leak")},
        fit_options={
            "starts": settings["optimizer_starts"],
            "max_iter": settings["max_iter"],
            "seed": seed,
        },
    )
    if bootstrap_replicates:
        from factorcon.stats.pattern_bootstrap import refit_pattern_bootstrap

        result = refit_pattern_bootstrap(
            datasets, replicates=bootstrap_replicates, evaluation_options=options, seed=seed
        )
    else:
        result = evaluate_patterns(datasets, **options)
    atomic_write_json(output, result)
    return result
