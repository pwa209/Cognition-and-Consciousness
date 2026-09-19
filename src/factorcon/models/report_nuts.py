"""Marginal ordered-probit NUTS backend for the SAME three-category report model.

The latent Gaussian trial variables are analytically integrated out, not estimated
or fixed. Priors, probit residual scale, fixed zero threshold, and independent
calibration-subject boundary are identical to the legacy Gibbs implementation.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.special import log_ndtr
from scipy.stats import invgamma, norm, truncnorm

from factorcon.models.report_measurement import OrdinalCalibration, OrdinalPosterior


def grouped_reports(data: OrdinalCalibration) -> dict[str, Any]:
    """Compress identical observed trial likelihood terms exactly, without fitted transforms.

    Keys include subject, context, every fixed-unit predictor and report category.
    Count-weighted log likelihood equals the uncompressed trial log likelihood;
    there is no binning, averaging, exclusion of observed reports or neural input.
    Missing reports contribute no likelihood, matching the original model exactly.
    """
    data.validate()
    if data.categories != 3:
        raise ValueError("validated NUTS backend requires three ordinal categories")
    observed = data.reports >= 0
    subjects = tuple(sorted({s for s, keep in zip(data.subjects, observed, strict=True) if keep}))
    contexts = tuple(sorted({s for s, keep in zip(data.contexts, observed, strict=True) if keep}))
    counts: Counter[tuple[Any, ...]] = Counter()
    for x, y, s, c in zip(data.design, data.reports, data.subjects, data.contexts, strict=True):
        if y >= 0:
            counts[(subjects.index(s), contexts.index(c), *map(float, x), int(y))] += 1
    keys = sorted(counts)
    return {
        "x": np.asarray([k[2:-1] for k in keys]),
        "y": np.asarray([k[-1] for k in keys], dtype=int),
        "si": np.asarray([k[0] for k in keys], dtype=int),
        "ci": np.asarray([k[1] for k in keys], dtype=int),
        "counts": np.asarray([counts[k] for k in keys], dtype=int),
        "subjects": subjects,
        "contexts": contexts,
        "observed_trials": int(observed.sum()),
        "missing_reports": int((~observed).sum()),
    }


def ordinal_log_prob(
    eta: NDArray[np.float64], cut: float, y: NDArray[np.int64]
) -> NDArray[np.float64]:
    """Independent SciPy log probabilities in probit units; zero/positive cut, labels 0..2.

    Stable CDF or survival-CDF differences avoid cancellation in positive tails.
    This reference evaluator does not fit parameters or read evaluation data.
    """
    eta, y = np.asarray(eta, dtype=float), np.asarray(y)
    if eta.shape != y.shape or not np.isfinite(eta).all() or not np.isfinite(cut) or cut <= 0:
        raise ValueError("finite eta and strictly positive upper threshold required")
    if y.dtype.kind not in "iu" or np.any((y < 0) | (y > 2)):
        raise ValueError("observed integer report labels 0..2 required")
    result = np.empty_like(eta)
    result[y == 0] = log_ndtr(-eta[y == 0])
    result[y == 2] = log_ndtr(eta[y == 2] - cut)
    middle = eta[y == 1]
    lo, hi = -middle, cut - middle
    a = np.where(lo > 0, log_ndtr(-lo), log_ndtr(hi))
    b = np.where(lo > 0, log_ndtr(-hi), log_ndtr(lo))
    result[y == 1] = a + np.log(-np.expm1(b - a))
    return result


def reference_log_joint(
    grouped: dict[str, Any],
    beta: NDArray[np.float64],
    subject_z: NDArray[np.float64],
    context_z: NDArray[np.float64],
    variances: NDArray[np.float64],
    cut: float,
) -> float:
    """Normalized noncentered joint density for independent backend equivalence tests.

    Variances have InvGamma(shape=2, scale=1), raw effects N(0,1), beta N(0,2.5),
    and upper threshold N(1,2) truncated above zero. No log-transform Jacobians:
    evaluate PyMC with jacobian=False at the corresponding constrained values.
    """
    v = np.asarray(variances)
    if v.shape != (2,) or np.any(v <= 0) or cut <= 0:
        return -np.inf
    eta = (
        grouped["x"] @ beta
        + np.sqrt(v[0]) * subject_z[grouped["si"]]
        + np.sqrt(v[1]) * context_z[grouped["ci"]]
    )
    likelihood = np.dot(grouped["counts"], ordinal_log_prob(eta, cut, grouped["y"]))
    return float(
        likelihood
        + norm.logpdf(beta, scale=2.5).sum()
        + norm.logpdf(subject_z).sum()
        + norm.logpdf(context_z).sum()
        + invgamma.logpdf(v, a=2, scale=1).sum()
        + truncnorm.logpdf(cut, a=-0.5, b=np.inf, loc=1, scale=2)
    )


def build_model(data: OrdinalCalibration) -> tuple[Any, dict[str, Any]]:
    """Build an exact marginal likelihood and noncentered but prior-equivalent hierarchy.

    Supports the current common-threshold, three-category model only. No constraint
    is added to random effects (e.g. sum-to-zero would change the prior).
    PyMC is imported lazily so basic analysis environments remain unchanged.
    """
    import pymc as pm
    import pytensor.tensor as pt

    g = grouped_reports(data)
    with pm.Model() as model:
        beta = pm.Normal("beta", mu=0, sigma=2.5, shape=g["x"].shape[1])
        variances = pm.InverseGamma("variances", alpha=2, beta=1, shape=2)
        subject_z = pm.Normal("subject_z", mu=0, sigma=1, shape=len(g["subjects"]))
        context_z = pm.Normal("context_z", mu=0, sigma=1, shape=len(g["contexts"]))
        subject = pm.Deterministic("subject_effects", subject_z * pt.sqrt(variances[0]))
        context = pm.Deterministic("context_effects", context_z * pt.sqrt(variances[1]))
        cut = pm.TruncatedNormal("upper_threshold", mu=1, sigma=2, lower=0, initval=1.0)
        eta = pt.dot(g["x"], beta) + subject[g["si"]] + context[g["ci"]]
        logp = pm.logp(pm.OrderedProbit.dist(eta=eta, cutpoints=pt.stack([0.0, cut])), g["y"])
        pm.Potential("observed_report_likelihood", pt.sum(g["counts"] * logp))
    return model, g


def posterior_variables(
    posterior: dict[str, Any],
) -> tuple[dict[str, NDArray[np.float64]], list[str]]:
    """Flatten chain/draw arrays into named scalar traces; omit only the fixed-zero anchor.

    Names use effect indices, not participant identities. Unexpected constants remain
    visible in diagnostics rather than being silently treated as converged.
    """
    variables, fixed = {}, []
    shape = None
    names = ["beta", "subject_effects", "context_effects", "thresholds", "variances"]
    names.extend(name for name in ("subject_z", "context_z") if name in posterior)
    for name in names:
        values = np.asarray(posterior[name], dtype=float)
        if values.ndim < 3 or not np.isfinite(values).all():
            raise ValueError("finite chain/draw/parameter arrays required")
        if shape is None:
            shape = values.shape[:2]
        if values.shape[:2] != shape:
            raise ValueError("posterior chain/draw mismatch")
        for index in np.ndindex(values.shape[2:]):
            key = name + "[" + ",".join(map(str, index)) + "]"
            trace = values[(slice(None), slice(None), *index)]
            if name == "thresholds" and index[-1] == 0:
                if np.any(trace != 0):
                    raise ValueError("first report threshold must be fixed at zero")
                fixed.append(key)
            else:
                variables[key] = trace
    return variables, fixed


def arviz_diagnostics(posterior: dict[str, Any]) -> dict[str, Any]:
    """ArviZ rank R-hat, bulk/tail ESS and mean MCSE per parameter, not a scientific gate.

    Monte Carlo SE is in each parameter's native probit/probit-squared units. The
    underlying chains stay private on the server. Constants outside the fixed anchor
    are explicitly invalid diagnostics; passing these checks is not model validation.
    """
    import arviz as az

    variables, fixed = posterior_variables(posterior)
    rows = []
    for name, trace in variables.items():

        def finite(value: Any) -> float | None:
            number = float(np.asarray(value))
            return number if np.isfinite(number) else None

        row = {
            "parameter": name,
            "constant": bool(np.ptp(trace) == 0),
            "rhat": finite(az.rhat(trace, method="rank")),
            "ess_bulk": finite(az.ess(trace, method="bulk")),
            "ess_tail": finite(az.ess(trace, method="tail")),
            "mcse_mean": finite(az.mcse(trace, method="mean")),
            "chain_means": trace.mean(axis=1).tolist(),
            "chain_stds": trace.std(axis=1, ddof=1).tolist(),
            "chain_decile_means": [[float(x.mean()) for x in np.array_split(t, 10)] for t in trace],
        }
        rows.append(row)
    invalid = any(
        r["constant"] or any(r[k] is None for k in ("rhat", "ess_bulk", "ess_tail", "mcse_mean"))
        for r in rows
    )
    max_rhat = max((r["rhat"] for r in rows if r["rhat"] is not None), default=None)
    min_bulk = min((r["ess_bulk"] for r in rows if r["ess_bulk"] is not None), default=None)
    min_tail = min((r["ess_tail"] for r in rows if r["ess_tail"] is not None), default=None)
    return {
        "backend": "arviz",
        "version": az.__version__,
        "parameters": rows,
        "fixed_anchors": fixed,
        "max_rank_folded_split_rhat": max_rhat,
        "min_bulk_ess_estimate": min_bulk,
        "min_tail_ess": min_tail,
        "flags": {
            "invalid_diagnostics": invalid,
            "rhat_above_1_01": max_rhat is None or max_rhat > 1.01,
            "bulk_ess_below_400": min_bulk is None or min_bulk < 400,
            "tail_ess_below_400": min_tail is None or min_tail < 400,
        },
    }


def fit_ordinal_nuts(
    data: OrdinalCalibration,
    *,
    draws: int,
    warmup: int,
    chains: int,
    seed: int,
    cores: int,
    target_accept: float = 0.95,
) -> tuple[OrdinalPosterior, dict[str, Any], Any]:
    """Fit reserved calibration subjects with PyMC NUTS; return compatible probit posterior.

    Preserves the full original probability model. Divergences, tree-depth limits,
    BFMI and per-parameter diagnostics are recorded, never used to choose outcomes.
    """
    import arviz as az
    import pymc as pm

    if draws < 8 or warmup < 1 or chains < 2 or cores < 1 or not 0.8 <= target_accept < 1:
        raise ValueError("invalid fixed NUTS sampling settings")
    model, g = build_model(data)
    with model:
        idata = pm.sample(
            draws=draws,
            tune=warmup,
            chains=chains,
            cores=min(cores, chains),
            random_seed=seed,
            target_accept=target_accept,
            init="jitter+adapt_full",
            nuts_sampler="pymc",
            progressbar=False,
            return_inferencedata=True,
            idata_kwargs={"log_likelihood": False},
        )
    values = idata.posterior
    upper = values["upper_threshold"].values
    cuts = np.stack([np.zeros_like(upper), upper], axis=-1)[:, :, None, :]
    arrays = {
        k: values[k].values for k in ("beta", "subject_effects", "context_effects", "variances")
    }
    arrays["thresholds"] = cuts
    arrays.update({name: values[name].values for name in ("subject_z", "context_z")})
    diagnostic = arviz_diagnostics(arrays)
    diagnostic.update(
        divergences=int(idata.sample_stats["diverging"].values.sum()),
        max_tree_depth=int(idata.sample_stats["tree_depth"].values.max()),
        bfmi=np.asarray(az.bfmi(idata)).tolist(),
        observed_trials=g["observed_trials"],
        likelihood_terms=len(g["y"]),
        missing_reports=g["missing_reports"],
        pymc_version=pm.__version__,
        parameterization="noncentered_marginal_ordered_probit",
    )
    reached = idata.sample_stats.get("reached_max_treedepth")
    diagnostic["tree_depth_limit_events"] = (
        int(reached.values.sum()) if reached is not None else None
    )
    diagnostic["flags"].update(
        divergences=diagnostic["divergences"] > 0,
        low_bfmi=any(v < 0.3 or not np.isfinite(v) for v in diagnostic["bfmi"]),
        tree_depth_limit=diagnostic["tree_depth_limit_events"] is None
        or diagnostic["tree_depth_limit_events"] > 0,
    )
    legacy_summary = {
        k: diagnostic[k] for k in ("max_rank_folded_split_rhat", "min_bulk_ess_estimate")
    }
    posterior = OrdinalPosterior(
        arrays["beta"],
        arrays["subject_effects"],
        arrays["context_effects"],
        cuts,
        arrays["variances"],
        g["subjects"],
        g["contexts"],
        data.anchor_id,
        legacy_summary,
        False,
    )
    return posterior, diagnostic, idata
