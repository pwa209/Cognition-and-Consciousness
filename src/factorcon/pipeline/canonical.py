"""Identity-checked RDM scoring and explicit, paired finite-family comparisons."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from factorcon.config import load_analysis_spec
from factorcon.models.architectures import ARCHITECTURES, CONSTRUCT_ORDER, unavailable_reason
from factorcon.models.fit import _component_matrix, evaluate_architecture
from factorcon.provenance import analysis_artifact
from factorcon.stats.meta import equal_family_summary
from factorcon.util import atomic_write_json, hash_file, utc_now

DEFAULT_SPEC = Path(__file__).resolve().parents[3] / "conf" / "analysis_spec.yaml"
SCORE_KIND = "mean_gaussian_marginal_log_score_nats_per_pair"
REQUIRED_ARRAYS = {
    "train_rdms",
    "test_rdms",
    "design_names",
    "design_values",
    "condition_labels",
    "train_group_ids",
    "test_group_ids",
    "independent_unit",
    "design_origin",
}


def _strings(value: np.ndarray, name: str) -> list[str]:
    if value.ndim != 1 or value.dtype.kind not in {"U", "S"}:
        raise ValueError(f"{name} must be a one-dimensional string array")
    strings = value.astype(str).tolist()
    if not strings or any(not item.strip() for item in strings):
        raise ValueError(f"{name} must contain non-empty IDs")
    return strings


def load_canonical_rdm(path: str | Path) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Load v2 replicates-by-pairs inputs with disjoint independent-group IDs.

    RDMs retain distance units and negative crossnobis values. Only fixed experimental
    design tables are accepted: empirical designs need per-inner-fold measurement
    fitting, which this interface does not implement. Provenance declarations are
    audited, not independently proved here.
    Run-only splits require a future nested participant-aware contract, not relabeling
    runs as participants. Existing v1 files must be regenerated from real source IDs.
    """
    with np.load(path, allow_pickle=False) as archive:
        missing = REQUIRED_ARRAYS - set(archive.files)
        if missing:
            raise ValueError(f"Canonical RDM v2 missing arrays: {sorted(missing)}")
        arrays = {key: np.asarray(archive[key]) for key in REQUIRED_ARRAYS}
    train = np.asarray(arrays["train_rdms"], dtype=float)
    test = np.asarray(arrays["test_rdms"], dtype=float)
    names = _strings(arrays["design_names"], "design_names")
    conditions = _strings(arrays["condition_labels"], "condition_labels")
    train_ids = _strings(arrays["train_group_ids"], "train_group_ids")
    test_ids = _strings(arrays["test_group_ids"], "test_group_ids")
    if len(set(names)) != len(names) or set(names) - set(CONSTRUCT_ORDER):
        raise ValueError("design_names must be unique known constructs")
    if len(set(conditions)) != len(conditions) or len(conditions) < 3:
        raise ValueError("at least three unique condition labels required")
    for key in ("independent_unit", "design_origin"):
        if arrays[key].ndim != 0 or arrays[key].dtype.kind not in {"U", "S"}:
            raise ValueError(f"{key} must be a scalar string")
    if str(arrays["independent_unit"].astype(str)) not in {
        "participant",
        "patient",
        "laboratory",
        "contributing_dataset",
        "synthetic_participant",
    }:
        raise ValueError("independent_unit must identify participants/patients or higher clusters")
    if str(arrays["design_origin"].astype(str)) != "fixed_by_design":
        raise ValueError(
            "design_origin must be fixed_by_design; empirical tables require "
            "per-inner-fold measurement fitting, not one outer-training fit"
        )
    values = np.asarray(arrays["design_values"], dtype=float)
    if train.ndim != 2 or test.ndim != 2 or train.shape[1] != test.shape[1]:
        raise ValueError("train/test RDM arrays must be replicates-by-identical-pairs")
    if len(train_ids) != len(train) or len(test_ids) != len(test):
        raise ValueError("one independent-group ID required per replicate")
    if set(train_ids) & set(test_ids):
        raise ValueError("train/test independent-group overlap: leakage")
    if len(set(train_ids)) < 3:
        raise ValueError("at least three independent training groups required")
    if values.shape != (len(names), len(conditions)):
        raise ValueError("design_values must be design_names-by-condition_labels")
    if train.shape[1] != len(conditions) * (len(conditions) - 1) // 2:
        raise ValueError("RDM pair count does not match conditions")
    if not np.isfinite(train).all() or not np.isfinite(test).all() or not np.isfinite(values).all():
        raise ValueError("canonical arrays must be finite; missingness is resolved upstream")
    return {
        "train": train,
        "test": test,
        "conditions": np.asarray(conditions),
        "train_group_ids": np.asarray(train_ids),
        "test_group_ids": np.asarray(test_ids),
        "independent_unit": arrays["independent_unit"].astype(str),
        "design_origin": arrays["design_origin"].astype(str),
    }, {name: values[index] for index, name in enumerate(names)}


