"""Fixed first-level operators for the initial masked-fMRI cortical association lane.

No scaling, covariance fitting, threshold choice or feature selection on evaluation
neural outcomes. First-level contrasts are linear operators determined by the run
design. Temporal and spatial noise parameters are learned only in reserved subjects.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.linalg import block_diag
from scipy.stats import gamma


def validate_feature_plan(plan: dict[str, Any]) -> None:
    """Reject unsupported source/units/settings before any neural read; no scientific gate."""
    if (
        plan.get("schema_version") != 1
        or plan.get("scientific_gates") is not False
        or plan.get("expected_parcels") != 400
        or plan.get("expected_runs") != 380
        or plan.get("hrf") != "SPM_canonical_plus_temporal_derivative_impulses"
        or plan.get("partitions") != "alternating_runs_sorted_by_numeric_session_and_run"
        or len(plan.get("conditions", [])) != 6
        or plan.get("posterior_draws") != 32
    ):
        raise ValueError("unsupported masked-feature plan")
    if (
        not 0 < plan["minimum_parcel_coverage"] <= 1
        or not 0 < plan["maximum_censored_fraction"] < 1
    ):
        raise ValueError("invalid technical coverage/censoring settings")


def numeric_column(
    rows: list[dict[str, str]], name: str, *, missing_zero: bool = False
) -> np.ndarray:
    """Read a confound in publisher units; only allowed first-row missingness becomes zero."""
    result = []
    for index, row in enumerate(rows):
        raw = row[name]
        value = 0.0 if raw in {"n/a", "", "nan"} and missing_zero and index == 0 else float(raw)
        if not math.isfinite(value):
            raise ValueError(f"nonfinite confound: {name}")
        result.append(value)
    return np.asarray(result)


def run_design(
    trials: list[dict[str, Any]],
    rows: list[dict[str, str]],
    tr: float,
    start_time: float,
    plan: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Return six canonical regressors and fixed nuisance columns in scanner seconds.

    Image exposures are impulses (frame duration not asserted). Temporal derivatives,
    unknown-report events, motion24, first five aCompCor, DCT drift, censor spikes
    and an intercept are nuisance. No BOLD-dependent regressor or outcome selection.
    """
    n = len(rows)
    if n < 20 or not 0 < tr < 10 or not 0 <= start_time < tr:
        raise ValueError("invalid acquisition times")
    dt = tr / plan["hrf_oversampling"]
    grid = np.arange(0, 32 + dt, dt)
    hrf = gamma.pdf(grid, 6) - gamma.pdf(grid, 16) / 6
    hrf /= np.sum(hrf) * dt
    derivative = np.gradient(hrf, dt)
    times = np.arange(n) * tr + start_time
    task, deriv = np.zeros((n, 8)), np.zeros((n, 8))
    counts = [0] * 8
    outside = []
    for trial in trials:
        onset = trial["image_onset_seconds"]
        if onset >= n * tr:
            outside.append(trial["trial"])
            continue
        report, category = trial["report"], trial["nonliving"]
        index = category * 3 + report if report >= 0 else 6 + category
        counts[index] += 1
        task[:, index] += np.interp(times - onset, grid, hrf, left=0, right=0)
        deriv[:, index] += np.interp(times - onset, grid, derivative, left=0, right=0)
    names = list(rows[0])
    nuisance = [np.ones(n), *task[:, 6:].T, *deriv.T]
    for motion in ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"):
        for suffix in ("", "_derivative1", "_power2", "_derivative1_power2"):
            nuisance.append(
                numeric_column(rows, motion + suffix, missing_zero="derivative" in suffix)
            )
    compcor = sorted(k for k in names if k.startswith("a_comp_cor_"))
    if len(compcor) < 5:
        raise ValueError("five retained aCompCor components required")
    nuisance.extend(numeric_column(rows, k) for k in compcor[:5])
    for k in range(1, int(np.floor(2 * n * tr / plan["high_pass_seconds"])) + 1):
        nuisance.append(np.cos(np.pi * (np.arange(n) + 0.5) * k / n))
    fd = numeric_column(rows, "framewise_displacement", missing_zero=True)
    censor = fd > plan["fd_threshold_mm"]
    nonsteady = [k for k in names if k.startswith("non_steady_state_outlier")]
    for name in nonsteady:
        censor |= numeric_column(rows, name).astype(bool)
    nuisance.extend(np.eye(n)[:, censor].T)
    return (
        task[:, :6],
        np.column_stack(nuisance),
        {
            "condition_counts": counts,
            "outside_scan_trials": outside,
            "censored_volumes": int(censor.sum()),
            "censored_fraction": float(censor.mean()),
            "excluded": bool(censor.mean() > plan["maximum_censored_fraction"]),
            "exclusion_reason": "censored_fraction_above_0.2"
            if censor.mean() > plan["maximum_censored_fraction"]
            else None,
            "start_time_seconds": start_time,
            "hrf_event_units": "unit_impulses_not_assumed_frame_duration",
        },
    )


