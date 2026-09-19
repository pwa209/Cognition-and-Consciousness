"""Prefetch public MRI reference templates inside the installed container on login.

This is reference acquisition, not participant analysis. All downloads/cache/tmp
are on personal scratch. Invoke via the dedicated shell wrapper, never locally.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    """Download public reference files and issue an atomic, hash-bound runtime receipt."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    if (
        root.parent != Path("/scratch/pwa209/cognition-and-consciousness")
        or not root.name.startswith("fresh-")
        or root.resolve() != root
    ):
        raise ValueError("personal fresh study root required")
    if root.stat().st_uid != os.getuid() or not socket.gethostname().startswith("rorqual"):
        raise ValueError("owner login-node acquisition only")
    import fmriprep
    from templateflow import api, conf

    if fmriprep.__version__ != "25.1.3" or root / "cache/templateflow" != conf.TF_HOME:
        raise ValueError("runtime version/cache mismatch")
    output = root / "operations/masked-runtime"
    output.mkdir(parents=True, exist_ok=True)
    attempt = output / datetime.now(UTC).strftime("attempt-%Y%m%dT%H%M%S%fZ")
    attempt.mkdir()
    state = {
        "status": "RUNNING",
        "fmriprep_version": fmriprep.__version__,
        "module_label": "fmriprep/25.1.1",
        "scientific_gate": None,
        "started_utc": datetime.now(UTC).isoformat(),
        "participant_data_analyzed": False,
    }

    def write(name: str) -> None:
        archive = attempt / name
        archive_tmp = attempt / (name + ".tmp")
        archive_tmp.write_text(json.dumps(state, indent=2))
        archive_tmp.replace(archive)
        temp = output / (name + ".tmp")
        temp.write_text(json.dumps(state, indent=2))
        temp.replace(output / name)

    write("status.json")
    try:
        for template in ("OASIS30ANTs", "MNI152NLin2009cAsym", "MNI152NLin6Asym"):
            print("PREFETCH_TEMPLATE", template, flush=True)
            paths = api.get(template, raise_empty=True)
            if isinstance(paths, Path):
                paths = [paths]
            if not paths or any(not p.is_file() or p.stat().st_size == 0 for p in paths):
                raise ValueError("incomplete template download")
        files = {}
        for template in ("OASIS30ANTs", "MNI152NLin2009cAsym", "MNI152NLin6Asym"):
            for p in sorted((conf.TF_HOME / ("tpl-" + template)).rglob("*")):
                if p.is_file():
                    p.resolve().relative_to(conf.TF_HOME)
                    if p.stat().st_size == 0:
                        raise ValueError("empty template file")
                    with p.open("rb") as stream:
                        files[p.relative_to(conf.TF_HOME).as_posix()] = hashlib.file_digest(
                            stream, "sha256"
                        ).hexdigest()
        state.update(
            status="SUCCESS",
            template_files=files,
            ended_utc=datetime.now(UTC).isoformat(),
            packages={
                k: importlib.metadata.version(k)
                for k in (
                    "fmriprep",
                    "smriprep",
                    "niworkflows",
                    "templateflow",
                    "nipype",
                    "nibabel",
                )
            },
        )
        write("ready.json")
        print("MASKED_RUNTIME_READY", len(files), flush=True)
    except BaseException as exc:
        state.update(
            status="FAILED",
            error=f"{type(exc).__name__}: {exc}",
            ended_utc=datetime.now(UTC).isoformat(),
        )
        raise
    finally:
        write("status.json")
        write("provenance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
