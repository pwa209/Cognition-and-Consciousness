"""Independent report/pattern stress generators and auditable local simulation runs.

Unlike the historical RDM self-recovery fixture, these generators do not call the
architecture design/covariance functions. Small runs test plumbing, not validity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from scipy.special import expit

from factorcon.config import load_analysis_spec
from factorcon.models.generative import PatternData
from factorcon.models.pattern_cv import evaluate_patterns
from factorcon.models.report_measurement import OrdinalCalibration, fit_ordinal
from factorcon.pipeline.canonical import DEFAULT_SPEC
from factorcon.provenance import analysis_artifact
from factorcon.util import atomic_write_json, load_structured


def simulate_patterns(
    scenario: str, *, seed: int, groups: int = 6, conditions: int = 8, features: int = 6
) -> PatternData:
    """Generate independent groups with repeated random patterns in synthetic SD units.

    Scenarios: signed unitary, factorized-correlated, design aliasing, and heavy-tail
    misspecification. Noise covariance is known from the generator, never test-fitted.
    This is a restricted scenario grid, not exhaustive theoretical identifiability.
    """
    if scenario not in {"unitary", "factorized", "aliased", "heavy_tail"}:
        raise ValueError("unknown pattern stress scenario")
    if groups < 3 or conditions < 4 or features < 1:
        raise ValueError("invalid independent-group/condition/feature counts")
    rng = np.random.default_rng(seed)
    e = rng.uniform(0.05, 0.95, conditions)
    k = e - e.mean() if scenario == "aliased" else rng.normal(size=conditions)
    r = rng.integers(0, 2, conditions)
    design = np.column_stack([e, k, r])
    if scenario in {"unitary", "aliased"}:
        basis = (1.1 * e - 0.7 * k + 0.3 * r)[:, None]
    else:
        basis = np.column_stack([e + 0.4 * k, k - 0.3 * r, 0.5 * e * k, 0.2 * r])
    # Repeated partitions share neural loadings, but have independent residuals.
    signal = np.stack([basis @ rng.normal(size=(basis.shape[1], features)) for _ in range(groups)])
    noise_condition = 0.3 ** np.abs(np.arange(conditions)[:, None] - np.arange(conditions)[None, :])
    residuals = (
        rng.standard_t(4, size=(groups, 2, conditions, features)) / np.sqrt(2)
        if scenario == "heavy_tail"
        else rng.normal(size=(groups, 2, conditions, features))
    )
    residuals = np.einsum("ij,grjf->grif", np.linalg.cholesky(noise_condition), residuals)
    patterns = signal[:, None] + residuals
    return PatternData(
        "stress",
        tuple(f"stress:{g}" for g in range(groups)),
        ("E", "K_content", "R"),
        patterns,
        design[None],
        np.zeros((conditions, 0)),
        np.kron(np.eye(2), noise_condition),
        "synthetic_SD_known_design",
    )


def simulate_reports(
    scenario: str, *, seed: int, subjects: int = 12, trials_per_subject: int = 30
) -> tuple[OrdinalCalibration, float]:
    """Generate ordered probit reports with site/subject effects and MAR/MNAR variants.

    Returns calibration trials and true slope in probit units. Missing-at-random
    selection depends on the observed predictor; MNAR depends on latent liability.
    The misspecified MNAR fit remains reported, not discarded for poor coverage.
    """
    if scenario not in {"complete", "mar", "mnar", "context_noninvariance"}:
        raise ValueError("unknown report stress scenario")
    if subjects < 4 or trials_per_subject < 3:
        raise ValueError("report stress needs >=4 subjects and >=3 trials each")
    rng = np.random.default_rng(seed)
    count = subjects * trials_per_subject
    sid = np.repeat(np.arange(subjects), trials_per_subject)
    contexts = sid % 2
    x = rng.normal(size=count)
    beta = 0.8
    liability = -0.2 + beta * x + rng.normal(0, 0.5, subjects)[sid] + 0.3 * contexts
    z = liability + rng.normal(size=count)
    upper = 1 + (contexts * 0.8 if scenario == "context_noninvariance" else 0)
    y = (z > 0).astype(int) + (z > upper).astype(int)
    if scenario in {"mar", "mnar"}:
        missing_probability = expit(-1 + (x if scenario == "mar" else z))
        y[rng.uniform(size=count) < missing_probability] = -1
    data = OrdinalCalibration(
        np.column_stack([np.ones(count), x]),
        y,
        tuple(f"simulation:{s}" for s in sid),
        tuple(f"context:{c}" for c in contexts),
        3,
        "synthetic_report_anchor",
    )
    return data, beta


def validate_stress_plan(path: str | Path) -> dict[str, Any]:
    """Validate a declarative simulation plan; no simulations or filesystem writes."""
    plan = load_structured(path)
    if plan.get("suite") not in {"patterns", "reports"}:
        raise ValueError("stress suite must be patterns or reports")
    for key in ("replicates", "groups", "conditions", "features", "draws", "warmup", "chains"):
        if type(plan.get(key)) is not int or plan[key] < 1:
            raise ValueError(f"positive integer plan field required: {key}")
    permitted = (
        {"unitary", "factorized", "aliased", "heavy_tail"}
        if plan["suite"] == "patterns"
        else {"complete", "mar", "mnar", "context_noninvariance"}
    )
    if (
        not isinstance(plan.get("scenarios"), list)
        or not plan["scenarios"]
        or set(plan["scenarios"]) - permitted
    ):
        raise ValueError("unknown or empty scenario list")
    if plan["groups"] < 4 or plan["conditions"] < 4 or plan["draws"] < 8 or plan["chains"] < 2:
        raise ValueError("insufficient simulation dimensions or chains")
    return plan


@analysis_artifact("P05_independent_stress_local")
def run_stress_plan(
    path: str | Path,
    output: str | Path,
    *,
    analysis_spec: str | Path = DEFAULT_SPEC,
    seed: int = 260830,
) -> dict[str, Any]:
    """Run all specified replicates and retain failures/diagnostics, never select seeds.

    Coverage is estimated for the report slope only. Pattern model wins are prediction
    frequencies, NOT type-I error. Full simultaneous inference calibration is not yet
    connected to pattern scores. Every completed replicate is atomically checkpointed.
    """
    plan = validate_stress_plan(path)
    spec = load_analysis_spec(analysis_spec)
    rows = []
    checkpoint = Path(str(output) + ".checkpoint.json")
    # Restart begins a fresh deterministic run; existing final outputs are preserved
    # by the provenance decorator. Checkpoint records are recovery evidence, not a cache.
    for scenario in plan["scenarios"]:
        for replicate in range(plan["replicates"]):
            run_seed = seed + replicate  # paired scenario seeds are deliberate.
            row: dict[str, Any] = {"scenario": scenario, "replicate": replicate, "seed": run_seed}
            try:
                if plan["suite"] == "reports":
                    data, true_beta = simulate_reports(
                        scenario,
                        seed=run_seed,
                        subjects=plan["groups"],
                        trials_per_subject=plan["conditions"],
                    )
                    posterior = fit_ordinal(
                        data,
                        draws=plan["draws"],
                        warmup=plan["warmup"],
                        chains=plan["chains"],
                        seed=run_seed,
                    )
                    lower, upper = np.quantile(posterior.beta[:, :, 1], [0.025, 0.975])
                    row.update(
                        status="completed",
                        true_beta=true_beta,
                        interval_95=[float(lower), float(upper)],
                        covered=bool(lower <= true_beta <= upper),
                        diagnostics=posterior.diagnostics,
                        missing_fraction=float(np.mean(data.reports == -1)),
                    )
                else:
                    data = simulate_patterns(
                        scenario,
                        seed=run_seed,
                        groups=plan["groups"],
                        conditions=plan["conditions"],
                        features=plan["features"],
                    )
                    settings = spec["pattern_evaluation"]
                    evaluation = evaluate_patterns(
                        (data,),
                        mode="within",
                        penalties=tuple(settings["penalties"]),
                        interactions=(("E", "K_content"),),
                        shape_options={
                            k: settings[k] for k in ("unitary_rank", "gate_floor", "report_leak")
                        },
                        fit_options={
                            "starts": settings["optimizer_starts"],
                            "max_iter": settings["max_iter"],
                            "seed": run_seed,
                        },
                    )
                    row.update(status="completed", evaluation=evaluation)
                rows.append(row)
            except (ValueError, np.linalg.LinAlgError) as exc:
                rows.append({**row, "status": "failed", "reason": str(exc)})
            atomic_write_json(checkpoint, {"plan": plan, "rows": rows, "complete": False})
    summary = {}
    if plan["suite"] == "reports":
        from scipy.stats import beta as beta_distribution

        for scenario in plan["scenarios"]:
            completed = [
                r for r in rows if r["scenario"] == scenario and r["status"] == "completed"
            ]
            coverage = float(np.mean([r["covered"] for r in completed])) if completed else None
            successes = sum(r["covered"] for r in completed)
            count = len(completed)
            coverage_interval = (
                [
                    float(beta_distribution.ppf(0.025, successes, count - successes + 1))
                    if successes
                    else 0.0,
                    float(beta_distribution.ppf(0.975, successes + 1, count - successes))
                    if successes < count
                    else 1.0,
                ]
                if count
                else None
            )
            summary[scenario] = {
                "completed": len(completed),
                "requested": plan["replicates"],
                "coverage_estimate": coverage,
                "coverage_binomial_interval_95": coverage_interval,
                "coverage_mc_se": float(np.sqrt(coverage * (1 - coverage) / len(completed)))
                if coverage is not None
                else None,
                "scope": "conditional_on_completed_fits_inspect_all_diagnostics",
            }
    result = {
        "plan": plan,
        "rows": rows,
        "summary": summary,
        "small_run_is_not_validation": plan["replicates"] < 200,
        "simultaneous_pattern_type_I_error_validated": False,
        "scientific_gate": None,
    }
    atomic_write_json(output, result)
    atomic_write_json(checkpoint, {"plan": plan, "complete": True, "output": str(output)})
    return result
