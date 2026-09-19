"""Exact likelihood/prior checks and optional independent PyMC/ArviZ verification."""

from dataclasses import replace

import numpy as np
import pytest
from scipy.special import ndtr
from scipy.stats import invgamma, norm

from factorcon.models.report_measurement import OrdinalCalibration, chain_diagnostics
from factorcon.models.report_nuts import (
    arviz_diagnostics,
    build_model,
    grouped_reports,
    ordinal_log_prob,
    posterior_variables,
    reference_log_joint,
)


def fixture() -> OrdinalCalibration:
    """Small synthetic repeated-predictor fixture in fixed probit units, not participant data."""
    return OrdinalCalibration(
        np.column_stack([np.ones(24), np.tile([-1.0, 0.0, 1.0], 8)]),
        np.tile([0, 1, 2, 1, 0, 2], 4),
        tuple(f"fixture:s{i // 6}" for i in range(24)),
        tuple(f"fixture:c{i % 2}" for i in range(24)),
        3,
        "fixture",
    )


def test_counted_likelihood_is_exact_and_missing_does_not_enter():
    data = fixture()
    data = replace(
        data,
        design=np.vstack([data.design, data.design[:6], [1.0, 99.0]]),
        reports=np.r_[data.reports, data.reports[:6], -1],
        subjects=(*data.subjects, *data.subjects[:6], "unobserved:subject"),
        contexts=(*data.contexts, *data.contexts[:6], "unobserved:context"),
    )
    g = grouped_reports(data)
    assert g["counts"].sum() == 30 and g["missing_reports"] == 1
    assert len(g["y"]) < 30 and "unobserved:subject" not in g["subjects"]
    beta = np.array([0.2, 0.4])
    us = np.arange(4) * 0.2
    uc = np.array([-0.1, 0.2])
    grouped_eta = g["x"] @ beta + us[g["si"]] + uc[g["ci"]]
    eta = (
        data.design[:-1] @ beta
        + np.array([us[g["subjects"].index(s)] for s in data.subjects[:-1]])
        + np.array([uc[g["contexts"].index(c)] for c in data.contexts[:-1]])
    )
    np.testing.assert_allclose(
        np.dot(g["counts"], ordinal_log_prob(grouped_eta, 1.1, g["y"])),
        ordinal_log_prob(eta, 1.1, data.reports[:-1]).sum(),
        atol=1e-12,
    )


def test_log_prob_normalization_and_extreme_tails():
    eta = np.linspace(-10, 10, 41)
    probabilities = np.column_stack(
        [np.exp(ordinal_log_prob(eta, 1.2, np.full(41, k))) for k in range(3)]
    )
    np.testing.assert_allclose(probabilities.sum(axis=1), 1, atol=1e-14)
    np.testing.assert_allclose(probabilities[:, 0], ndtr(-eta), atol=1e-15)
    assert np.isfinite(
        ordinal_log_prob(np.array([-100.0, 100.0]), 1.0, np.ones(2, dtype=int))
    ).all()
    with pytest.raises(ValueError):
        ordinal_log_prob(np.ones(1), -1, np.ones(1, dtype=int))
    with pytest.raises(ValueError):
        ordinal_log_prob(np.ones(1), 1, np.ones(1) * 0.5)


def test_noncentering_preserves_conditional_prior_including_jacobian():
    z = np.array([-0.3, 0.7, 1.2])
    v = 0.6
    effects = np.sqrt(v) * z
    centered = norm.logpdf(effects, scale=np.sqrt(v)).sum() + invgamma.logpdf(v, a=2, scale=1)
    noncentered = norm.logpdf(z).sum() + invgamma.logpdf(v, a=2, scale=1)
    np.testing.assert_allclose(centered + len(z) * np.log(np.sqrt(v)), noncentered)


def trace_fixture() -> dict:
    """Synthetic chain arrays; a constant non-anchor must not disappear from diagnostics."""
    rng = np.random.default_rng(11)
    return {
        "beta": rng.normal(size=(4, 400, 2)),
        "subject_effects": rng.normal(size=(4, 400, 2)),
        "context_effects": rng.normal(size=(4, 400, 1)),
        "variances": rng.lognormal(size=(4, 400, 2)),
        "thresholds": np.stack([np.zeros((4, 400)), rng.lognormal(size=(4, 400))], axis=-1)[
            :, :, None, :
        ],
    }


def test_only_fixed_anchor_omitted_and_shape_checked():
    data = trace_fixture()
    data["beta"][:, :, 1] = 0
    traces, fixed = posterior_variables(data)
    assert "beta[1]" in traces and fixed == ["thresholds[0,0]"]
    data["thresholds"][:, :, :, 0] = 1
    with pytest.raises(ValueError, match="fixed at zero"):
        posterior_variables(data)


def test_arviz_checks_legacy_rhat_and_flags_stuck_parameter():
    az = pytest.importorskip("arviz")
    data = trace_fixture()
    traces, _ = posterior_variables(data)
    values = np.stack(list(traces.values()), axis=-1)
    legacy = chain_diagnostics(values)
    result = arviz_diagnostics(data)
    np.testing.assert_allclose(
        result["max_rank_folded_split_rhat"], legacy["max_rank_folded_split_rhat"], atol=1e-12
    )
    assert result["version"] == az.__version__
    assert abs(result["min_bulk_ess_estimate"] / legacy["min_bulk_ess_estimate"] - 1) < 0.1
    data["beta"][:, :, 1] = 0
    assert arviz_diagnostics(data)["flags"]["invalid_diagnostics"]


def test_pymc_joint_and_gradient_equal_independent_reference():
    pytest.importorskip("pymc")
    model, g = build_model(fixture())
    logp = model.compile_logp(jacobian=False)
    logp_jac = model.compile_logp(jacobian=True)
    gradient = model.compile_dlogp()
    rng = np.random.default_rng(260831)
    for _ in range(5):
        beta = rng.normal(size=2)
        sz = rng.normal(size=4)
        cz = rng.normal(size=2)
        v = rng.lognormal(size=2)
        cut = float(rng.uniform(0.2, 3))
        point = {
            "beta": beta,
            "subject_z": sz,
            "context_z": cz,
            "variances_log__": np.log(v),
            "upper_threshold_interval__": np.log(cut),
        }
        reference = reference_log_joint(g, beta, sz, cz, v, cut)
        np.testing.assert_allclose(logp(point), reference, atol=1e-8)
        np.testing.assert_allclose(
            logp_jac(point), reference + np.log(v).sum() + np.log(cut), atol=1e-8
        )
        numerical = []
        for variable in model.value_vars:
            name = variable.name
            for index in np.ndindex(np.shape(point[name])):
                plus = {k: np.array(x, copy=True) for k, x in point.items()}
                minus = {k: np.array(x, copy=True) for k, x in point.items()}
                plus[name][index] += 1e-5
                minus[name][index] -= 1e-5
                numerical.append((logp_jac(plus) - logp_jac(minus)) / 2e-5)
        np.testing.assert_allclose(gradient(point), numerical, rtol=1e-5, atol=1e-5)
