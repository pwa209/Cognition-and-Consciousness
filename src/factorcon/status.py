"""Read-only status aggregation for local or remote canonical roots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def collect_status(root: str | Path) -> dict[str, Any]:
    """Collect phase and family marker files without changing run state."""

    canonical = Path(root)
    records: list[dict[str, Any]] = []
    state = canonical / "run_state"
    if state.is_dir():
        for path in sorted(state.rglob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                records.append({"path": str(path), "status": "unreadable", "error": str(exc)})
                continue
            records.append({"path": str(path.relative_to(canonical)), "record": value})
    return {"canonical_root": str(canonical), "exists": canonical.exists(), "records": records}

