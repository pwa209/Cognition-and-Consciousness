"""Independent numerical checks and synthetic fixtures; no participant data."""

import json
from dataclasses import replace

import numpy as np
import pytest
from scipy.linalg import helmert
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

from factorcon.features.patterns import whiten_patterns
from factorcon.models.generative import (
    GenerativeFit,
    ModelShape,
    OptimizationFailure,
    PatternData,
    fit_generative,
    pattern_log_density,
    predictive_scores,
    signal_covariance,
)
from factorcon.models.pattern_cv import evaluate_patterns, validate_collection
from factorcon.pipeline.patterns import load_pattern_data, score_pattern_files


def fixture(family="fixture", seed=7):
    rng = np.random.default_rng(seed)
    design = np.asarray([[0, -1, 0], [0.3, 1, 1], [0.7, -1, 1], [1, 1, 0]])
    latent = (design @ np.asarray([0.8, -0.4, 0.2]))[:, None]
    patterns = rng.normal(size=(3, 2, 4, 2)) + latent * rng.normal(size=(3, 1, 1, 2))
    return PatternData(
        family,
        tuple(f"{family}:{g}" for g in range(3)),
        ("E", "K_content", "R"),
        patterns,
        design[None],
        np.zeros((4, 0)),
        np.eye(8),
        "synthetic_common_anchor",
    )


def save_fixture(path, data=None, **metadata):
    d = data or fixture()
    meta = {
        "schema_version": 1,
        "source_kind": "synthetic_fixture",
        "family": d.family,
        "anchor_id": d.anchor_id,
        "design_source": "fixed_by_design",
        "units": "synthetic_SD",
        "feature_definition": "synthetic_patterns",
        "noise_definition": "identity",
        **metadata,
    }
    np.savez(
        path,
        metadata=json.dumps(meta),
        group_ids=np.asarray(d.group_ids),
        names=np.asarray(d.names),
        patterns=d.patterns,
        design_draws=d.design_draws,
        sensory=d.sensory,
        noise=d.noise,
    )


def test_joint_density_matches_independent_scipy_reference():
    d = fixture()
    signal = d.design_draws[0] @ d.design_draws[0].T
    projection = np.kron(np.eye(2), helmert(4))
    cov = projection @ (np.kron(np.ones((2, 2)), signal) + 0.7 * d.noise) @ projection.T
    expected = [
        sum(
            multivariate_normal.logpdf(projection @ group.reshape(8, 2)[:, f], cov=cov)
            for f in range(2)
        )
        for group in d.patterns
    ]
    np.testing.assert_allclose(pattern_log_density(d, signal, 0.7), expected, rtol=1e-12)
    shifted = replace(d, patterns=d.patterns + np.arange(6).reshape(3, 2, 1, 1))
    np.testing.assert_allclose(pattern_log_density(shifted, signal, 0.7), expected, rtol=1e-12)


def test_group_noise_matches_independent_densities_and_subset():
    d = fixture()
    signal = d.design_draws[0] @ d.design_draws[0].T
    group = replace(d, noise=np.stack([d.noise * scale for scale in (0.3, 1, 2)]))
    group.validate()
    scores = pattern_log_density(group, signal, 0.7)
    expected = [
        pattern_log_density(replace(d.subset(np.array([i])), noise=group.noise[i]), signal, 0.7)[0]
        for i in range(3)
    ]
    np.testing.assert_allclose(scores, expected)
    subset = group.subset(np.array([2, 0]))
    np.testing.assert_array_equal(subset.noise, group.noise[[2, 0]])
    np.testing.assert_allclose(pattern_log_density(subset, signal, 0.7), scores[[2, 0]])
    common = replace(d, noise=np.repeat(d.noise[None], 3, axis=0))
    np.testing.assert_allclose(
        pattern_log_density(common, signal, 0.7), pattern_log_density(d, signal, 0.7)
    )
    with pytest.raises(ValueError, match="symmetric"):
        bad = group.noise.copy()
        bad[0, 0, 1] = 1
        replace(group, noise=bad).validate()


