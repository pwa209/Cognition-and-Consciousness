"""Detached, single-worker publisher acquisition into the personal fresh-run scratch.

No university-server data, other-project caches or earlier completion records enter
this run. Individual source failures remain explicit and do not suppress later sources.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import signal
import traceback
from pathlib import Path
from typing import Any

from factorcon.acquire import acquire_families, resolve_manifests
from factorcon.alliance import (
    ScratchQuotaGuard,
    read_source_record,
    scratch_environment,
    validate_fresh_root,
)
from factorcon.config import load_project
from factorcon.util import atomic_write_json, hash_file, utc_now


def main() -> int:
    """Run acquisition only, with durable status/provenance and whole-run process lock."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("conf/base.yaml"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    project = load_project(args.config)
    marker = read_source_record(root, project.root)
    for path in [args.config, *(d.path for d in project.datasets)]:
        relative = path.resolve().relative_to(project.root.resolve()).as_posix()
        if hash_file(path) != marker["files"][relative]:
            raise ValueError(f"acquisition configuration changed: {relative}")
    paths = scratch_environment(root)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "root": str(root),
                    "cache_paths": paths,
                    "families": [d.family for d in project.datasets],
                }
            )
        )
        return 0
    for key, value in paths.items():
        Path(value).mkdir(parents=True, exist_ok=True)
        os.environ[key] = value
    operations = root / "operations/acquisition"
    operations.mkdir(parents=True, exist_ok=True)
    attempt = utc_now().replace(":", "").replace("-", "")
    status_path = operations / "status.json"
    provenance_path = operations / f"attempt-{attempt}.json"
    guard = ScratchQuotaGuard(operations / "personal-quota.json")
    results: dict[str, Any] = {}

    def state(status: str, **details: Any) -> None:
        value = {
            "status": status,
            "updated_utc": utc_now(),
            "attempt": attempt,
            "root": str(root),
            "pid": os.getpid(),
            "families": results,
            "workers": 1,
            "analysis_jobs_launched": [],
            "scientific_gates": False,
            "config_sha256": hash_file(args.config),
            "analysis_spec_sha256": hash_file(project.root / project.values["analysis_spec"]),
            "source_release": str(project.root),
            **details,
        }
        atomic_write_json(status_path, value)
        atomic_write_json(provenance_path, value)

    def interrupted(signum: int, frame: object) -> None:
        state(
            "INTERRUPTED",
            signal=signum,
            restart="resume verified files and partials in this fresh run",
        )
        raise SystemExit(128 + signum)

    with (operations / "campaign.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        state("RUNNING")
        try:
            guard(0)
            # Small anchor first; then EEG, masked fMRI, registry, large fMRI/BMVP.
            order = [
                "multisite_working_memory",
                "propofol_awakening_eeg",
                "masked_content_fmri",
                "dream",
                "cogitate",
                "propofol_volition_fmri",
                "bmvp",
            ]
            if set(order) != {d.family for d in project.datasets}:
                raise ValueError("campaign order does not cover the complete configured family set")
            for family in order:
                state("RUNNING", current_family=family)
                try:
                    guard(0)
                    dataset = next(d for d in project.datasets if d.family == family)
                    manifest = (
                        root / "manifests/generated" / family / f"{dataset.snapshot_label}.jsonl"
                    )
                    if not manifest.exists():
                        resolve_manifests(project, root, families={family})
                    if dataset.access == "account_and_terms_required":
                        results[family] = {"status": "WAITING_ACCESS"}
                        continue
                    result = acquire_families(
                        project,
                        root,
                        families={family},
                        workers=1,
                        resolve=False,
                        storage_guard=guard,
                    )["families"][family]
                    complete = result.get("success") is True
                    if family == "dream":
                        complete = complete and result.get("unresolved_constituents", 0) == 0
                        if result.get("constituents"):
                            complete = complete and result["constituents"].get("success") is True
                    results[family] = {
                        "status": "ACQUIRED" if complete else "PARTIAL_OR_HELD",
                        "details": result,
                    }
                except Exception as exc:
                    traceback.print_exc()
                    results[family] = {
                        "status": "SOURCE_OR_INTEGRITY_HOLD",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                finally:
                    state("RUNNING", current_family=None)
            complete = all(r["status"] == "ACQUIRED" for r in results.values())
            state("COMPLETE" if complete else "FINISHED_WITH_HOLDS", all_families_acquired=complete)
            return 0 if complete else 3
        except Exception as exc:
            state("FAILED", error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(lock, fcntl.LOCK_UN)


if __name__ == "__main__":
    raise SystemExit(main())
