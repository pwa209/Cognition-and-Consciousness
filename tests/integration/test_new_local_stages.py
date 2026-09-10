"""Local artifact/dry-run fixtures for the new stages; never server deployment."""

import json
from pathlib import Path

import numpy as np

from factorcon.cli import main
from factorcon.pipeline.measurement import fit_report_file
from factorcon.pipeline.patterns import score_pattern_files
from factorcon.simulation_stress import run_stress_plan, simulate_patterns, simulate_reports


def small_spec(tmp_path):
    spec = json.loads(Path("conf/analysis_spec.yaml").read_text())
    spec["report_measurement"].update(draws=8, warmup=8, chains=2)
    spec["pattern_evaluation"].update(penalties=[0.01], optimizer_starts=1, max_iter=250)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return path


def test_measurement_stage_actual_fit_and_dry_run(tmp_path):
    path, output = tmp_path / "reports.json", tmp_path / "posterior.json"
    data, _ = simulate_reports("complete", seed=9, subjects=4, trials_per_subject=6)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "predictor_source": "non_neural_fixed_units",
                "design": data.design.tolist(),
                "reports": data.reports.tolist(),
                "subjects": data.subjects,
                "contexts": data.contexts,
                "categories": data.categories,
                "anchor_id": data.anchor_id,
            }
        )
    )
    spec = small_spec(tmp_path)
    assert (
        main(
            [
                "measurement",
                "--input",
                str(path),
                "--output",
                str(output),
                "--analysis-spec",
                str(spec),
                "--dry-run",
            ]
        )
        == 0
    )
    assert not output.exists()
    result = fit_report_file(path, output, analysis_spec=spec)
    assert not result["universal_consciousness_probability"]
    assert np.asarray(result["posterior"]["beta"]).shape == (2, 8, 2)
    assert json.loads(Path(str(output) + ".status.json").read_text())["status"] == "SUCCESS"


def test_independent_stress_generators_and_checkpoint_stage(tmp_path, monkeypatch):
    import factorcon.models.generative as module

    def forbidden(*args, **kwargs):
        raise AssertionError("generator must not call model covariance")

    monkeypatch.setattr(module, "signal_covariance", forbidden)
    for scenario in ("unitary", "factorized", "aliased", "heavy_tail"):
        data = simulate_patterns(scenario, seed=12, groups=4, conditions=4, features=2)
        data.validate()
    path, output = tmp_path / "plan.json", tmp_path / "stress.json"
    path.write_text(
        json.dumps(
            {
                "suite": "reports",
                "replicates": 2,
                "groups": 4,
                "conditions": 6,
                "features": 2,
                "draws": 8,
                "warmup": 8,
                "chains": 2,
                "scenarios": ["complete", "mar", "mnar"],
            }
        )
    )
    result = run_stress_plan(path, output)
    assert len(result["rows"]) == 6
    assert all(r["status"] == "completed" for r in result["rows"])
    assert result["small_run_is_not_validation"]
    assert json.loads(Path(str(output) + ".checkpoint.json").read_text())["complete"]


def test_real_nested_pattern_stage_retains_candidates(tmp_path):
    data = simulate_patterns("unitary", seed=72, groups=3, conditions=4, features=1)
    path, output = tmp_path / "patterns.npz", tmp_path / "scores.json"
    metadata = {
        "schema_version": 1,
        "source_kind": "synthetic_fixture",
        "family": data.family,
        "anchor_id": data.anchor_id,
        "design_source": "fixed_by_design",
        "units": "synthetic_SD",
        "feature_definition": "simulated_patterns",
        "noise_definition": "known_simulation_covariance",
    }
    np.savez(
        path,
        metadata=json.dumps(metadata),
        group_ids=np.asarray(data.group_ids),
        names=np.asarray(data.names),
        patterns=data.patterns,
        design_draws=data.design_draws,
        sensory=data.sensory,
        noise=data.noise,
    )
    result = score_pattern_files([path], output, mode="within", analysis_spec=small_spec(tmp_path))
    assert len(result["rows"]) == 18
    assert {r["model"] for r in result["rows"]} == {f"M{i}" for i in range(6)}
    assert all(r["status"] == "scored" for r in result["rows"])
    assert all(set(r["training_groups"]).isdisjoint(r["test_groups"]) for r in result["rows"])
    assert json.loads(Path(str(output) + ".status.json").read_text())["status"] == "SUCCESS"
