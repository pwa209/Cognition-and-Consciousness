"""Bootstrap multiplicities stay attached to original independent subjects."""

import numpy as np

from factorcon.models.generative import PatternData
from factorcon.stats.pattern_bootstrap import paired_pattern_summary, refit_pattern_bootstrap


def test_bootstrap_refits_and_never_clones_group_identities(monkeypatch):
    import factorcon.stats.pattern_bootstrap as module

    data = PatternData(
        "f",
        tuple(f"f:{i}" for i in range(8)),
        ("K_content",),
        np.zeros((8, 2, 4, 1)),
        np.arange(4).reshape(1, 4, 1),
        np.zeros((4, 0)),
        np.eye(8),
        "fixture",
    )
    seen = []

    def evaluate(datasets, **options):
        sample = datasets[0]
        seen.append(sample)
        weights = (
            np.ones(len(sample.group_ids)) if sample.group_weights is None else sample.group_weights
        )
        rows = []
        for model in range(6):
            rows.append(
                {
                    "family": "f",
                    "model": f"M{model}",
                    "status": "scored",
                    "test_groups": list(sample.group_ids),
                    "test_group_weights": weights.tolist(),
                    "scores_nats": [float(int(g.split(":")[1]) * model) for g in sample.group_ids],
                    "scored_dimensions_per_group": 6,
                }
            )
        return {"rows": rows}

    monkeypatch.setattr(module, "evaluate_patterns", evaluate)
    result = refit_pattern_bootstrap((data,), replicates=12, evaluation_options={}, seed=17)
    assert len(seen) == 13
    for sample in seen[1:]:
        assert len(sample.group_ids) == len(set(sample.group_ids))
        assert set(sample.group_ids) <= set(data.group_ids)
        assert sample.group_weights.sum() == 8
    assert len(result["replicates"]) == 12
    assert all(v["percentile_95"] is not None for v in result["intervals"].values())
    assert not result["multiplicity_adjusted"]


def test_missing_model_does_not_change_family_population():
    rows = [
        {
            "family": "f",
            "model": f"M{m}",
            "status": "scored",
            "test_groups": ["f:1"],
            "test_group_weights": [1],
            "scores_nats": [float(m)],
            "scored_dimensions_per_group": 1,
        }
        for m in range(6)
    ]
    summary = paired_pattern_summary({"rows": rows}, ("f", "unavailable_family"))
    assert all(v is None for v in summary.values())
