"""Hierarchical ordinal-probit report measurement with posterior uncertainty.

The anchor is probability of a report liability exceeding the first threshold. It is
NOT probability of consciousness, a universal E scale, or a validation of reports as
ground truth. Neural evaluation subjects must be disjoint from calibration subjects.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import cho_factor, cho_solve, solve_triangular
from scipy.special import ndtr, ndtri
from scipy.stats import rankdata, truncnorm


@dataclass(frozen=True)
class OrdinalCalibration:
    """Fixed-unit report predictors; rows=trials, reports 0..K-1 or -1=missing.

    The design includes one intercept and externally fixed covariate units. IDs are
    globally namespaced. Contexts can encode site/instrument; no neural features may
    be used. Non-report rows are marginalized, not assigned lowest-category labels.
    """

    design: NDArray[np.float64]
    reports: NDArray[np.int64]
    subjects: tuple[str, ...]
    contexts: tuple[str, ...]
    categories: int
    anchor_id: str

    def validate(self) -> None:
        """Validate ordinal codes and fixed design without fitting or neural access."""
        n = len(self.reports)
        if self.design.ndim != 2 or self.design.shape[0] != n or self.design.shape[1] < 1:
            raise ValueError("design requires trial rows and an intercept column")
        if not n or not np.isfinite(self.design).all() or not np.all(self.design[:, 0] == 1):
            raise ValueError("finite nonempty fixed-unit design, first column all ones required")
        if self.reports.shape != (n,) or self.reports.dtype.kind not in "iu":
            raise ValueError("reports must be integer category codes; -1 means missing")
        if self.categories < 2 or np.any((self.reports < -1) | (self.reports >= self.categories)):
            raise ValueError("invalid ordinal category")
        if len(self.subjects) != n or len(self.contexts) != n or not self.anchor_id:
            raise ValueError("one subject/context per trial and a declared anchor required")
        if any(not s for s in (*self.subjects, *self.contexts)):
            raise ValueError("empty subject/context identifier")
        if not np.any(self.reports >= 0):
            raise ValueError("no observed reports: calibration not estimable")


@dataclass(frozen=True)
class OrdinalPosterior:
    """Chains x draws x parameters, with fixed latent residual SD=1 probit units.

    Normal beta prior SD=2.5; subject/context variances have InvGamma(2,1)
    priors (probit-squared units). First threshold fixed zero, subsequent ordered
    thresholds have N(index, 2^2) priors restricted to the ordered region.
    """

    beta: NDArray[np.float64]
    subject_effects: NDArray[np.float64]
    context_effects: NDArray[np.float64]
    thresholds: NDArray[np.float64]
    variances: NDArray[np.float64]
    subject_levels: tuple[str, ...]
    context_levels: tuple[str, ...]
    anchor_id: str
    diagnostics: dict[str, float]
    context_specific_thresholds: bool = False


def chain_diagnostics(values: NDArray[np.float64]) -> dict[str, float]:
    """Rank/folded split R-hat and initial-positive-sequence bulk ESS estimates.

    Input chains x retained draws x parameters. These are convergence diagnostics,
    not proof of identifiability, coverage, or adequate tail Monte Carlo precision.
    """
    if values.ndim != 3 or values.shape[0] < 2 or values.shape[1] < 8:
        raise ValueError(">=2 chains and >=8 draws per chain required")
    if not np.isfinite(values).all():
        raise ValueError("nonfinite posterior draws")
    half = values.shape[1] // 2
    split = np.concatenate([values[:, :half], values[:, -half:]], axis=0)
    rhats, esses = [], []
    for index in range(split.shape[2]):
        raw = split[:, :, index]
        if np.ptp(raw) == 0:
            continue
        normalized = None
        for candidate in (raw, np.abs(raw - np.median(raw))):
            ranks = rankdata(candidate.ravel()).reshape(candidate.shape)
            z = ndtri((ranks - 0.375) / (candidate.size + 0.25))
            w = np.var(z, axis=1, ddof=1).mean()
            b = half * np.var(z.mean(axis=1), ddof=1)
            variance = (half - 1) / half * w + b / half
            rhats.append(float(np.sqrt(variance / w)) if w > 0 else float("inf"))
            if normalized is None:
                normalized = (z, w, variance)
        z, w, variance = normalized
        centered = z - z.mean(axis=1, keepdims=True)
        rho = [1.0]
        for lag in range(1, half):
            acov = np.mean(np.sum(centered[:, :-lag] * centered[:, lag:], axis=1) / half)
            rho.append(1 - (w - acov) / variance)
        pairs = []
        for lag in range(0, len(rho) - 1, 2):
            pair = rho[lag] + rho[lag + 1]
            if pair <= 0:
                break
            pairs.append(min(pair, pairs[-1]) if pairs else pair)
        tau = max(-1 + 2 * sum(pairs), 1.0)
        esses.append(float(z.size / tau))
    return {
        "max_rank_folded_split_rhat": max(rhats, default=1.0),
        "min_bulk_ess_estimate": min(esses, default=float(split.shape[0] * half)),
    }


def fit_ordinal(
    data: OrdinalCalibration,
    *,
    draws: int = 1000,
    warmup: int = 1000,
    chains: int = 4,
    seed: int = 260830,
    context_specific_thresholds: bool = False,
) -> OrdinalPosterior:
    """Gibbs sample latent reports, regression, random effects, variances and thresholds.

    Only observed calibration reports enter the likelihood. No neural outcomes or
    evaluation subjects are accepted here; collection-level overlap is checked by the
    pattern pipeline. Units are fixed probit-liability units, not fold-standardized data.
    """
    data.validate()
    if draws < 8 or warmup < 0 or chains < 2:
        raise ValueError(">=8 retained draws, >=2 chains and nonnegative warmup required")
    observed = data.reports >= 0
    x, y = data.design[observed], data.reports[observed]
    subjects = tuple(sorted({s for s, keep in zip(data.subjects, observed, strict=True) if keep}))
    contexts = tuple(sorted({s for s, keep in zip(data.contexts, observed, strict=True) if keep}))
    si = np.asarray(
        [subjects.index(s) for s, keep in zip(data.subjects, observed, strict=True) if keep]
    )
    ci = np.asarray(
        [contexts.index(s) for s, keep in zip(data.contexts, observed, strict=True) if keep]
    )
    p, ns, nc = x.shape[1], len(subjects), len(contexts)
    design = np.column_stack([x, np.eye(ns)[si], np.eye(nc)[ci]])
    cross = design.T @ design
    parameters = np.empty((chains, draws, design.shape[1]))
    threshold_contexts = nc if context_specific_thresholds else 1
    threshold_index = ci if context_specific_thresholds else np.zeros(len(ci), dtype=int)
    thresholds = np.empty((chains, draws, threshold_contexts, data.categories - 1))
    variances = np.empty((chains, draws, 2))
    for chain, stream in enumerate(np.random.SeedSequence(seed).spawn(chains)):
        rng = np.random.default_rng(stream)
        coef = rng.normal(0, 0.25, design.shape[1])
        cuts = np.tile(np.arange(data.categories - 1, dtype=float), (threshold_contexts, 1))
        var = np.ones(2)
        for step in range(warmup + draws):
            mu = design @ coef
            bounds = np.column_stack(
                [np.full(threshold_contexts, -np.inf), cuts, np.full(threshold_contexts, np.inf)]
            )
            z = truncnorm.rvs(
                bounds[threshold_index, y] - mu,
                bounds[threshold_index, y + 1] - mu,
                loc=mu,
                random_state=rng,
            )
            prior_precision = np.r_[
                np.full(p, 1 / 2.5**2), np.full(ns, 1 / var[0]), np.full(nc, 1 / var[1])
            ]
            precision = cho_factor(cross + np.diag(prior_precision), lower=True)
            mean = cho_solve(precision, design.T @ z)
            coef = mean + solve_triangular(precision[0].T, rng.normal(size=len(mean)), lower=False)
            for j, effects in enumerate((coef[p : p + ns], coef[p + ns :])):
                var[j] = 1 / rng.gamma(2 + len(effects) / 2, 1 / (1 + np.sum(effects**2) / 2))
            for context in range(threshold_contexts):
                mask = threshold_index == context
                for j in range(1, cuts.shape[1]):
                    low = max(cuts[context, j - 1], float(z[mask & (y == j)].max(initial=-np.inf)))
                    high = min(
                        cuts[context, j + 1] if j + 1 < cuts.shape[1] else np.inf,
                        float(z[mask & (y == j + 1)].min(initial=np.inf)),
                    )
                    cuts[context, j] = truncnorm.rvs(
                        (low - j) / 2, (high - j) / 2, loc=j, scale=2, random_state=rng
                    )
            if step >= warmup:
                parameters[chain, step - warmup] = coef
                thresholds[chain, step - warmup] = cuts
                variances[chain, step - warmup] = var
    diagnostics = chain_diagnostics(
        np.concatenate([parameters, thresholds.reshape(chains, draws, -1), variances], axis=2)
    )
    return OrdinalPosterior(
        parameters[:, :, :p],
        parameters[:, :, p : p + ns],
        parameters[:, :, p + ns :],
        thresholds,
        variances,
        subjects,
        contexts,
        data.anchor_id,
        diagnostics,
        context_specific_thresholds,
    )


def predict_reports(
    posterior: OrdinalPosterior,
    design: NDArray[np.float64],
    *,
    subjects: tuple[str, ...],
    contexts: tuple[str, ...],
    seed: int = 260831,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return draw x row operational E and draw x row x category probabilities.

    New subject/context effects are posterior-predictive draws shared across that
    entity's rows. No held-out reports update coefficients, variances or thresholds.
    Mapping probabilities to neural conditions must average *within each draw*.
    """
    if (
        design.ndim != 2
        or design.shape[1] != posterior.beta.shape[2]
        or not np.isfinite(design).all()
        or not np.all(design[:, 0] == 1)
        or len(subjects) != len(design)
        or len(contexts) != len(design)
    ):
        raise ValueError("incompatible fixed-unit prediction design/IDs")
    beta = posterior.beta.reshape(-1, posterior.beta.shape[-1])
    variance = posterior.variances.reshape(-1, 2)
    eta = beta @ design.T
    rng = np.random.default_rng(seed)
    for j, (ids, levels, effects) in enumerate(
        (
            (subjects, posterior.subject_levels, posterior.subject_effects),
            (contexts, posterior.context_levels, posterior.context_effects),
        )
    ):
        known = effects.reshape(len(beta), len(levels))
        for identifier in sorted(set(ids)):
            effect = (
                known[:, levels.index(identifier)]
                if identifier in levels
                else (rng.normal(size=len(beta)) * np.sqrt(variance[:, j]))
            )
            eta[:, np.asarray(ids) == identifier] += effect[:, None]
    cuts = posterior.thresholds.reshape(len(beta), *posterior.thresholds.shape[2:])
    if posterior.context_specific_thresholds:
        if set(contexts) - set(posterior.context_levels):
            raise ValueError(
                "context-specific thresholds cannot transfer to an uncalibrated context"
            )
        index = [posterior.context_levels.index(c) for c in contexts]
    else:
        index = [0] * len(contexts)
    cdf = ndtr(cuts[:, index, :] - eta[:, :, None])
    probabilities = np.diff(
        np.concatenate([np.zeros((*eta.shape, 1)), cdf, np.ones((*eta.shape, 1))], axis=2), axis=2
    )
    return ndtr(eta), probabilities


