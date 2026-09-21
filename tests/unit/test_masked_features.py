"""Tiny source/linear-operator fixtures; no empirical participant data."""

import csv
import hashlib
import io
import json
import tarfile
from pathlib import Path

import numpy as np
import pytest

from factorcon.errors import IntegrityError
from factorcon.pipeline.masked_auxiliary import read_member, select_behavior
from factorcon.pipeline.masked_features import (
    ar_transform,
    combine_partitions,
    estimate_ar1,
    linear_summary,
    run_design,
    validate_feature_plan,
)
from factorcon.pipeline.masked_timing import align_run, behavior_path, behavior_trials, git_blob_sha

ROOT = Path(__file__).resolve().parents[2]


def test_source_timing_and_missing_reports():
    behavior = (ROOT / "tests/fixtures/masked_timing/behavior.csv").read_bytes()
    trials = behavior_trials(behavior)
    assert [t["trial"] for t in trials] == [1, 2]
    assert trials[1]["report"] == -1
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=[
            "onset",
            "duration",
            "trials",
            "visibility",
            "paths",
            "targets",
            "volume_interest",
            "probe_frame",
        ],
        delimiter="\t",
    )
    writer.writeheader()
    for t in range(20):
        trial = None if t == 0 else trials[0 if t < 11 else 1]
        writer.writerow(
            {
                "onset": t,
                "duration": 1,
                "trials": 0 if trial is None else trial["trial"],
                "visibility": "n/a"
                if trial is None
                else "unconscious"
                if t < 11
                else "missing data",
                "paths": "n/a" if trial is None else trial["stimulus_id"],
                "targets": "Living_Things" if t < 11 else "Nonliving_Things",
                "volume_interest": int(6 < t < 9 or 16 < t < 19),
                "probe_frame": 2 if t < 11 else 3,
            }
        )
    data = out.getvalue().encode()
    result = align_run(data, behavior, volumes=30, tr_seconds=1)
    assert result["trials"][0]["image_onset_seconds"] == 12
    assert result["event_alignment_verified"]
    with pytest.raises(ValueError, match="volume-count"):
        align_run(data, behavior, volumes=20, tr_seconds=1)
    with pytest.raises(ValueError, match="linkage"):
        align_run(data.replace(b"bird.jpg", b"other.jpg"), behavior, volumes=30, tr_seconds=1)
    with pytest.raises(ValueError, match="order"):
        behavior_trials(behavior.replace(b"1,22", b"0,22"))


def test_packed_source_paths_counts_and_integrity():
    run = {"run_id": "sub-01_ses-02_task-recog_run-1", "subject": "sub-01", "session": "ses-02"}
    path = behavior_path(run)
    assert path == "data/behavioral/sub-01/session-02/sub-01_unfeat_run-01.csv"
    with pytest.raises(ValueError):
        behavior_path({**run, "run_id": "../../private"})
    blob = b"fixture"
    plan = {"publisher_revision": "abc", "expected_source_behavior_files": 1, "expected_runs": 1}
    tree = {
        "sha": "abc",
        "truncated": False,
        "tree": [{"type": "blob", "path": path, "sha": git_blob_sha(blob)}],
    }
    assert select_behavior(tree, [run], plan)[path] == git_blob_sha(blob)
    with pytest.raises(ValueError):
        select_behavior(tree, [run, run], plan)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        member = tarfile.TarInfo(path)
        member.size = len(blob)
        archive.addfile(member, io.BytesIO(blob))
        link = tarfile.TarInfo("link")
        link.type, link.linkname = tarfile.SYMTYPE, path
        archive.addfile(link)
    buffer.seek(0)
    expected = {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
    with tarfile.open(fileobj=buffer) as archive:
        assert read_member(archive, path, expected) == blob
        with pytest.raises(IntegrityError):
            read_member(archive, "../escape", expected)
        with pytest.raises(ValueError):
            read_member(archive, "link", {**expected, "bytes": 0})
        with pytest.raises(ValueError):
            read_member(archive, path, {**expected, "sha256": "0" * 64})


def test_fixed_linear_gls_and_aggregation():
    rng = np.random.default_rng(12)
    x, z = rng.normal(size=(100, 6)), np.column_stack([np.ones(100), np.linspace(-1, 1, 100)])
    beta = rng.normal(size=(6, 4))
    y = x @ beta + z @ rng.normal(size=(2, 4))
    summary = linear_summary(y, x, z, 0.3)
    patterns, noise = combine_partitions([summary, summary], [0, 1])
    assert np.allclose(patterns, np.stack([beta, beta]))
    assert np.linalg.eigvalsh(noise).min() > 0
    changed = linear_summary(y * 7, x, z, 0.3)
    assert np.array_equal(changed["information"], summary["information"])
    assert np.allclose(changed["score"], summary["score"] * 7)
    singular = {**summary, "information": np.zeros((6, 6))}
    with pytest.raises(ValueError, match="estimable"):
        combine_partitions([singular, singular], [0, 1])
    assert ar_transform(np.ones((5, 2)), 0).sum() == 10
    with pytest.raises(ValueError):
        ar_transform(y, 1)
    residual = rng.normal(size=(2000, 4))
    for i in range(1, len(residual)):
        residual[i] += 0.7 * residual[i - 1]
    assert abs(estimate_ar1([residual]) - 0.7) < 0.04


def test_design_unknown_report_not_condition_zero_and_technical_censoring():
    plan = json.loads((ROOT / "conf/masked_feature_plan.yaml").read_text())
    validate_feature_plan(plan)
    row = {"framewise_displacement": "0"}
    for name in ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"):
        row.update(
            {
                name + suffix: "0"
                for suffix in ("", "_derivative1", "_power2", "_derivative1_power2")
            }
        )
    row.update({f"a_comp_cor_{i:02d}": "0" for i in range(5)})
    rows = [row.copy() for _ in range(100)]
    trials = [{"trial": 1, "image_onset_seconds": 5.1, "report": -1, "nonliving": 0}]
    task, nuisance, audit = run_design(trials, rows, 0.85, 0.378, plan)
    assert not task.any() and nuisance[:, 1].any()
    assert audit["condition_counts"][6] == 1 and not audit["excluded"]
    for r in rows[:21]:
        r["framewise_displacement"] = "1"
    assert run_design(trials, rows, 0.85, 0.378, plan)[2]["excluded"]
