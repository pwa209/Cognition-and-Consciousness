"""Auditable P06 handoff, not a substitute for raw-recording preprocessing.

Bundles contain runwise beta/epoch patterns and independently sampled calibration
residuals in identical feature units/order. No source file is executed or extracted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.features.patterns import whiten_patterns
from factorcon.models.generative import PatternData
from factorcon.models.pattern_cv import validate_collection
from factorcon.util import ensure_within, hash_file, load_structured, safe_relative_path


def verified_record(root: Path, record: dict[str, str]) -> Path:
    """Resolve a root-relative file and verify its SHA-256; no fitting or code execution."""
    path = ensure_within(root, root / safe_relative_path(record["path"]))
    digest = record["sha256"]
    if (
        len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
        or not path.is_file()
        or hash_file(path) != digest
    ):
        raise ValueError(f"input missing or SHA-256 mismatch: {record['path']}")
    return path


def _strings(value: np.ndarray, name: str) -> tuple[str, ...]:
    if value.ndim != 1 or value.dtype.kind not in "US" or not len(value):
        raise ValueError(f"{name}: nonempty string vector required")
    result = tuple(value.tolist())
    if len(set(result)) != len(result) or any(not s.strip() for s in result):
        raise ValueError(f"{name}: unique nonempty IDs required")
    return result


def load_bundle(
    root: Path, record: dict[str, str], *, ridge_fraction: float
) -> tuple[PatternData, dict[str, Any]]:
    """Validate bundle v1 then whiten features using disjoint calibration subjects only.

    Arrays are G x R x C x F neural summaries, N x F independent residuals,
    D x C x Q design draws, C x J sensory regressors and RC x RC design noise.
    It is a technical contract, not proof that upstream preprocessing is valid.
    Empirical E requires external report calibration; missing constructs stay absent.
    """
    manifest = verified_record(root, record)
    value = load_structured(manifest)
    if value.get("schema_version") != 1 or value.get("source_kind") != "derived_neural_patterns":
        raise ValueError("P06 requires an empirical bundle v1, never a simulation substitute")
    for key in (
        "family",
        "anchor_id",
        "source_units",
        "feature_definition",
        "noise_definition",
        "condition_definition",
        "partition_definition",
        "independent_unit",
    ):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError(f"missing bundle declaration: {key}")
    if value["independent_unit"] not in {"participant", "patient"}:
        raise ValueError("independent unit must be participant or patient, never electrode")
    if value.get("modality") == "ieeg" and value["independent_unit"] != "patient":
        raise ValueError("iEEG requires patient grouping")
    if value.get("design_source") not in {"fixed_by_design", "external_calibration"}:
        raise ValueError("neural-outcome-fitted designs are forbidden")
    if value.get("noise_source") not in {"fixed_design", "independent_calibration"}:
        raise ValueError("test-neural noise covariance estimation is forbidden")
    if value.get("selection_basis") != "design_and_technical_integrity_only":
        raise ValueError("outcome-independent feature/condition/group selection required")
    proofs = value.get("provenance", [])
    if not proofs:
        raise ValueError("hashed preprocessing/calibration provenance required")
    required_roles = {"preprocessing", "noise_calibration", "condition_mapping"}
    if value["design_source"] == "external_calibration":
        required_roles.add("report_or_construct_calibration")
    if not required_roles <= {p.get("role") for p in proofs}:
        raise ValueError("missing preprocessing or calibration provenance role")
    for proof in proofs:
        evidence = load_structured(verified_record(root, proof))
        if evidence.get("status") != "SUCCESS" or evidence.get("scientific_gate") is not None:
            raise ValueError("upstream technical provenance must record SUCCESS and no gate")
    arrays_path = verified_record(root, value["arrays"])
    required = {
        "patterns",
        "group_ids",
        "names",
        "design_draws",
        "sensory",
        "noise",
        "calibration_residuals",
        "calibration_ids",
        "design_calibration_ids",
        "feature_ids",
        "calibration_feature_ids",
        "condition_ids",
        "partition_ids",
    }
    with np.load(arrays_path, allow_pickle=False) as archive:
        if set(archive.files) != required:
            raise ValueError("bundle NPZ requires exactly the documented array keys")
        arrays = {name: archive[name].copy() for name in required}
    groups = _strings(arrays["group_ids"], "group_ids")
    calibration = _strings(arrays["calibration_ids"], "calibration_ids")
    features = _strings(arrays["feature_ids"], "feature_ids")
    if features != _strings(arrays["calibration_feature_ids"], "calibration_feature_ids"):
        raise ValueError("feature/calibration order mismatch")
    conditions = _strings(arrays["condition_ids"], "condition_ids")
    partitions = _strings(arrays["partition_ids"], "partition_ids")
    names = _strings(arrays["names"], "names")
    dc = arrays["design_calibration_ids"]
    if dc.ndim != 1 or dc.dtype.kind not in "US":
        raise ValueError("design_calibration_ids must be a string vector (possibly empty)")
    design_ids = _strings(dc, "design_calibration_ids") if len(dc) else ()
    if value["design_source"] == "external_calibration" and not design_ids:
        raise ValueError("external design requires independent calibration IDs")
    if "E" in names and value["design_source"] != "external_calibration":
        raise ValueError("empirical E cannot be assigned a ground-truth design label")
    if arrays["patterns"].shape != (len(groups), len(partitions), len(conditions), len(features)):
        raise ValueError("feature/condition/partition expected-count mismatch")
    if any(":" not in g for g in (*groups, *calibration, *design_ids)):
        raise ValueError("globally namespaced subject IDs required")
    data = PatternData(
        value["family"],
        groups,
        names,
        arrays["patterns"].astype(float),
        arrays["design_draws"].astype(float),
        arrays["sensory"].astype(float),
        arrays["noise"].astype(float),
        value["anchor_id"],
        design_ids,
    )
    result = whiten_patterns(
        data,
        arrays["calibration_residuals"],
        calibration_ids=calibration,
        ridge_fraction=ridge_fraction,
    )
    metadata = {
        "schema_version": 1,
        "source_kind": "derived_neural_patterns",
        "family": result.family,
        "anchor_id": result.anchor_id,
        "units": "independent_residual_SD",
        "source_units": value["source_units"],
        "design_source": value["design_source"],
        "feature_scaling": "independent_calibration",
        "calibration_ids": list(result.calibration_ids),
        "feature_definition": value["feature_definition"],
        "noise_definition": value["noise_definition"],
        "source_sha256": {r["path"]: r["sha256"] for r in [record, value["arrays"], *proofs]},
        "condition_ids": conditions,
        "partition_ids": partitions,
        "feature_ids": features,
        "ridge_fraction": ridge_fraction,
        "raw_preprocessing_performed_here": False,
        "independent_unit": value["independent_unit"],
    }
    result.validate()
    # Detect a changed input during parsing/calibration before publishing any result.
    for check in (record, value["arrays"], *proofs):
        verified_record(root, check)
    return result, metadata


def load_campaign(
    root: Path, campaign: Path, *, ridge_fraction: float
) -> tuple[tuple[PatternData, ...], tuple[dict[str, Any], ...]]:
    """Verify a private campaign and every bundle; enforce global calibration isolation."""
    ensure_within(root, campaign)
    value = load_structured(campaign)
    if (
        value.get("schema_version") != 1
        or value.get("scientific_gates") is not False
        or not value.get("bundles")
    ):
        raise ValueError("nonempty empirical campaign v1 with no scientific gates required")
    pairs = [load_bundle(root, r, ridge_fraction=ridge_fraction) for r in value["bundles"]]
    datasets, metadata = tuple(p[0] for p in pairs), tuple(p[1] for p in pairs)
    validate_collection(datasets)
    if any(len(d.group_ids) < 3 for d in datasets):
        raise ValueError("nested evaluation needs >=3 independent groups per family")
    if len({d.family for d in datasets}) != len(datasets):
        raise ValueError("one bundle per family required")
    return datasets, metadata


def write_pattern_file(path: Path, data: PatternData, metadata: dict[str, Any]) -> None:
    """Atomically create a non-pickled calibrated pattern NPZ, never overwrite a result."""
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_suffix(".npz.partial")
    with temporary.open("xb") as handle:
        np.savez_compressed(
            handle,
            patterns=data.patterns,
            group_ids=np.asarray(data.group_ids),
            names=np.asarray(data.names),
            design_draws=data.design_draws,
            sensory=data.sensory,
            noise=data.noise,
            metadata=json.dumps(metadata),
        )
    os.replace(temporary, path)
