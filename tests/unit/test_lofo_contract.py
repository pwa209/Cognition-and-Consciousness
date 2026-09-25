"""Synthetic, outcome-blind tests for the restricted empirical transfer contract."""

import json

import numpy as np

from factorcon.models.generative import PatternData
from factorcon.pipeline.lofo_contract import (
    audit_exploratory_er_transfer,
    nonestimable_lofo_rows,
)


def family(name):
    """Create a four-condition E×R technical fixture, not empirical evidence."""
    design = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    return PatternData(
        name,
        tuple(f"{name}:{i}" for i in range(3)),
        ("E", "R"),
        np.zeros((3, 2, 4, 2)),
        design[None],
        np.zeros((4, 0)),
        np.eye(8),
        "reviewed_E_R_anchor",
        (f"{name}:cal",),
    )


def save(path, data, **changes):
    """Write only the pattern metadata consumed by the audit (no neural outcomes)."""
    meta = {
        "source_kind": "derived_neural_patterns",
        "family": data.family,
        "anchor_id": data.anchor_id,
        "units": "independent_residual_SD",
        "feature_definition": "fixed_cortical_parcels",
        "noise_definition": "independent_calibration",
        "condition_ids": ["e0r0", "e0r1", "e1r0", "e1r1"],
        "feature_ids": ["p1", "p2"],
        "partition_ids": ["r1", "r2"],
        "sensory_definition": "no_covariates_in_fixture",
        "transfer_bridge": {
            "schema_version": 1,
            "estimand": "exploratory_report_evidence_E_R",
            "calibration_status": "independent_external_reviewed",
            "id": "fixture_only",
            "sha256": "a" * 64,
        },
    }
    meta.update(changes)
    np.savez(path, metadata=json.dumps(meta))


def test_audit_requires_external_bridge_and_common_axes(tmp_path):
    a, b = family("a"), family("b")
    pa, pb = tmp_path / "a.npz", tmp_path / "b.npz"
    save(pa, a)
    save(pb, b)
    assert audit_exploratory_er_transfer((pa, pb), (a, b)) == ()
    save(pb, b, transfer_bridge=None, feature_ids=["p1", "wrong"])
    issues = audit_exploratory_er_transfer((pa, pb), (a, b))
    assert any("reviewed" in item for item in issues)
    assert any("feature_ids differs" in item for item in issues)
    rows = nonestimable_lofo_rows((a, b), issues)["rows"]
    assert len(rows) == 12
    assert all(row["status"] == "not_estimable" and "scores_nats" not in row for row in rows)


def test_audit_rejects_rank_deficient_design(tmp_path):
    a, b = family("a"), family("b")
    b.design_draws[:, :, 1] = b.design_draws[:, :, 0]
    pa, pb = tmp_path / "a.npz", tmp_path / "b.npz"
    save(pa, a)
    save(pb, b)
    assert any("rank deficient" in x for x in audit_exploratory_er_transfer((pa, pb), (a, b)))