@pytest.mark.parametrize("model", [f"M{i}" for i in range(6)])
def test_all_covariances_psd_and_parameters_learned(model):
    d = fixture()
    shape = ModelShape(model, d.names, (("E", "K_content"),), condition_count=4)
    theta = np.linspace(-0.2, 0.5, len(shape.labels))
    covariance = signal_covariance(shape, theta, d)
    assert np.linalg.eigvalsh(covariance).min() > -1e-10
    fit = fit_generative((d,), shape, penalty=0.01, starts=1, max_iter=250)
    assert np.isfinite(predictive_scores(fit, d)).all()
    assert any(s["success"] for s in fit.starts)
    assert not np.allclose(theta, fit.theta)


def test_signed_unitary_loading_and_strict_gate():
    d = fixture()
    shape = ModelShape("M0", d.names)
    theta = np.asarray([1.0, -1.0, 0.0, -3.0, 0.0])
    signal = signal_covariance(shape, theta, d)
    expected = d.design_draws[0] @ theta[:3]
    np.testing.assert_allclose(signal, np.outer(expected, expected))
    gate_shape = ModelShape("M1", d.names)
    low = replace(d, design_draws=d.design_draws.copy())
    low.design_draws[:, :, 0] = 0
    low.design_draws[:, :, 2] = 0
    strict = signal_covariance(gate_shape, np.zeros(len(gate_shape.labels)), low)
    np.testing.assert_array_equal(strict, 0)
    partial = signal_covariance(
        replace(gate_shape, gate_floor=0.2), np.zeros(len(gate_shape.labels)), low
    )
    assert np.trace(partial) > 0


def test_draw_mixture_is_not_mean_log_density():
    d = fixture()
    d = replace(d, design_draws=np.concatenate([d.design_draws, d.design_draws * 0.2]))
    shape = ModelShape("M0", d.names)
    fit = GenerativeFit(shape, np.asarray([2.0, 1.0, 0.0, -3.0, 0.0]), 0, (), 0, ())
    logs = np.stack(
        [pattern_log_density(d, signal_covariance(shape, fit.theta, d, j), 1) for j in range(2)]
    )
    np.testing.assert_allclose(predictive_scores(fit, d), logsumexp(logs, axis=0) - np.log(2))
    assert not np.allclose(predictive_scores(fit, d), logs.mean(axis=0))


def test_collection_rejects_cross_family_calibration_overlap():
    a, b = fixture("a"), fixture("b")
    with pytest.raises(ValueError, match="calibration"):
        validate_collection((replace(a, calibration_ids=(b.group_ids[0],)), b))


def test_whitening_rejects_neural_groups_and_preserves_partition_axis():
    d = fixture()
    residuals = np.random.default_rng(0).normal(size=(100, 2)) * [2, 4]
    with pytest.raises(ValueError, match="overlap"):
        whiten_patterns(d, residuals, calibration_ids=d.group_ids)
    out = whiten_patterns(d, residuals, calibration_ids=("external:1",))
    assert out.patterns.shape == d.patterns.shape
    assert np.std(out.patterns[..., 1]) < np.std(d.patterns[..., 1])
    np.testing.assert_array_equal(out.design_draws, d.design_draws)


def test_lofo_target_mutation_cannot_change_fits(monkeypatch):
    # Deterministic fit stub isolates orchestration leakage from optimizer tolerance.
    import factorcon.models.pattern_cv as module

    def fitted(datasets, shape, *, penalty, **kwargs):
        average = sum(d.patterns.mean() for d in datasets)
        theta = np.zeros(len(shape.labels)) + average * 0.01
        return GenerativeFit(shape, theta, penalty, tuple(d.family for d in datasets), 0, ())

    monkeypatch.setattr(module, "fit_generative", fitted)
    a, b = fixture("a"), fixture("b", 99)
    first = evaluate_patterns((a, b), mode="lofo", penalties=(0.0, 0.1))
    second = evaluate_patterns(
        (a, replace(b, patterns=b.patterns * 10)), mode="lofo", penalties=(0.0, 0.1)
    )
    original = [r for r in first["rows"] if r["family"] == "b"]
    changed = [r for r in second["rows"] if r["family"] == "b"]
    assert len(original) == 6
    for left, right in zip(original[:-1], changed[:-1], strict=True):
        assert left["status"] == right["status"] == "scored"
        assert left["parameters"] == right["parameters"]
        assert left["penalty"] == right["penalty"]
        assert left["inner_cv"] == right["inner_cv"]
        assert set(left["training_groups"]).isdisjoint(left["test_groups"])
    assert original[-1]["status"] == "not_estimable"  # M5 cannot transfer condition IDs.