def missingness_sensitivity(
    probabilities: NDArray[np.float64], missing: NDArray[np.bool_], log_odds_shift: float
) -> NDArray[np.float64]:
    """Pattern-mixture sensitivity on missing rows only; never an estimated correction.

    Input draw x row probabilities in [0,1], missing row flags, and a declared log-odds
    shift. Zero shift is the baseline missing-at-random prediction, not proof of MAR.
    """
    from scipy.special import expit, logit

    if (
        probabilities.ndim != 2
        or missing.dtype.kind != "b"
        or missing.shape != (probabilities.shape[1],)
        or not np.isfinite(probabilities).all()
        or not np.isfinite(log_odds_shift)
        or np.any((probabilities < 0) | (probabilities > 1))
    ):
        raise ValueError("finite draw-row probabilities and boolean row missingness required")
    result = probabilities.copy()
    result[:, missing] = expit(logit(result[:, missing]) + log_odds_shift)
    return result


def report_invariance_check(
    train: OrdinalCalibration,
    test: OrdinalCalibration,
    *,
    draws: int = 1000,
    warmup: int = 1000,
    chains: int = 4,
    seed: int = 260830,
) -> dict[str, object]:
    """Compare common/context-specific thresholds on disjoint calibration subjects.

    Retains both models and subject-level joint predictive nats; does not select a
    universal E scale or assert invariance from a nonsignificant comparison. All test
    contexts must be represented in training, including observed report information.
    """
    from scipy.special import logsumexp

    train.validate()
    test.validate()
    if set(train.subjects) & set(test.subjects):
        raise ValueError("invariance test requires disjoint train/test subjects")
    if train.categories != test.categories or train.anchor_id != test.anchor_id:
        raise ValueError("same instrument categories and operational anchor required")
    observed_contexts = {c for c, y in zip(train.contexts, train.reports, strict=True) if y >= 0}
    if set(test.contexts) - observed_contexts:
        raise ValueError("unseen contexts: comparative calibration not estimable")
    models = []
    for varying in (False, True):
        posterior = fit_ordinal(
            train,
            draws=draws,
            warmup=warmup,
            chains=chains,
            seed=seed,
            context_specific_thresholds=varying,
        )
        _, probability = predict_reports(
            posterior, test.design, subjects=test.subjects, contexts=test.contexts, seed=seed + 1
        )
        scores = []
        for subject in sorted(set(test.subjects)):
            mask = (np.asarray(test.subjects) == subject) & (test.reports >= 0)
            if not np.any(mask):
                scores.append({"subject": subject, "status": "no_observed_reports"})
                continue
            # Conditional trials share each posterior draw and subject effect.
            selected = probability[:, mask, :][:, np.arange(mask.sum()), test.reports[mask]]
            with np.errstate(divide="ignore"):
                joint = np.log(selected).sum(axis=1)
            value = float(logsumexp(joint) - np.log(len(joint)))
            scores.append(
                {
                    "subject": subject,
                    "status": "scored",
                    "joint_nats": value,
                    "observed_reports": int(mask.sum()),
                }
            )
        models.append(
            {
                "context_specific_thresholds": varying,
                "scores": scores,
                "diagnostics": posterior.diagnostics,
            }
        )
    return {
        "models": models,
        "universal_scale_validated": False,
        "all_calibration_subjects": sorted(set(train.subjects) | set(test.subjects)),
        "scope": "held_out_report_instrument_prediction_not_causal_experience",
    }
