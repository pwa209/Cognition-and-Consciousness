"""Regression tests for scientific-integrity defects identified 2026-09-10."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from factorcon.cli import main
from factorcon.config import load_analysis_spec
from factorcon.errors import ConfigError
from factorcon.models.architectures import ARCHITECTURES
from factorcon.models.fit import evaluate_architecture, nonnegative_ridge
from factorcon.pipeline.canonical import (
    DEFAULT_SPEC,
    SCORE_KIND,
    load_canonical_rdm,
    score_canonical_rdm,
    synthesize_scores,
)
from factorcon.pipeline.reporting import build_paper_tables
from factorcon.pipeline.robustness import robustness_canonical_rdm
from factorcon.stats.meta import equal_family_summary
from factorcon.util import hash_file


def _inputs() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(52)
    return {
        "train_rdms": rng.normal(size=(3, 6)),
        "test_rdms": rng.normal(size=(2, 6)),
        "train_group_ids": np.array(["a", "b", "c"]),
        "test_group_ids": np.array(["d", "e"]),
        "design_names": np.array(["E", "A", "R"]),
        "design_values": np.array([[0, 1, 2, 3], [1, 0, 1, 0], [0, 1, 0, 1]]),
        "condition_labels": np.array(["c1", "c2", "c3", "c4"]),
        "independent_unit": np.array("participant"),
        "design_origin": np.array("fixed_by_design"),
    }


def _spec(tmp_path: Path) -> Path:
    spec = json.loads(DEFAULT_SPEC.read_text())
    spec["rdm_evaluation"]["alphas"] = [0.1]
    spec["rdm_evaluation"]["robustness_alphas"] = {"fixture": [0.1]}
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return path


def test_zero_component_does_not_produce_nan() -> None:
    intercept, weights = nonnegative_ridge(np.zeros((6, 2)), [-2, -1, 0, 1, 2, 3], alpha=0)
    assert intercept == 0.5
    np.testing.assert_array_equal(weights, [0, 0])


def test_ridge_intercept_matches_centered_solution() -> None:
    x = np.arange(8.0)[:, None] + 50
    y = 2 * x[:, 0] - 3
    intercept, weights = nonnegative_ridge(x, y, alpha=0)
    np.testing.assert_allclose(intercept + x @ weights, y, atol=1e-9)


@pytest.mark.parametrize("alpha", [float("nan"), float("inf"), -1])
def test_invalid_penalty_is_rejected(alpha: float) -> None:
    with pytest.raises(ValueError):
        nonnegative_ridge(np.ones((6, 1)), np.ones(6), alpha=alpha)


@pytest.mark.parametrize(
    "defect",
    [
        "overlap",
        "missing_ids",
        "duplicate_name",
        "duplicate_condition",
        "unknown_construct",
        "run_unit",
        "test_design",
    ],
)
def test_canonical_rejects_invalid_identity(tmp_path: Path, defect: str) -> None:
    values = _inputs()
    if defect == "overlap":
        values["test_group_ids"] = np.array(["a", "e"])
    elif defect == "missing_ids":
        del values["train_group_ids"]
    elif defect == "duplicate_name":
        values["design_names"] = np.array(["E", "E", "R"])
    elif defect == "duplicate_condition":
        values["condition_labels"] = np.array(["c1", "c2", "c3", "c3"])
    elif defect == "unknown_construct":
        values["design_names"] = np.array(["E", "A", "consciousness"])
    elif defect == "run_unit":
        values["independent_unit"] = np.array("run")
    else:
        values["design_origin"] = np.array("all_participants")
    path = tmp_path / "input.npz"
    np.savez(path, **values)
    with pytest.raises(ValueError):
        load_canonical_rdm(path)


def test_test_perturbation_cannot_change_training_fit_or_variance() -> None:
    values = _inputs()
    design = {"E": values["design_values"][0], "R": values["design_values"][2]}
    first = evaluate_architecture(
        "M4", design, values["train_rdms"], values["test_rdms"], alphas=[0.1]
    )
    second = evaluate_architecture(
        "M4", design, values["train_rdms"], values["test_rdms"] + 1e6, alphas=[0.1]
    )
    assert first.weights == second.weights
    assert first.alpha == second.alpha
    assert first.residual_variance == second.residual_variance
    np.testing.assert_array_equal(first.predictions, second.predictions)


def test_m5_variance_uses_held_out_training_predictions() -> None:
    values = _inputs()
    train = values["train_rdms"]
    fit = evaluate_architecture("M5", {"E": np.arange(4)}, train, values["test_rdms"])
    expected = np.mean(
        [(row - np.delete(train, i, axis=0).mean(axis=0)) ** 2 for i, row in enumerate(train)]
    )
    assert fit.residual_variance == pytest.approx(expected)
    assert fit.residual_variance > np.mean((train - train.mean(axis=0)) ** 2)


def test_duplicate_rows_with_same_group_do_not_inflate_evidence() -> None:
    v = _inputs()
    kwargs = {
        "train_groups": v["train_group_ids"].tolist(),
        "test_groups": v["test_group_ids"].tolist(),
        "alphas": [0.1],
    }
    original = evaluate_architecture(
        "M4", {"E": np.arange(4)}, v["train_rdms"], v["test_rdms"], **kwargs
    )
    kwargs["train_groups"] = ["a", "b", "c", "a"]
    kwargs["test_groups"] = ["d", "e", "d"]
    duplicate = evaluate_architecture(
        "M4",
        {"E": np.arange(4)},
        np.vstack([v["train_rdms"], v["train_rdms"][0]]),
        np.vstack([v["test_rdms"], v["test_rdms"][0]]),
        **kwargs,
    )
    assert original.log_score == pytest.approx(duplicate.log_score)
    assert original.residual_variance == duplicate.residual_variance


def test_unavailable_models_are_retained_in_scores_and_tables(tmp_path: Path) -> None:
    source = tmp_path / "rdms.npz"
    np.savez(source, **_inputs())
    spec = _spec(tmp_path)
    output = tmp_path / "scores.json"
    report = score_canonical_rdm(source, output, family="sleep", analysis_spec=spec)
    assert set(report["scores"]) == set(ARCHITECTURES)
    assert report["scores"]["M1"]["status"] == "not_estimable"
    assert report["scores"]["M2"]["status"] == "not_estimable"
    assert report["scores"]["M4"]["design_diagnostics"]["aliased_components_present"]
    synthesis = tmp_path / "synthesis.json"
    summary = synthesize_scores([output], synthesis, analysis_spec=spec)
    assert summary["comparisons"]["M4_minus_M1"]["equal_family"] is None
    manifest = build_paper_tables([output], synthesis, tmp_path / "paper")
    assert manifest["tables"]["model_scores"]["rows"] == 6


def test_equal_family_weights_do_not_depend_on_precision() -> None:
    summary = equal_family_summary([1, -1], [0.001, 10])
    assert summary["mean"] == 0
    assert summary["weights"] == [0.5, 0.5]
    assert equal_family_summary([1], [None])["standard_error"] is None
    assert equal_family_summary([1, -1], [0, 0])["standard_error"] == 0


def test_group_target_averages_rdms_before_loss() -> None:
    v = _inputs()
    test = np.vstack([np.ones(6), -np.ones(6)])
    fit = evaluate_architecture(
        "M5", {"E": np.arange(4)}, v["train_rdms"], test, test_groups=["person", "person"]
    )
    expected = np.mean(fit.predictions**2)
    assert fit.mean_squared_error == pytest.approx(expected)
    assert fit.log_score != pytest.approx(fit.replicate_log_scores.mean())


def test_outer_training_design_is_not_mistaken_for_inner_fold_locality(tmp_path: Path) -> None:
    values = _inputs()
    values["design_origin"] = np.array("training_only")
    path = tmp_path / "input.npz"
    np.savez(path, **values)
    with pytest.raises(ValueError, match="per-inner-fold"):
        load_canonical_rdm(path)


def _score_fixture(path: Path, family: str, spec: Path, size: int = 2) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "family": family,
                "score_kind": SCORE_KIND,
                "analysis_spec_sha256": hash_file(spec),
                "independent_unit": "participant",
                "test_group_ids": [f"p{i}" for i in range(size)],
                "scores": {
                    model: {
                        "status": "scored",
                        "log_score": 100 - i,
                        "group_log_scores": [i * 0.1] * size,
                    }
                    for i, model in enumerate(ARCHITECTURES)
                },
            }
        )
    )


def test_synthesis_retains_fixed_comparators_and_unknown_uncertainty(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    source = tmp_path / "score.json"
    _score_fixture(source, "one", spec, size=1)
    report = synthesize_scores([source], tmp_path / "synthesis.json", analysis_spec=spec)
    assert set(report["comparisons"]) == {f"M4_minus_M{i}" for i in [0, 1, 2, 3, 5]}
    for comparison in report["comparisons"].values():
        assert comparison["equal_family"]["standard_error"] is None
    assert report["comparisons"]["M4_minus_M0"]["families"][0]["delta"] == 0.4
    with pytest.raises(ValueError, match="duplicate"):
        synthesize_scores([source, source], tmp_path / "bad.json", analysis_spec=spec)


def test_robustness_uses_joint_shuffle_and_group_influence(tmp_path: Path) -> None:
    source = tmp_path / "rdms.npz"
    v = _inputs()
    v["test_rdms"] = np.vstack([v["test_rdms"], v["test_rdms"][0]])
    v["test_group_ids"] = np.array(["d", "e", "d"])
    np.savez(source, **v)
    report = robustness_canonical_rdm(
        source, tmp_path / "robustness.json", family="sleep", analysis_spec=_spec(tmp_path)
    )
    assert len(report["leave_one_group_out"]) == 2
    permutation = report["permutation"]
    np.testing.assert_allclose(
        np.corrcoef(v["design_values"]), np.corrcoef(v["design_values"][:, permutation])
    )
    assert set(report["random_construct_map_negative_control"]) == set(ARCHITECTURES)
    assert "best_nonfactorized" not in report["specifications"][0]


def test_failure_retry_provenance_and_output_preservation(tmp_path: Path) -> None:
    source = tmp_path / "input.npz"
    output = tmp_path / "score.json"
    spec = _spec(tmp_path)
    invalid = _inputs()
    invalid["test_group_ids"] = np.array(["a", "e"])
    np.savez(source, **invalid)
    with pytest.raises(ValueError, match="overlap"):
        score_canonical_rdm(source, output, family="fixture", analysis_spec=spec)
    state = Path(str(output) + ".status.json")
    assert json.loads(state.read_text())["status"] == "FAILED"
    assert not output.exists()
    np.savez(source, **_inputs())
    score_canonical_rdm(source, output, family="fixture", analysis_spec=spec)
    status = json.loads(state.read_text())
    assert status["status"] == "SUCCESS"
    provenance = json.loads(Path(status["provenance"]).read_text())
    assert provenance["outputs"][str(output)] == hash_file(output)
    assert provenance["inputs"][str(spec)] == hash_file(spec)
    assert len(list(Path(str(output) + ".runs").glob("*.json"))) == 2
    original = output.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        score_canonical_rdm(source, output, family="fixture", analysis_spec=spec)
    assert output.read_bytes() == original


def test_cli_dry_run_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "input.npz"
    output = tmp_path / "score.json"
    np.savez(source, **_inputs())
    assert (
        main(
            [
                "model",
                "score",
                "--family",
                "fixture",
                "--input",
                str(source),
                "--output",
                str(output),
                "--analysis-spec",
                str(_spec(tmp_path)),
                "--dry-run",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["writes"] is False
    assert not output.exists()
    assert not Path(str(output) + ".status.json").exists()


@pytest.mark.parametrize("defect", ["alpha", "contrast", "score_kind", "gate"])
def test_invalid_analysis_settings_fail_validation(tmp_path: Path, defect: str) -> None:
    path = _spec(tmp_path)
    spec = json.loads(path.read_text())
    if defect == "alpha":
        spec["rdm_evaluation"]["alphas"] = [-1]
    elif defect == "contrast":
        spec["rdm_evaluation"]["paired_contrasts"] = [["M4", "M0"]]
    elif defect == "score_kind":
        spec["rdm_evaluation"]["score_kind"] = "joint_ELPD"
    else:
        spec["scientific_gates"] = True
    path.write_text(json.dumps(spec))
    with pytest.raises(ConfigError):
        load_analysis_spec(path)