def evaluate_candidates(
    arrays: Mapping[str, np.ndarray], design: Mapping[str, np.ndarray], *, alphas: Sequence[float]
) -> dict[str, Any]:
    """Score all six prototypes on identical groups, in nats per pair.

    Structurally unavailable models remain explicit rows. Collinearity is reported,
    never used to select a favorable design or silently discard a candidate.
    """
    scores: dict[str, Any] = {}
    for model in ARCHITECTURES:
        reason = unavailable_reason(model, design)
        if reason:
            scores[model] = {
                "name": ARCHITECTURES[model],
                "status": "not_estimable",
                "reason": reason,
            }
            continue
        fit = evaluate_architecture(
            model,
            design,
            arrays["train"],
            arrays["test"],
            alphas=alphas,
            train_groups=arrays["train_group_ids"].tolist(),
            test_groups=arrays["test_group_ids"].tolist(),
        )
        names, matrix = _component_matrix(model, design)
        centered = matrix - matrix.mean(axis=0)
        rank = int(np.linalg.matrix_rank(centered)) if matrix.shape[1] else 0
        scores[model] = {
            "name": ARCHITECTURES[model],
            "status": "scored",
            "log_score": fit.log_score,
            "replicate_log_scores": fit.replicate_log_scores.tolist(),
            "group_log_scores": fit.group_log_scores.tolist(),
            "mse": fit.mean_squared_error,
            "effective_df": fit.effective_df,
            "alpha": fit.alpha,
            "weights": fit.weights,
            "residual_variance": fit.residual_variance,
            "variance_method": fit.variance_method,
            "design_diagnostics": {
                "component_count": len(names),
                "centered_component_rank": rank,
                "aliased_components_present": rank < len(names),
                "zero_components": [
                    n for n, v in zip(names, centered.T, strict=True) if np.linalg.norm(v) < 1e-12
                ],
            },
        }
    return scores


@analysis_artifact("P07_component_rdm")
def score_canonical_rdm(
    path: str | Path, output: str | Path, *, family: str, analysis_spec: str | Path = DEFAULT_SPEC
) -> dict[str, Any]:
    """Score a family on fixed conditions; preserve all candidates and group identities.

    Output schema v2 uses marginal nats/pair, not joint ELPD or causal/theory evidence.
    Configuration supplies tuning and implementation scope, without scientific gates.
    """
    settings = load_analysis_spec(analysis_spec)["rdm_evaluation"]
    arrays, design = load_canonical_rdm(path)
    report = {
        "schema_version": 2,
        "family": family,
        "created_utc": utc_now(),
        "input": str(Path(path)),
        "input_sha256": hash_file(path),
        "analysis_spec_sha256": hash_file(analysis_spec),
        "score_kind": SCORE_KIND,
        "implementation": settings["implementation"],
        "model_scope": settings["model_scope"],
        "inference_scope": "new_independent_groups_fixed_conditions_conditional_on_training",
        "prediction_target": "independent_group_mean_RDM",
        "independent_unit": str(arrays["independent_unit"]),
        "design_origin": str(arrays["design_origin"]),
        "conditions": arrays["conditions"].tolist(),
        "train_replicates": len(arrays["train"]),
        "test_replicates": len(arrays["test"]),
        "test_group_ids": list(dict.fromkeys(arrays["test_group_ids"].tolist())),
        "scores": evaluate_candidates(arrays, design, alphas=settings["alphas"]),
        "scientific_gate": None,
        "all_models_retained": True,
    }
    atomic_write_json(output, report)
    return report


