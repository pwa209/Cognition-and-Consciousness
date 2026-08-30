"""Standard-library-only command surface for NAS data acquisition deployments."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from typing import Any

from factorcon.acquire import acquire_families, acquisition_capacity, resolve_manifests
from factorcon.config import load_project, validate_project
from factorcon.errors import FactorconError


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factorcon-acquisition")
    parser.add_argument("action", choices=("validate", "resolve", "capacity", "download"))
    parser.add_argument("--config", default="conf/base.yaml")
    parser.add_argument("--canonical-root")
    parser.add_argument("--family", action="append")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--no-resolve", action="store_true")
    return parser


def dispatch(args: argparse.Namespace) -> int:
    if args.action == "validate":
        _print(validate_project(args.config))
        return 0

    project = load_project(args.config)
    root = Path(args.canonical_root) if args.canonical_root else project.canonical_root
    if args.canonical_root is None:
        if project.server.get("roots_status") != "owner_confirmed":
            raise FactorconError("Canonical root has not been confirmed by the project owner")
        expected_host = str(project.server["expected_hostname"])
        if socket.gethostname() != expected_host:
            raise FactorconError(
                f"Default acquisition root may be used only on {expected_host}; "
                f"current host is {socket.gethostname()}"
            )
    families = set(args.family) if args.family else None
    if args.action == "resolve":
        _print(resolve_manifests(project, root, families=families))
        return 0
    if args.action == "capacity":
        result = acquisition_capacity(project, root, families=families)
        _print(result)
        return 0 if result["sufficient_known_capacity"] else 4

    result = acquire_families(
        project,
        root,
        families=families,
        workers=args.workers,
        resolve=not args.no_resolve,
    )
    _print(result)
    return 0 if result["all_public_success"] else 3


def main(argv: list[str] | None = None) -> int:
    try:
        return dispatch(build_parser().parse_args(argv))
    except FactorconError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
