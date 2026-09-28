"""Generative reporting and bootstrap identities; fixtures are not empirical results."""

import copy

import numpy as np
import pytest

from factorcon.pipeline.downstream import (
    bootstrap_shard,
    report_results,
    retry_structurally_invalid_bootstrap,
)
from factorcon.simulation_stress import simulate_patterns
from factorcon.stats.pattern_bootstrap import paired_pattern_summary


def evaluation():
    return {
        "implementation": "generative_pattern_v1",
        "mode": "within",
        "rows": [
            {
                "family": "f",
                "model": f"M{i}",
                "test_groups": ["f:1"],
                "test_group_weights": [1.0],
                "scored_dimensions_per_group": 10,
                "scores_nats": [float(i)],
                "status": "scored",
            }
            for i in range(6)
        ],
    }


def test_pairing_checks_scored_dimensions_and_no_silent_missing_family():
    value = evaluation()
    assert paired_pattern_summary(value, ("f",))["M4-M0"] == 0.4
    assert paired_pattern_summary(value, ("f", "missing"))["M4-M0"] is None
    value["rows"][0]["scored_dimensions_per_group"] = 11
    with pytest.raises(ValueError, match="dimensions"):
        paired_pattern_summary(value, ("f",))


def test_reporting_retains_null_failure_and_missing_replicate(tmp_path):
    value = evaluation()
    value["rows"][4]["scores_nats"] = [0.0]
    value["rows"][1].update(status="not_estimable", reason="E absent")
    del value["rows"][1]["scores_nats"]
    result = report_results(
        tmp_path,
        families=("f",),
        evaluations={"within": value},
        bootstrap=[],
        requested_replicates=2,
        coverage=[],
    )
    assert result["summaries"]["within"]["M4-M0"] == 0.0
    assert result["summaries"]["within"]["M4-M1"] is None
    assert result["intervals"]["M4-M0"]["percentile_95"] is None
    assert "E absent" in (tmp_path / "scores.tsv").read_text()
    assert not result["equivalence_tested"] and not result["multiplicity_adjusted"]
    omitted = copy.deepcopy(value)
    omitted["rows"].pop()
    with pytest.raises(ValueError, match="M0-M5"):
        report_results(
            tmp_path,
            families=("f",),
            evaluations={"within": omitted},
            bootstrap=[],
            requested_replicates=2,
            coverage=[],
        )


def test_bootstrap_deterministic_original_subject_weights(monkeypatch):
    import factorcon.pipeline.downstream as module

    data = simulate_patterns("unitary", seed=3, groups=8, conditions=4, features=1)
    observed = []

    def evaluate(sampled, **_kwargs):
        selected = sampled[0]
        observed.append(selected)
        assert len(set(selected.group_ids)) == len(selected.group_ids)
        assert sum(selected.group_weights) == len(data.group_ids)
        return {"rows": []}

    monkeypatch.setattr(module, "evaluate_patterns", evaluate)
    first = bootstrap_shard((data,), replicate=5, seed=17, options={})
    bootstrap_shard((data,), replicate=2, seed=17, options={})
    repeated = bootstrap_shard((data,), replicate=5, seed=17, options={})
    assert first == repeated
    assert np.array_equal(observed[0].patterns, observed[2].patterns)


