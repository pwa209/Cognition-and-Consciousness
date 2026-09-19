"""Read-only neural artifact census, explicitly not an empirical P06-P10 analysis."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def census(root: Path) -> dict[str, Any]:
    """Count existing analysis artifacts; existence alone never certifies readiness."""
    counts: dict[str, dict[str, int]] = {}
    for path in (root / "analysis").glob("P*/**/status.json"):
        value = load_structured(path)
        phase = path.relative_to(root / "analysis").parts[0]
        status = value.get("status", "UNKNOWN")
        counts.setdefault(phase, {}).setdefault(status, 0)
        counts[phase][status] += 1
    return {
        "scope": "artifact_census_not_neural_preprocessing_or_model_fitting",
        "phase_status_counts": counts,
        "npz_candidates": [str(p.relative_to(root)) for p in (root / "analysis").rglob("*.npz")],
        "verified_empirical_campaign": False,
        "requirements": [
            "source_specific_preprocessing_and_event_report_linkage",
            "outcome_independent_features_conditions_partitions",
            "globally_disjoint_feature_noise_and_construct_calibration_subjects",
            "hash_bound_empirical_bundle_and_campaign",
        ],
        "scientific_gate": None,
    }


def main() -> int:
    """Write a provenance-backed read-only readiness audit inside personal scratch."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    if not args.job.isdigit():
        raise ValueError("numeric Slurm job ID required")
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if any(hash_file(source / p) != h for p, h in record["files"].items()):
        raise ValueError("source release changed")
    output = root / "operations/neural-readiness" / args.job
    output.mkdir(parents=True, exist_ok=False)
    state = {
        "status": "RUNNING",
        "source_release": str(source),
        "started_utc": utc_now(),
        "participant_data_analyzed": False,
        "scientific_gate": None,
    }
    for name in ("status.json", "provenance.json"):
        atomic_write_json(output / name, state)
    try:
        atomic_write_json(output / "readiness.json", census(root))
        state.update(status="SUCCESS", output_sha256=hash_file(output / "readiness.json"))
    except BaseException as exc:
        state.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        state["ended_utc"] = utc_now()
        for name in ("status.json", "provenance.json"):
            atomic_write_json(output / name, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
