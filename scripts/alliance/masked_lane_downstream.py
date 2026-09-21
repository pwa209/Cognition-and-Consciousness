"""Resolve a queued future bundle only from its same-release hashed SUCCESS receipt."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from downstream_phase import run_phase
from masked_lane_phase import proof

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, ensure_within, hash_file, load_structured


def resolve_bundle(root: Path, source: Path, config: dict[str, Any]) -> Path:
    """Resolve producer-bound campaign bytes after successful BUNDLE; never accept a placeholder."""
    directory = proof(root, config["bundle"], phase="BUNDLE", source=source)
    state = load_structured(directory / "status.json")
    if "campaign.json" not in state["outputs"]:
        raise ValueError("producer did not hash-bind a real campaign")
    return directory / "campaign.json"


def main() -> int:
    """Run queued P06-P10 against verified future producer artifacts and immutable Slurm graph."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    source = Path(__file__).resolve().parents[2]
    record = read_source_record(root, source)
    if record.get("analysis_execution_authorized") is not True or any(
        hash_file(source / p) != h for p, h in record["files"].items()
    ):
        raise ValueError("authorized immutable release required")
    ensure_within(root, args.input)
    if hash_file(args.input) != args.input_sha256:
        raise ValueError("submission graph bytes changed")
    config = load_structured(args.input)
    campaign = resolve_bundle(root, source, config)
    phase = config["stage"]
    job = os.environ.get("SLURM_ARRAY_JOB_ID", os.environ["SLURM_JOB_ID"])
    replicate = int(os.environ["SLURM_ARRAY_TASK_ID"]) if phase == "P09" else None
    suffix = f"{job}-{replicate}" if phase == "P09" else job
    graph = None
    if phase == "P10":
        # The submitted graph fixes all job IDs. Only the verified producer's campaign
        # digest is resolved later; no paths or models are selected from outcomes.
        graph = args.input.parent / f"resolved-graph-{job}.json"
        if graph.exists():
            raise FileExistsError("new P10 attempt/graph required")
        atomic_write_json(
            graph,
            {
                "schema_version": 1,
                "campaign_sha256": hash_file(campaign),
                "source_release": str(source),
                "families": ["masked_content_fmri"],
                "results": config["results"],
            },
        )
    result = run_phase(
        root,
        source,
        campaign,
        root / "analysis/downstream" / phase / suffix,
        phase,
        p06=root / config["p06"] if "p06" in config else None,
        graph=graph,
        replicate=replicate,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