def test_structural_retry_preserves_initial_failure_and_redraws_deterministically(monkeypatch):
    import factorcon.pipeline.downstream as module

    data = simulate_patterns("unitary", seed=3, groups=5, conditions=4, features=1)
    seed = 17
    for replicate in range(1000):
        rng = np.random.default_rng(np.random.SeedSequence([seed, replicate]))
        counts = np.bincount(rng.integers(0, 5, 5), minlength=5)
        if np.count_nonzero(counts) < 3:
            break
    else:
        raise AssertionError("fixture needs a structurally invalid initial draw")
    original = {data.family: dict(zip(data.group_ids, counts.tolist(), strict=True))}
    observed = []

    def evaluate(sampled, **_kwargs):
        selected = sampled[0]
        observed.append(selected)
        assert len(selected.group_ids) >= 3
        assert len(set(selected.group_ids)) == len(selected.group_ids)
        assert sum(selected.group_weights) == 5
        return {"rows": []}

    monkeypatch.setattr(module, "evaluate_patterns", evaluate)
    monkeypatch.setattr(module, "paired_pattern_summary", lambda *_: {"M4-M0": 0.4})
    first = retry_structurally_invalid_bootstrap(
        (data,), replicate=replicate, seed=seed, options={}, original_multiplicities=original
    )
    repeated = retry_structurally_invalid_bootstrap(
        (data,), replicate=replicate, seed=seed, options={}, original_multiplicities=original
    )
    assert first == repeated
    assert first["status"] == "completed"
    assert first["draw_attempt"] >= 1
    assert first["original_multiplicities"] == original
    assert first["sampling_policy"] == "conditional_min_three_unique_groups_per_family_v1"
    assert np.array_equal(observed[0].patterns, observed[1].patterns)
    with pytest.raises(ValueError, match="original draw identity"):
        retry_structurally_invalid_bootstrap(
            (data,),
            replicate=replicate,
            seed=seed,
            options={},
            original_multiplicities={data.family: {}},
        )


def test_five_group_original_seed_has_113_structurally_invalid_draws():
    """Check the pre-score failure count using participant IDs only."""
    failures = 0
    for replicate in range(1000):
        rng = np.random.default_rng(np.random.SeedSequence([260830, replicate]))
        counts = np.bincount(rng.integers(0, 5, 5), minlength=5)
        failures += np.count_nonzero(counts) < 3
    assert failures == 113


def test_structural_retry_does_not_redraw_a_numerical_failure(monkeypatch):
    import factorcon.pipeline.downstream as module

    data = simulate_patterns("unitary", seed=3, groups=5, conditions=4, features=1)
    seed = 17
    replicate = next(
        r
        for r in range(1000)
        if np.count_nonzero(
            np.bincount(
                np.random.default_rng(np.random.SeedSequence([seed, r])).integers(0, 5, 5),
                minlength=5,
            )
        )
        < 3
    )
    rng = np.random.default_rng(np.random.SeedSequence([seed, replicate]))
    original_counts = np.bincount(rng.integers(0, 5, 5), minlength=5)
    original = {data.family: dict(zip(data.group_ids, original_counts.tolist(), strict=True))}
    calls = []

    def failed_fit(*_args, **_kwargs):
        calls.append(1)
        raise ValueError("numerical fitting failure")

    monkeypatch.setattr(module, "evaluate_patterns", failed_fit)
    result = retry_structurally_invalid_bootstrap(
        (data,), replicate=replicate, seed=seed, options={}, original_multiplicities=original
    )
    assert result["status"] == "failed"
    assert "numerical fitting failure" in result["reason"]
    assert len(calls) == 1


def test_no_conditional_on_success_interval(tmp_path):
    point = evaluation()
    contrasts = paired_pattern_summary(point, ("f",))
    shards = [
        {"replicate": 0, "status": "completed", "scores": contrasts},
        {"replicate": 1, "status": "failed", "reason": "too few unique groups"},
    ]
    report = report_results(
        tmp_path,
        families=("f",),
        evaluations={"within": point},
        bootstrap=shards,
        requested_replicates=2,
        coverage=[],
    )
    assert all(v["percentile_95"] is None for v in report["intervals"].values())
    shards[1] = {"replicate": 1, "status": "completed", "scores": contrasts}
    report = report_results(
        tmp_path,
        families=("f",),
        evaluations={"within": point},
        bootstrap=shards,
        requested_replicates=2,
        coverage=[],
    )
    assert report["intervals"]["M4-M0"]["percentile_95"] == [0.4, 0.4]
