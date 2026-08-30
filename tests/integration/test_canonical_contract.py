from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from factorcon.pipeline.canonical import load_canonical_rdm, score_canonical_rdm, synthesize_scores
from factorcon.simulation import simulate_rdms


def _write(path: Path, truth: str, seed: int) -> None:
    design, train, test = simulate_rdms(
        truth, seed=seed, condition_count=30, train_replicates=6, test_replicates=6
    )
    names = np.asarray(list(design), dtype="U32")
    values = np.stack([design[name] for name in names])
    np.savez_compressed(
        path,
        train_rdms=train,
        test_rdms=test,
        design_names=names,
        design_values=values,
        condition_labels=np.asarray(
            [f"condition-{index}" for index in range(values.shape[1])], dtype="U32"
        ),
    )


def test_canonical_contract_scores_all_models(tmp_path: Path) -> None:
    source = tmp_path / "rdms.npz"
    output = tmp_path / "scores.json"
    _write(source, "M4", 901)
    arrays, design = load_canonical_rdm(source)
    assert arrays["train"].shape[0] == 6
    assert "E" in design
    report = score_canonical_rdm(source, output, family="fixture")
    assert set(report["scores"]) == {"M0", "M1", "M2", "M3", "M4", "M5"}
    assert report["scores"]["M4"]["log_score"] > report["scores"]["M0"]["log_score"]
    assert json.loads(output.read_text())["all_models_retained"] is True


def test_synthesis_keeps_every_family(tmp_path: Path) -> None:
    score_paths = []
    for index, truth in enumerate(("M4", "M0")):
        source = tmp_path / f"rdms-{index}.npz"
        output = tmp_path / f"scores-{index}.json"
        _write(source, truth, 1000 + index)
        score_canonical_rdm(source, output, family=f"family-{index}")
        score_paths.append(output)
    report = synthesize_scores(score_paths, tmp_path / "synthesis.json")
    assert report["family_count"] == 2
    assert {item["family"] for item in report["families"]} == {"family-0", "family-1"}
