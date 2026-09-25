"""Outcome-blind compatibility contract for exploratory cross-family E–R transfer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.models.generative import PatternData


def audit_exploratory_er_transfer(
    paths: tuple[Path, ...], datasets: tuple[PatternData, ...]
) -> tuple[str, ...]:
    """Return technical non-estimability reasons without inspecting neural outcomes.

    Every pattern file must declare the same independently reviewed measurement
    bridge, six condition identities, feature/partition axes, sensory convention
    and independently scaled units. This verifies a machine-readable contract,
    not the scientific truth of the bridge; that requires separate review.
    E and R must vary jointly in each family's calibration design. Missing
    metadata never silently becomes an anchor by matching arbitrary strings.
    """
    issues: list[str] = []
    if len(paths) != len(datasets) or len(datasets) < 2:
        return ("exploratory E–R transfer requires >=2 matched empirical families",)
    metadata: list[dict[str, Any]] = []
    for path, data in zip(paths, datasets, strict=True):
        with np.load(path, allow_pickle=False) as archive:
            meta = json.loads(str(archive["metadata"].item()))
        metadata.append(meta)
        if meta.get("family") != data.family or meta.get("source_kind") != "derived_neural_patterns":
            issues.append(f"{data.family}: empirical family/source identity mismatch")
        if set(data.names) != {"E", "R"}:
            issues.append(f"{data.family}: restricted E–R design must retain exactly E and R")
        if data.design_draws.ndim == 4:
            design = np.mean(data.design_draws, axis=(0, 1))
        else:
            design = np.mean(data.design_draws, axis=0)
        if set(data.names) == {"E", "R"}:
            e, report = (design[:, data.names.index(name)] for name in ("E", "R"))
            matrix = np.stack([np.ones(len(e)), e, report, e * report], axis=1)
            if np.linalg.matrix_rank(matrix) < 4:
                issues.append(f"{data.family}: E/R/intercept/interaction condition design is rank deficient")
        bridge = meta.get("transfer_bridge")
        if (
            not isinstance(bridge, dict)
            or bridge.get("schema_version") != 1
            or bridge.get("estimand") != "exploratory_report_evidence_E_R"
            or bridge.get("calibration_status") != "independent_external_reviewed"
            or not isinstance(bridge.get("id"), str)
            or not bridge["id"].strip()
            or not isinstance(bridge.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", bridge["sha256"])
        ):
            issues.append(f"{data.family}: independently reviewed E–R measurement bridge missing")
        for key in ("condition_ids", "feature_ids", "partition_ids"):
            value = meta.get(key)
            if not isinstance(value, list) or not value or any(
                not isinstance(x, str) or not x.strip() for x in value
            ) or len(set(value)) != len(value):
                issues.append(f"{data.family}: valid {key} required for transfer")
        expected_axis_lengths = {
            "condition_ids": data.patterns.shape[2],
            "feature_ids": data.patterns.shape[3],
            "partition_ids": data.patterns.shape[1],
        }
        for key, expected in expected_axis_lengths.items():
            if isinstance(meta.get(key), list) and len(meta[key]) != expected:
                issues.append(f"{data.family}: {key} length differs from neural axis")
        if not isinstance(meta.get("sensory_definition"), str) or not meta["sensory_definition"].strip():
            issues.append(f"{data.family}: common sensory-covariate definition missing")
    first = metadata[0]
    for key in (
        "anchor_id", "units", "feature_definition", "noise_definition",
        "condition_ids", "feature_ids", "partition_ids", "sensory_definition",
    ):
        if any(meta.get(key) != first.get(key) for meta in metadata[1:]):
            issues.append(f"cross-family {key} differs")
    bridges = [meta.get("transfer_bridge") for meta in metadata]
    if any(bridge != bridges[0] for bridge in bridges[1:]):
        issues.append("cross-family reviewed bridge identities differ")
    sensory_widths = {data.sensory.shape[-1] for data in datasets}
    if len(sensory_widths) != 1:
        issues.append("cross-family sensory covariate dimensions differ")
    return tuple(dict.fromkeys(issues))


def nonestimable_lofo_rows(
    datasets: tuple[PatternData, ...], issues: tuple[str, ...]
) -> dict[str, Any]:
    """Retain every family/model row with no fabricated predictive score."""
    if not issues:
        raise ValueError("non-estimability requires a recorded technical reason")
    rows = []
    for data in datasets:
        for index in range(6):
            rows.append(
                {
                    "family": data.family,
                    "model": f"M{index}",
                    "test_groups": list(data.group_ids),
                    "test_group_weights": (
                        data.group_weights.tolist()
                        if data.group_weights is not None
                        else [1.0] * len(data.group_ids)
                    ),
                    "scored_dimensions_per_group": int(
                        data.patterns.shape[1]
                        * (data.patterns.shape[2] - 1)
                        * data.patterns.shape[3]
                    ),
                    "training_groups": [
                        group for source in datasets if source.family != data.family
                        for group in source.group_ids
                    ],
                    "status": "not_estimable",
                    "reason": "; ".join(issues),
                }
            )
    return {
        "implementation": "generative_pattern_v1",
        "mode": "lofo",
        "rows": rows,
        "preflight_issues": list(issues),
        "all_candidates_retained": True,
        "score_units": "joint_nats_per_independent_group",
        "scientific_gate": None,
    }
