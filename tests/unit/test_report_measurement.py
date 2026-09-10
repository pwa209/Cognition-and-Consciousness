"""Small deterministic posterior checks, not large-scale coverage certification."""

from dataclasses import replace

import numpy as np
import pytest

from factorcon.models.report_measurement import (
    OrdinalCalibration,
    chain_diagnostics,
    fit_ordinal,
    missingness_sensitivity,
    predict_reports,
    report_invariance_check,
)


def calibration():
    x = np.column_stack([np.ones(60), np.tile([-1.0, 0.0, 1.0], 20)])
    reports = np.tile([0, 1, 2], 20)
    return OrdinalCalibration(
        x,
        reports,
        tuple(f"cal:{i // 15}" for i in range(60)),
        ("instrument:a",) * 60,
        3,
        "fixture_report_anchor",
    )


def test_ordinal_posterior_order_probability_and_prediction():
    d = calibration()
    p = fit_ordinal(d, draws=30, warmup=40, chains=2, seed=11)
    assert p.beta.shape == (2, 30, 2)
    assert np.all(np.diff(p.thresholds, axis=3) > 0)
    assert np.all(p.thresholds[:, :, :, 0] == 0)
    e, probability = predict_reports(p, d.design, subjects=d.subjects, contexts=d.contexts)
    assert e.shape == (60, 60)
    np.testing.assert_allclose(probability.sum(axis=2), 1, atol=1e-12)
    np.testing.assert_allclose(e, 1 - probability[:, :, 0], atol=1e-12)
    assert e[:, d.design[:, 1] == 1].mean() > e[:, d.design[:, 1] == -1].mean()
    assert p.diagnostics["min_bulk_ess_estimate"] > 0


def test_missing_report_rows_do_not_become_no_experience_likelihood():
    d = calibration()
    missing = replace(
        d,
        design=np.vstack([d.design, [1, -100]]),
        reports=np.r_[d.reports, -1],
        subjects=(*d.subjects, "missing:1"),
        contexts=(*d.contexts, "instrument:a"),
    )
    a = fit_ordinal(d, draws=8, warmup=8, chains=2)
    b = fit_ordinal(missing, draws=8, warmup=8, chains=2)
    np.testing.assert_array_equal(a.beta, b.beta)
    np.testing.assert_array_equal(a.thresholds, b.thresholds)


def test_missingness_sensitivity_only_changes_flagged_rows():
    baseline = np.asarray([[0.1, 0.5, 0.9], [0.2, 0.6, 0.8]])
    shifted = missingness_sensitivity(baseline, np.asarray([False, True, False]), 1)
    np.testing.assert_array_equal(shifted[:, [0, 2]], baseline[:, [0, 2]])
    assert np.all(shifted[:, 1] > baseline[:, 1])
    with pytest.raises(ValueError):
        missingness_sensitivity(baseline * 10, np.ones(3, dtype=bool), 0)


def test_diagnostics_detect_separated_chains():
    rng = np.random.default_rng(4)
    good = rng.normal(size=(4, 400, 2))
    bad = good + np.arange(4)[:, None, None] * 5
    assert chain_diagnostics(good)["max_rank_folded_split_rhat"] < 1.05
    assert chain_diagnostics(bad)["max_rank_folded_split_rhat"] > 1.5


def test_invariance_comparison_retains_both_models_and_rejects_overlap():
    train = calibration()
    test = replace(train, subjects=tuple(s.replace("cal:", "test:") for s in train.subjects))
    result = report_invariance_check(train, test, draws=8, warmup=8, chains=2)
    assert len(result["models"]) == 2
    assert not result["universal_scale_validated"]
    assert all(np.isfinite(r["joint_nats"]) for m in result["models"] for r in m["scores"])
    with pytest.raises(ValueError, match="disjoint"):
        report_invariance_check(train, train, draws=8, warmup=8, chains=2)