def ar_transform(values: np.ndarray, rho: float) -> np.ndarray:
    """Apply externally calibrated stationary AR(1) whitening; no parameter fit here."""
    if not 0 <= rho <= 0.95:
        raise ValueError("AR coefficient outside declared calibration bounds")
    result = values.copy()
    result[0] *= np.sqrt(1 - rho * rho)
    result[1:] = values[1:] - rho * values[:-1]
    return result


def linear_summary(
    y: np.ndarray, task: np.ndarray, nuisance: np.ndarray, rho: float = 0.0
) -> dict[str, Any]:
    """Design-only GLS sufficient statistics, unscaled intensity units; rank loss is explicit.

    Evaluation BOLD is multiplied by a fixed linear operator, not used to fit noise
    covariance, scaling or predictive nuisance transformations. Empty condition columns
    remain zero-information; aggregate partitions must be full rank before fitting.
    """
    if (
        y.ndim != 2
        or task.shape != (len(y), 6)
        or nuisance.ndim != 2
        or len(nuisance) != len(y)
        or not all(np.isfinite(v).all() for v in (y, task, nuisance))
    ):
        raise ValueError("finite aligned time-feature/task/nuisance matrices required")
    yw, x, z = (ar_transform(v, rho) for v in (y, task, nuisance))
    u, s, _ = np.linalg.svd(z, full_matrices=False)
    rank = int(np.sum(s > max(z.shape) * np.finfo(float).eps * s[0]))
    basis = u[:, :rank]
    x = x - basis @ (basis.T @ x)
    yr = yw - basis @ (basis.T @ yw)
    information = x.T @ x
    score = x.T @ yr
    beta = np.linalg.pinv(information, rcond=1e-10) @ score
    residual = yr - x @ beta
    df = len(y) - rank - np.linalg.matrix_rank(x)
    if df < 10:
        raise ValueError("insufficient residual degrees of freedom")
    return {
        "information": information,
        "score": score,
        "residual": residual,
        "df": int(df),
        "rows": len(y),
        "rank": int(np.linalg.matrix_rank(x)),
    }


def estimate_ar1(residuals: list[np.ndarray]) -> float:
    """Estimate AR(1) from reserved residuals only, excluding between-run transitions."""
    if not residuals or any(
        v.ndim != 2 or len(v) < 3 or not np.isfinite(v).all() for v in residuals
    ):
        raise ValueError("finite calibration residual runs required")
    numerator = sum(np.sum(v[:-1] * v[1:]) for v in residuals)
    denominator = sum(np.sum(v[:-1] ** 2) for v in residuals)
    if denominator <= 0:
        raise ValueError("zero calibration residual variation")
    return float(np.clip(numerator / denominator, 0, 0.95))


def combine_partitions(
    summaries: list[dict[str, Any]], partition: list[int]
) -> tuple[np.ndarray, np.ndarray]:
    """Combine GLS design information within fixed partitions, without fitting outcome variance."""
    if len(summaries) != len(partition) or set(partition) != {0, 1}:
        raise ValueError("two aligned fixed partitions required")
    patterns, covariance = [], []
    for index in (0, 1):
        selected = [s for s, p in zip(summaries, partition, strict=True) if p == index]
        info = sum(s["information"] for s in selected)
        if np.linalg.matrix_rank(info, tol=np.linalg.norm(info, 2) * 1e-10) != 6:
            raise ValueError("condition partition is not estimable; no fabricated betas")
        inv = np.linalg.inv(info)
        patterns.append(inv @ sum(s["score"] for s in selected))
        covariance.append(inv)
    return np.asarray(patterns), block_diag(*covariance)
