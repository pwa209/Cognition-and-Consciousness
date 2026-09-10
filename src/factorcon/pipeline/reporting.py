"""Auditable tidy table and results-manifest generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from factorcon.util import atomic_write_json, hash_file, utc_now


def build_paper_tables(
    score_paths: list[str | Path],
    synthesis_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Build tidy model-score source data and map every value to its source hash."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    sources: dict[str, dict[str, str]] = {}
    for score_path in score_paths:
        source = Path(score_path)
        record = json.loads(source.read_text(encoding="utf-8"))
        sources[str(source)] = {"sha256": hash_file(source), "family": record["family"]}
        for model, score in record["scores"].items():
            rows.append(
                {
                    "dataset_family": record["family"],
                    "candidate_model": model,
                    "status": score.get("status", "legacy_unverified"),
                    "reason": score.get("reason", ""),
                    "score_kind": record.get("score_kind", "legacy_unspecified"),
                    "implementation": record.get("implementation", "legacy_unspecified"),
                    "model_scope": record.get("model_scope", {}).get(model, "legacy_unspecified"),
                    "log_score": score.get("log_score"),
                    "mse": score.get("mse"),
                    "effective_df": score.get("effective_df"),
                    "alpha": score.get("alpha"),
                    "source_file": str(source),
                    "source_sha256": sources[str(source)]["sha256"],
                }
            )
    table_path = output / "model_scores.tsv"
    with table_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]) if rows else ["dataset_family"], delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(rows)
    synthesis = Path(synthesis_path)
    sources[str(synthesis)] = {"sha256": hash_file(synthesis), "family": "cross_family"}
    manifest = {
        "created_utc": utc_now(),
        "tables": {
            "model_scores": {
                "path": str(table_path),
                "sha256": hash_file(table_path),
                "rows": len(rows),
            }
        },
        "sources": sources,
        "synthesis": {"path": str(synthesis), "sha256": hash_file(synthesis)},
        "claims": [],
        "note": (
            "Claims are added only after results exist; journal positioning is not an "
            "execution gate."
        ),
    }
    atomic_write_json(output / "results_manifest.json", manifest)
    return manifest