def test_lofo_incompatible_anchors_retains_every_candidate():
    result = evaluate_patterns(
        (fixture("a"), replace(fixture("b"), anchor_id="other")), mode="lofo", penalties=(0.1,)
    )
    assert len(result["rows"]) == 12
    assert all(row["status"] == "not_estimable" for row in result["rows"])


def test_input_contract_and_failure_restart_success_markers(tmp_path, monkeypatch):
    import factorcon.pipeline.patterns as module

    path, output = tmp_path / "fixture.npz", tmp_path / "scores.json"
    np.savez(path, wrong=np.ones(2))
    with pytest.raises(ValueError):
        score_pattern_files([path], output, mode="within")
    assert json.loads((tmp_path / "scores.json.status.json").read_text())["status"] == "FAILED"
    save_fixture(path)
    assert load_pattern_data(path).family == "fixture"
    monkeypatch.setattr(module, "evaluate_patterns", lambda *a, **k: {"fixture_test": True})
    score_pattern_files([path], output, mode="within")
    assert json.loads((tmp_path / "scores.json.status.json").read_text())["status"] == "SUCCESS"
    assert len(list((tmp_path / "scores.json.runs").glob("*.provenance.json"))) == 2
    with pytest.raises(ValueError, match="exists"):
        score_pattern_files([path], output, mode="within")


def test_cli_dry_run_writes_nothing(tmp_path):
    from factorcon.cli import main

    path = tmp_path / "fixture.npz"
    save_fixture(path)
    assert (
        main(
            [
                "patterns",
                "--input",
                str(path),
                "--output",
                str(tmp_path / "out.json"),
                "--mode",
                "within",
                "--dry-run",
            ]
        )
        == 0
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fixture.npz"]


def test_failed_optimizer_preserves_every_start_and_anchor_guard():
    d = fixture()
    shape = ModelShape("M0", d.names)
    with pytest.raises(OptimizationFailure) as caught:
        fit_generative((d,), shape, penalty=0.01, starts=2, max_iter=1)
    assert len(caught.value.diagnostics) == 2
    fit = fit_generative((d,), shape, penalty=0.01, starts=1, max_iter=250)
    with pytest.raises(ValueError, match="anchors"):
        predictive_scores(fit, replace(d, anchor_id="unrelated_units"))


def test_group_specific_design_and_sensory_match_separate_density():
    base = fixture()
    design = np.stack([base.design_draws * v for v in (0.3, 0.6, 1)], axis=1)
    sensory = np.arange(12, dtype=float).reshape(3, 4, 1) / 12
    noise = np.stack([base.noise * v for v in (0.3, 1, 2)])
    data = replace(base, design_draws=design, sensory=sensory, noise=noise)
    data.validate()
    shape = ModelShape("M4", data.names)
    theta = np.arange(len(shape.labels), dtype=float) / 10
    signal = signal_covariance(shape, theta, data)
    assert signal.shape == (3, 4, 4)
    result = pattern_log_density(data, signal, 0.7)
    for i in range(3):
        single = replace(
            base,
            group_ids=(base.group_ids[i],),
            patterns=base.patterns[i : i + 1],
            design_draws=design[:, i],
            sensory=sensory[i],
            noise=noise[i],
        )
        assert np.allclose(
            result[i], pattern_log_density(single, signal_covariance(shape, theta, single), 0.7)[0]
        )
    selected = data.subset(np.array([2, 0]))
    selected.validate()
    assert np.array_equal(selected.design_draws, design[:, [2, 0]])
    assert np.array_equal(selected.sensory, sensory[[2, 0]])
