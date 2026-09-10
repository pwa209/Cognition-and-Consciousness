"""Local report-calibration command with posterior draws and provenance."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.config import load_analysis_spec
from factorcon.models.report_measurement import OrdinalCalibration, fit_ordinal
from factorcon.pipeline.canonical import DEFAULT_SPEC
from factorcon.provenance import analysis_artifact
from factorcon.util import atomic_write_json, load_structured


def load_report_calibration(path: str | Path) -> OrdinalCalibration:
    """Load JSON v1 containing fixed-unit predictors and ordinal calibration reports.

    Reports use -1 for missing, never zero for unavailable. Source fields are data,
    not instructions. Predictor derivation must be documented in the calibration
    source record; metadata alone cannot verify that a predictor excludes neural data.
    """
    value = load_structured(path)
    if (
        value.get("schema_version") != 1
        or value.get("predictor_source") != "non_neural_fixed_units"
    ):
        raise ValueError(
            "report schema v1 and non_neural_fixed_units predictor declaration required"
        )
    reports = np.asarray(value["reports"])
    if reports.dtype.kind not in "iu":
        raise ValueError("report category codes must be integers")
    if type(value["categories"]) is not int:
        raise ValueError("integer category count required")
    data = OrdinalCalibration(
        np.asarray(value["design"], dtype=float),
        reports,
        tuple(value["subjects"]),
        tuple(value["contexts"]),
        value["categories"],
        value["anchor_id"],
    )
    data.validate()
    return data


@analysis_artifact("P04_report_measurement_local")
def fit_report_file(
    path: str | Path,
    output: str | Path,
    *,
    analysis_spec: str | Path = DEFAULT_SPEC,
    seed: int = 260830,
) -> dict[str, Any]:
    """Fit calibration reports only; output posterior arrays in probit units as JSON.

    Diagnostic flags are retained and require review before scientific interpretation.
    Neither favorable model scores nor report prevalence determines operational success.
    """
    data = load_report_calibration(path)
    spec = load_analysis_spec(analysis_spec)
    settings = spec["report_measurement"]
    posterior = fit_ordinal(
        data,
        draws=settings["draws"],
        warmup=settings["warmup"],
        chains=settings["chains"],
        seed=seed,
        context_specific_thresholds=settings["context_specific_thresholds"],
    )
    payload = {
        k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in asdict(posterior).items()
    }
    diagnostics = posterior.diagnostics
    result = {
        "schema_version": 1,
        "implementation": "hierarchical_ordinal_probit_v1",
        "posterior": payload,
        "calibration_ids": sorted(set(data.subjects)),
        "operational_E": "probability_report_liability_exceeds_first_threshold",
        "universal_consciousness_probability": False,
        "diagnostic_flags": {
            "rhat_above_1_01": diagnostics["max_rank_folded_split_rhat"] > 1.01,
            "bulk_ess_below_400": diagnostics["min_bulk_ess_estimate"] < 400,
        },
        "calibration_neural_overlap_check": "required_globally_when_patterns_are_loaded",
    }
    atomic_write_json(output, result)
    return result
