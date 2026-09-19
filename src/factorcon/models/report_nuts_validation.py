"""Synthetic-only numerical checks for the marginal report sampler."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
from scipy.integrate import quad
from scipy.stats import truncnorm

from factorcon.models.report_measurement import OrdinalCalibration
from factorcon.models.report_nuts import fit_ordinal_nuts, ordinal_log_prob


def validate_sampling(settings: dict[str, Any]) -> dict[str, Any]:
    """Compare NUTS to scalar quadrature and exercise the whole synthetic hierarchy.

    No real participant or neural data are read. Scalar posterior means are checked
    against deterministic integration within six Monte Carlo standard errors plus
    0.002 probit units. Hierarchical recovery is recorded, not a scientific gate;
    one synthetic realization cannot establish repeated-sample coverage.
    """
    import arviz as az
    import pymc as pm
    import pytensor.tensor as pt

    seed = settings["qualification_synthetic_seed"]
    draws = settings["qualification_synthetic_draws"]
    warmup = settings["qualification_synthetic_warmup"]
    rng = np.random.default_rng(seed)
    eta = np.tile(np.array([-1.0, 0.0, 1.0, 2.0]), 30)
    y = np.digitize(eta + rng.normal(size=len(eta)), [0.0, 1.2])

    def density(cut: float) -> float:
        return float(
            ordinal_log_prob(eta, cut, y).sum()
            + truncnorm.logpdf(cut, -0.5, np.inf, loc=1, scale=2)
        )

    offset = density(1.2)
    z = quad(lambda c: np.exp(density(c) - offset), 0, np.inf, epsabs=1e-10)[0]
    exact = quad(lambda c: c * np.exp(density(c) - offset), 0, np.inf, epsabs=1e-10)[0] / z
    with pm.Model():
        cut = pm.TruncatedNormal("cut", mu=1, sigma=2, lower=0)
        pm.OrderedProbit("report", eta=eta, cutpoints=pt.stack([0.0, cut]), observed=y)
        sample = pm.sample(
            draws=draws,
            tune=warmup,
            chains=4,
            cores=4,
            random_seed=seed,
            target_accept=0.95,
            progressbar=False,
        )
    trace = sample.posterior["cut"].values
    mcse = float(az.mcse(trace, method="mean"))
    scalar = {
        "quadrature_mean": exact,
        "sample_mean": float(trace.mean()),
        "mcse": mcse,
        "tolerance": 6 * mcse + 0.002,
        "rhat": float(az.rhat(trace)),
        "ess_bulk": float(az.ess(trace)),
        "divergences": int(sample.sample_stats.diverging.values.sum()),
    }
    scalar["numerical_agreement"] = bool(abs(trace.mean() - exact) <= scalar["tolerance"])
    if not scalar["numerical_agreement"] or not np.isfinite(mcse):
        raise ValueError(f"synthetic quadrature verification failed: {scalar}")

    n = 480
    x = np.column_stack([np.ones(n), rng.choice([-1.0, 0.0, 1.0], n)])
    si, ci = np.arange(n) % 8, (np.arange(n) // 8) % 4
    truth_beta = np.array([0.15, 0.7])
    eta = x @ truth_beta + rng.normal(0, 0.4, 8)[si] + rng.normal(0, 0.3, 4)[ci]
    y = np.digitize(eta + rng.normal(size=n), [0.0, 1.1])
    y[::19] = -1
    data = OrdinalCalibration(
        x,
        y,
        tuple(f"synthetic:s{s}" for s in si),
        tuple(f"synthetic:c{c}" for c in ci),
        3,
        "synthetic-only",
    )
    posterior, diagnostic, _ = fit_ordinal_nuts(
        data,
        draws=draws,
        warmup=warmup,
        chains=4,
        seed=seed + 1,
        cores=4,
        target_accept=settings["target_accept"],
        parameterization=settings["parameterization"],
    )
    recovery = []
    for name, trace, truth in (
        ("slope", posterior.beta[:, :, 1], 0.7),
        ("upper_threshold", posterior.thresholds[:, :, 0, 1], 1.1),
    ):
        lo, hi = np.quantile(trace, [0.025, 0.975])
        recovery.append(
            {
                "parameter": name,
                "truth": truth,
                "mean": float(trace.mean()),
                "interval95": [float(lo), float(hi)],
                "covers_truth": bool(lo <= truth <= hi),
            }
        )
    # Exercise serialization and compatible shape, not a desired scientific outcome.
    assert asdict(posterior)["thresholds"].shape == (4, draws, 1, 2)
    return {
        "scalar_quadrature": scalar,
        "hierarchical_recovery": recovery,
        "hierarchical_diagnostics": diagnostic,
        "synthetic_only": True,
        "coverage_validation": False,
        "scientific_gate": None,
    }
