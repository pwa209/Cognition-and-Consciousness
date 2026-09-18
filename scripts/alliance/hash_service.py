"""Compute-node-only digest worker for acquisition; no external network access."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import time
from pathlib import Path

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, ensure_within, hash_file, utc_now


def main() -> int:
    """Process same-run raw-file digest requests under one Slurm allocation.

    Each result is bound to bytes/mtime, with atomic status and provenance. No code
    supplied in a request is executed; scientific values are neither read nor selected.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    root = validate_fresh_root(args.root)
    if not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Hash service requires a compute allocation")
    read_source_record(root, Path(__file__).resolve().parents[2])
    os.environ.pop("FACTORCON_HASH_QUEUE", None)
    os.umask(0o077)
    queue = root / "operations/hash-service"
    for name in ["requests", "results"]:
        (queue / name).mkdir(parents=True, exist_ok=True)

    def state(status: str, **details: object) -> None:
        atomic_write_json(
            queue / "status.json",
            {
                "status": status,
                "updated_utc": utc_now(),
                "job_id": os.environ["SLURM_JOB_ID"],
                "host": os.uname().nodename,
                **details,
            },
        )

    def stop(signum: int, frame: object) -> None:
        state("INTERRUPTED", signal=signum)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    with (queue / "worker.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            state("READY")
            for p in sorted((queue / "requests").glob("*.json")):
                result = queue / "results" / p.name
                if result.exists():
                    continue
                request = json.loads(p.read_text())
                try:
                    target = ensure_within(root / "data/raw", Path(request["path"]).resolve())
                    if request["algorithm"] not in {"sha256", "md5"}:
                        raise ValueError("algorithm")
                    before = target.stat()
                    if (before.st_size, before.st_mtime_ns) != (
                        request["size"],
                        request["mtime_ns"],
                    ):
                        raise ValueError("request identity changed")
                    state("HASHING", request_id=p.stem, bytes=before.st_size)
                    digest = hash_file(target, request["algorithm"])
                    after = target.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError("file changed while hashing")
                    atomic_write_json(
                        result,
                        {
                            "status": "SUCCESS",
                            "request": request,
                            "digest": digest,
                            "completed_utc": utc_now(),
                            "job_id": os.environ["SLURM_JOB_ID"],
                        },
                    )
                except Exception as exc:
                    atomic_write_json(
                        result,
                        {
                            "status": "FAILED",
                            "request": request,
                            "error": f"{type(exc).__name__}: {exc}",
                            "completed_utc": utc_now(),
                        },
                    )
            if args.once:
                state("SUCCESS")
                return 0
            terminal = []
            for family in ["cogitate", "propofol_volition_fmri"]:
                marker = root / "operations/acquisition-repair-v1" / family / "status.json"
                terminal.append(
                    marker.exists()
                    and json.loads(marker.read_text()).get("status")
                    in {"SUCCESS", "FINISHED_WITH_HOLDS"}
                )
            if all(terminal):
                state("SUCCESS", reason="both acquisition families finished")
                return 0
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