@analysis_artifact("P08_finite_family_summary")
def synthesize_scores(
    paths: list[str | Path], output: str | Path, *, analysis_spec: str | Path = DEFAULT_SPEC
) -> dict[str, Any]:
    """Report every configured paired contrast with genuinely equal family weights.

    Groups, not RDM pairs/runs, supply test-sample uncertainty. Comparators are fixed
    in configuration, never selected on test scores. Unknown uncertainty is None.
    Families with missing constructs remain in each contrast's unavailable ledger.
    Only a finite-family, conditional summary is supplied; this is not LOFO transfer.
    """
    settings = load_analysis_spec(analysis_spec)["rdm_evaluation"]
    records = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    names = [record["family"] for record in records]
    if not records or len(set(names)) != len(names):
        raise ValueError(
            "non-empty, unique family records required; duplicate families inflate evidence"
        )
    for record in records:
        if record.get("schema_version") != 2 or record.get("score_kind") != SCORE_KIND:
            raise ValueError("synthesis requires v2 scores with compatible marginal-score units")
        if record.get("analysis_spec_sha256") != hash_file(analysis_spec):
            raise ValueError("score/specification mismatch; rescore under a common specification")
        if set(record["scores"]) != set(ARCHITECTURES):
            raise ValueError("all six candidates must be retained")
    comparisons: dict[str, Any] = {}
    for left, right in settings["paired_contrasts"]:
        families, unavailable = [], []
        for record in records:
            a, b = record["scores"][left], record["scores"][right]
            if a["status"] != "scored" or b["status"] != "scored":
                unavailable.append(
                    {"family": record["family"], "reason": "candidate_not_estimable"}
                )
                continue
            group_ids = record["test_group_ids"]
            av = np.asarray(a["group_log_scores"], dtype=float)
            bv = np.asarray(b["group_log_scores"], dtype=float)
            if (
                not group_ids
                or len(set(group_ids)) != len(group_ids)
                or av.shape != (len(group_ids),)
                or bv.shape != av.shape
                or not np.isfinite(av).all()
                or not np.isfinite(bv).all()
            ):
                raise ValueError("paired finite scores and unique group identities required")
            delta = av - bv
            families.append(
                {
                    "family": record["family"],
                    "delta": float(delta.mean()),
                    "standard_error": float(delta.std(ddof=1) / np.sqrt(len(delta)))
                    if len(delta) > 1
                    else None,
                    "independent_groups": len(delta),
                    "independent_unit": record["independent_unit"],
                }
            )
        comparisons[f"{left}_minus_{right}"] = {
            "families": families,
            "unavailable_families": unavailable,
            "equal_family": equal_family_summary(
                [row["delta"] for row in families], [row["standard_error"] for row in families]
            )
            if families
            else None,
        }
    report = {
        "schema_version": 2,
        "created_utc": utc_now(),
        "family_count": len(records),
        "families": [{"family": name} for name in names],
        "comparisons": comparisons,
        "score_kind": SCORE_KIND,
        "comparator_selection": "fixed_configured_pairwise",
        "analysis_spec_sha256": hash_file(analysis_spec),
        "input_sha256": {str(path): hash_file(path) for path in paths},
        "interpretation_gate": None,
        "leave_one_family_out_transfer": "not_implemented",
        "multiplicity": "descriptive_intervals_no_joint_significance_claim",
        "note": "No new-family, measurement-error, or training-refit uncertainty is claimed.",
    }
    atomic_write_json(output, report)
    return report
