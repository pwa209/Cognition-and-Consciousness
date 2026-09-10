"""Fitted representational architectures with a repeated-partition Gaussian likelihood.

This is a separate, versioned implementation from the historical RDM proxies.
The distribution integrates random neural loadings, not architectural parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import cho_factor, cho_solve, helmert
from scipy.optimize import minimize
from scipy.special import expit, logsumexp

from factorcon.models.architectures import CONSTRUCT_ORDER, K_NAMES, unavailable_reason


class OptimizationFailure(ValueError):
    """Numerical failure retaining every multistart diagnostic, without a fake score."""

    def __init__(self, diagnostics: tuple[dict[str, Any], ...]) -> None:
        super().__init__("all generative optimizer starts failed; no scientific score emitted")
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class PatternData:
    """One family in common calibrated units, with independently whitened features.

    Patterns: independent groups x partitions x conditions x features. Design:
    draws x conditions x named constructs. Sensory: conditions x fixed covariates.
    Noise: partition-condition x partition-condition covariance, known up to scale
    from design/independent calibration, never estimated on evaluation outcomes.
    Design draws must come from fixed design or calibration disjoint from ALL neural
    groups. Group IDs must be globally namespaced across families. E is in [0,1].
    """

    family: str
    group_ids: tuple[str, ...]
    names: tuple[str, ...]
    patterns: NDArray[np.float64]
    design_draws: NDArray[np.float64]
    sensory: NDArray[np.float64]
    noise: NDArray[np.float64]
    anchor_id: str
    calibration_ids: tuple[str, ...] = ()
    group_weights: NDArray[np.float64] | None = None

    def validate(self) -> None:
        """Check shapes, probability units, unique groups and calibration separation."""
        y, x = self.patterns, self.design_draws
        if y.ndim != 4 or min(y.shape) < 1 or y.shape[1] < 2 or y.shape[2] < 3:
            raise ValueError("patterns require groups, >=2 partitions, >=3 conditions, features")
        if len(self.group_ids) != len(y) or len(set(self.group_ids)) != len(y):
            raise ValueError("one unique independent group ID per pattern block required")
        if self.group_weights is not None and (
            self.group_weights.shape != (len(y),)
            or not np.isfinite(self.group_weights).all()
            or np.any(self.group_weights <= 0)
        ):
            raise ValueError("group bootstrap weights must be finite and positive")
        if any(not i.strip() for i in self.group_ids) or not self.family or not self.anchor_id:
            raise ValueError("family, anchor and group identifiers must be non-empty")
        if set(self.group_ids) & set(self.calibration_ids):
            raise ValueError("calibration/neural group overlap")
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or set(self.names) - set(CONSTRUCT_ORDER)
        ):
            raise ValueError("unique known construct names required")
        if "S" in self.names:
            raise ValueError("sensory covariates belong in sensory, not scalar S coding")
        if x.ndim != 3 or not len(x) or x.shape[1:] != (y.shape[2], len(self.names)):
            raise ValueError("design_draws must be draws x conditions x named constructs")
        if self.sensory.ndim != 2 or self.sensory.shape[0] != y.shape[2]:
            raise ValueError("sensory must be conditions x covariates")
        if self.noise.shape != (y.shape[1] * y.shape[2],) * 2:
            raise ValueError("noise covariance has incompatible partition-condition dimensions")
        if not all(np.isfinite(v).all() for v in (y, x, self.sensory, self.noise)):
            raise ValueError("all numerical inputs must be finite")
        if not np.allclose(self.noise, self.noise.T):
            raise ValueError("noise covariance must be symmetric")
        np.linalg.cholesky(self.noise)
        if "E" in self.names:
            e = x[:, :, self.names.index("E")]
            if np.any((e < 0) | (e > 1)):
                raise ValueError("E must use the declared operational probability scale [0,1]")

    def subset(self, indices: NDArray[np.int64]) -> PatternData:
        """Select entire groups only; no fitting, preserving all physical units."""
        return replace(
            self,
            group_ids=tuple(self.group_ids[i] for i in indices),
            patterns=self.patterns[indices].copy(),
            group_weights=None
            if self.group_weights is None
            else self.group_weights[indices].copy(),
        )


@dataclass(frozen=True)
class ModelShape:
    """Shared parameter layout; absent constructs are structural omissions, not E=0."""

    architecture: str
    names: tuple[str, ...]
    interactions: tuple[tuple[str, str], ...] = ()
    unitary_rank: int = 1
    gate_floor: float = 0.0
    report_leak: float = 0.1
    condition_count: int = 0

    def __post_init__(self) -> None:
        """Validate outcome-independent model choices and dimensionless constraints."""
        if self.architecture not in {f"M{i}" for i in range(6)}:
            raise ValueError("unknown architecture")
        if not self.names or len(set(self.names)) != len(self.names):
            raise ValueError("unique nonempty names required")
        if set(self.names) - (set(CONSTRUCT_ORDER) - {"S"}):
            raise ValueError("unknown construct")
        if self.unitary_rank not in (1, 2):
            raise ValueError("unitary rank must be the declared 1 or 2 sensitivity")
        if not 0 <= self.gate_floor < 1 or not 0 <= self.report_leak <= 1:
            raise ValueError("invalid gate floor/report leakage")
        if any(
            left not in self.names or right not in self.names for left, right in self.interactions
        ):
            raise ValueError("interaction refers to absent construct")
        if len(set(self.interactions)) != len(self.interactions):
            raise ValueError("duplicate interaction")
        if self.architecture == "M5" and self.condition_count < 3:
            raise ValueError("free covariance needs >=3 fixed conditions")

    @property
    def labels(self) -> tuple[str, ...]:
        """Return dimensionless parameter labels, independent of neural observations."""
        q = len(self.names)
        k = [n for n in self.names if n in K_NAMES]
        if self.architecture == "M0":
            core = [f"loading:{n}:{j}" for n in self.names for j in range(self.unitary_rank)]
        elif self.architecture == "M1":
            core = ["gate_offset", "gate_log_slope"] + [f"log_weight:{n}" for n in self.names]
        elif self.architecture == "M2":
            core = [f"access:{n}" for n in k] + ["E_on_access", "E_on_A", "A_loading", "R_loading"]
        elif self.architecture == "M3":
            core = [f"report:{n}" for n in self.names] + [f"leak:{n}" for n in self.names]
        elif self.architecture == "M4":
            q += len(self.interactions)
            core = [f"L:{i}:{j}" for i in range(q) for j in range(i + 1)]
        else:
            q = self.condition_count - 1
            core = [f"free_L:{i}:{j}" for i in range(q) for j in range(i + 1)]
        return (*core, "log_sensory", "log_noise")


def signal_covariance(
    shape: ModelShape, theta: NDArray[np.float64], data: PatternData, draw: int = 0
) -> NDArray[np.float64]:
    """Generate conditions-squared covariance in standardized feature-squared units.

    M0 learns signed rank-one (or declared rank-two sensitivity) loadings. M1 fits a
    monotone E gate with exact zero at E=0 when gate_floor=0. M2 places the E loading
    in the learned access/A span. M3 allows shrunk main effects, not absent effects.
    M4 fits a Cholesky construct covariance, permitting correlated neural directions.
    All candidates include the identical sensory covariance term.
    """
    if theta.shape != (len(shape.labels),):
        raise ValueError("parameter shape mismatch")
    x = np.zeros((data.patterns.shape[2], len(shape.names)))
    for j, name in enumerate(shape.names):
        if name in data.names:
            x[:, j] = data.design_draws[draw, :, data.names.index(name)]
    columns = {n: x[:, i] for i, n in enumerate(shape.names)}
    zero = np.zeros(len(x))
    e, a, r = (columns.get(n, zero) for n in ("E", "A", "R"))
    core = theta[:-2]
    if shape.architecture == "M0":
        features = x @ core.reshape(len(shape.names), shape.unitary_rank)
    elif shape.architecture == "M1":
        offset, slope = core[0], np.exp(core[1])
        low, high = expit(offset), expit(offset + slope)
        gate = (expit(offset + slope * e) - low) / max(high - low, 1e-12)
        gate = shape.gate_floor + (1 - shape.gate_floor) * gate
        features = np.column_stack(
            [columns[n] * (gate if n in K_NAMES else 1) for n in shape.names]
        )
        features *= np.exp(core[2:] / 2)
    elif shape.architecture == "M2":
        ks = [columns[n] for n in shape.names if n in K_NAMES]
        access_weights = core[: len(ks)]
        access = np.column_stack(ks) @ access_weights
        e_access, e_a, a_loading, r_loading = core[len(ks) :]
        features = np.column_stack(
            [
                access + e_access * np.linalg.norm(access_weights) * e,
                a_loading * (a + e_a * e),
                r_loading * r,
            ]
        )
        # If A is absent, E cannot acquire a second, unconstrained direction.
        if "A" not in data.names:
            features[:, 1] = 0
    elif shape.architecture == "M3":
        main = np.column_stack([r if n == "R" else columns[n] * r for n in shape.names])
        features = np.column_stack(
            [main * core[: len(shape.names)], shape.report_leak * x * core[len(shape.names) :]]
        )
    elif shape.architecture == "M4":
        expanded = np.column_stack(
            [x, *[columns[left] * columns[right] for left, right in shape.interactions]]
        )
        chol = np.zeros((expanded.shape[1],) * 2)
        chol[np.tril_indices(len(chol))] = core
        features = expanded @ chol
    else:
        if shape.condition_count != len(x):
            raise ValueError("M5 requires unchanged condition identities and order")
        chol = np.zeros((len(x) - 1,) * 2)
        chol[np.tril_indices(len(chol))] = core
        features = helmert(len(x)).T @ chol
    return features @ features.T + np.exp(theta[-2]) * (data.sensory @ data.sensory.T)


def pattern_log_density(
    data: PatternData, signal: NDArray[np.float64], noise_variance: float
) -> NDArray[np.float64]:
    """Joint Gaussian log density per group in condition-contrast/whitened units.

    Repeated partitions share the same random neural pattern. Helmert projection
    removes per-partition feature baselines without fitting test-dependent covariance.
    Channel independence is an explicit whitening assumption, not an inferred fact.
    """
    groups, partitions, conditions, features = data.patterns.shape
    if (
        signal.shape != (conditions, conditions)
        or not np.isfinite(signal).all()
        or not np.allclose(signal, signal.T)
    ):
        raise ValueError("signal covariance must be symmetric conditions x conditions")
    if not np.isfinite(noise_variance) or noise_variance <= 0:
        raise ValueError("positive finite noise variance required")
    if np.linalg.eigvalsh(signal).min() < -1e-8:
        raise ValueError("signal covariance must be positive semidefinite")
    projection = np.kron(np.eye(partitions), helmert(conditions))
    covariance = (
        projection
        @ (np.kron(np.ones((partitions, partitions)), signal) + noise_variance * data.noise)
        @ projection.T
    )
    chol = cho_factor(covariance, lower=True)
    logdet = 2 * np.log(np.diag(chol[0])).sum()
    projected = np.einsum("ij,njf->nif", projection, data.patterns.reshape(groups, -1, features))
    scores = []
    for y in projected:
        scores.append(
            -0.5
            * (
                features * (logdet + len(covariance) * np.log(2 * np.pi))
                + np.sum(y * cho_solve(chol, y))
            )
        )
    return np.asarray(scores)


@dataclass(frozen=True)
class GenerativeFit:
    """Training-only penalized maximum-likelihood fit; not a Bayesian posterior."""

    shape: ModelShape
    theta: NDArray[np.float64]
    penalty: float
    training_families: tuple[str, ...]
    objective: float
    starts: tuple[dict[str, Any], ...]
    anchor_id: str | None = None


def predictive_scores(fit: GenerativeFit, data: PatternData) -> NDArray[np.float64]:
    """Integrate calibrated design draws with log-mean-exp, returning joint nats/group.

    Neither fitted parameters nor preprocessing are changed by held-out observations.
    The density is conditional on fitted architecture parameters and external calibration.
    """
    if fit.anchor_id is not None and fit.anchor_id != data.anchor_id:
        raise ValueError("predictive anchors differ from training")
    if set(data.names) - set(fit.shape.names):
        raise ValueError("target has constructs absent from fitted parameter layout")
    if (
        fit.shape.architecture == "M5"
        and fit.training_families
        and data.family not in fit.training_families
    ):
        raise ValueError("M5 condition identities cannot transfer between families")
    values = np.stack(
        [
            pattern_log_density(
                data, signal_covariance(fit.shape, fit.theta, data, d), np.exp(fit.theta[-1])
            )
            for d in range(len(data.design_draws))
        ]
    )
    return logsumexp(values, axis=0) - np.log(len(values))


def fit_generative(
    datasets: tuple[PatternData, ...],
    shape: ModelShape,
    *,
    penalty: float,
    starts: int = 4,
    max_iter: int = 500,
    seed: int = 260830,
) -> GenerativeFit:
    """Fit source families with equal-family, equal-group normalized likelihood.

    Penalty is selected only by an enclosing grouped CV. Every initialization is
    recorded; only converged finite optima compete. No scientific sign or score gate.
    """
    if not datasets or penalty < 0 or not np.isfinite(penalty) or starts < 1:
        raise ValueError("datasets, nonnegative penalty, and positive start count required")
    ids = [g for data in datasets for g in data.group_ids]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate independent groups across source families")
    if set(ids) & {g for data in datasets for g in data.calibration_ids}:
        raise ValueError("calibration overlaps a neural group in another family")
    if shape.architecture == "M5" and len(datasets) != 1:
        raise ValueError("M5 is within-family only; condition identities do not transfer")
    for data in datasets:
        data.validate()
        if set(data.names) - set(shape.names):
            raise ValueError("source constructs absent from model parameter layout")
        reason = unavailable_reason(shape.architecture, dict.fromkeys(data.names))
        if reason:
            raise ValueError(reason)
    if len({data.anchor_id for data in datasets}) != 1:
        raise ValueError("common externally defined measurement/feature anchors required")
    rng = np.random.default_rng(seed)
    results = []

    def objective(theta: NDArray[np.float64]) -> float:
        fit = GenerativeFit(shape, theta, penalty, (), 0, ())
        losses = []
        for data in datasets:
            dimensions = (
                np.prod(data.patterns.shape[1:]) - data.patterns.shape[1] * data.patterns.shape[3]
            )
            losses.append(
                -np.average(predictive_scores(fit, data), weights=data.group_weights) / dimensions
            )
        # All architecture parameters regularized; shared sensory/noise scales excluded.
        return float(np.mean(losses) + penalty * np.sum(theta[:-2] ** 2))

    for _index in range(starts):
        initial = rng.normal(0, 0.25, len(shape.labels))
        initial[-2:] = [-2.0, 0.0]
        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            bounds=[(-5.0, 5.0)] * (len(initial) - 2) + [(-12, 8), (-12, 8)],
            options={"maxiter": max_iter, "ftol": 1e-10, "maxls": 30},
        )
        results.append(result)
    converged = [r for r in results if r.success and np.isfinite(r.fun)]
    diagnostics = tuple(
        {
            "success": bool(r.success),
            "objective": float(r.fun) if np.isfinite(r.fun) else None,
            "iterations": int(r.nit),
            "message": str(r.message),
        }
        for r in results
    )
    if not converged:
        raise OptimizationFailure(diagnostics)
    best = min(converged, key=lambda r: r.fun)
    return GenerativeFit(
        shape,
        best.x.copy(),
        penalty,
        tuple(d.family for d in datasets),
        float(best.fun),
        diagnostics,
        datasets[0].anchor_id,
    )
