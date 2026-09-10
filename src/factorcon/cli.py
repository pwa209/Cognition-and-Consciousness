"""Command-line interface for configuration, acquisition, simulation, and status."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from factorcon.acquire import acquire_families, resolve_manifests
from factorcon.config import load_analysis_spec, load_project, validate_project
from factorcon.errors import FactorconError
from factorcon.models.architectures import ARCHITECTURES, unavailable_reason
from factorcon.pipeline import harmonize_family, validate_family
from factorcon.pipeline.canonical import (
    DEFAULT_SPEC,
    load_canonical_rdm,
    score_canonical_rdm,
    synthesize_scores,
)
from factorcon.pipeline.reporting import build_paper_tables
from factorcon.pipeline.robustness import robustness_canonical_rdm
from factorcon.simulation import run_recovery_suite
from factorcon.status import collect_status


def _families(values: list[str] | None) -> set[str] | None:
    return set(values) if values else None


def _root(args: argparse.Namespace, project: Any, *, require_confirmation: bool) -> Path:
    override = getattr(args, "canonical_root", None) or getattr(args, "out", None)
    if override:
        return Path(override)
    env = os.environ.get("FACTORCON_CANONICAL_ROOT")
    if env:
        return Path(env)
    if require_confirmation and project.server.get("roots_status") != "owner_confirmed":
        raise FactorconError(
            "Server roots are pending owner confirmation; pass an explicit --canonical-root "
            "for a safe test location or update conf/server_h100.yaml after confirmation"
        )
    return project.canonical_root


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    """Build the deterministic command surface."""

    parser = argparse.ArgumentParser(prog="factorcon")
    subcommands = parser.add_subparsers(dest="command", required=True)

    config = subcommands.add_parser("config", help="validate configuration contracts")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_validate = config_sub.add_parser("validate")
    config_validate.add_argument("--config", default="conf/base.yaml")

    manifest = subcommands.add_parser("manifest", help="resolve immutable source inventories")
    manifest_sub = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_resolve = manifest_sub.add_parser("resolve")
    manifest_resolve.add_argument("--config", default="conf/base.yaml")
    manifest_resolve.add_argument("--out")
    manifest_resolve.add_argument("--family", action="append")

    acquire = subcommands.add_parser(
        "acquire", help="download eligible public data directly to NAS"
    )
    acquire.add_argument("--config", default="conf/base.yaml")
    acquire.add_argument("--canonical-root")
    acquire.add_argument("--family", action="append")
    acquire.add_argument("--workers", type=int)
    acquire.add_argument("--no-resolve", action="store_true")
    acquire.add_argument(
        "--eligible-only",
        action="store_true",
        help="documented no-op; restricted access is never bypassed",
    )

    dataset = subcommands.add_parser("dataset", help="validate or harmonize one downloaded family")
    dataset_sub = dataset.add_subparsers(dest="dataset_command", required=True)
    dataset_validate = dataset_sub.add_parser("validate")
    dataset_validate.add_argument("--config", default="conf/base.yaml")
    dataset_validate.add_argument("--canonical-root")
    dataset_validate.add_argument("--family", required=True)
    dataset_validate.add_argument("--output", required=True)
    dataset_validate.add_argument("--deep-hash", action="store_true")
    dataset_harmonize = dataset_sub.add_parser("harmonize")
    dataset_harmonize.add_argument("--config", default="conf/base.yaml")
    dataset_harmonize.add_argument("--canonical-root")
    dataset_harmonize.add_argument("--family", required=True)
    dataset_harmonize.add_argument("--output", required=True)
    dataset_harmonize.add_argument("--report", required=True)

    model = subcommands.add_parser("model", help="score canonical RDMs or synthesize families")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    model_score = model_sub.add_parser("score")
    model_score.add_argument("--family", required=True)
    model_score.add_argument("--input", required=True)
    model_score.add_argument("--output", required=True)
    model_synthesize = model_sub.add_parser("synthesize")
    model_synthesize.add_argument("--input", action="append", required=True)
    model_synthesize.add_argument("--output", required=True)
    model_robustness = model_sub.add_parser("robustness")
    model_robustness.add_argument("--family", required=True)
    model_robustness.add_argument("--input", required=True)
    model_robustness.add_argument("--output", required=True)
    model_robustness.add_argument("--seed", type=int, default=260830)
    for model_parser in (model_score, model_synthesize, model_robustness):
        model_parser.add_argument("--analysis-spec", default=str(DEFAULT_SPEC))
    for model_parser in (model_score, model_robustness):
        model_parser.add_argument("--dry-run", action="store_true", help="validate without writing")

    report = subcommands.add_parser("report", help="build auditable paper-source tables")
    report.add_argument("--score", action="append", required=True)
    report.add_argument("--synthesis", required=True)
    report.add_argument("--output-directory", required=True)

    simulate = subcommands.add_parser("simulate", help="run synthetic architecture recovery")
    simulate.add_argument(
        "--architecture", choices=["all", "M0", "M1", "M2", "M3", "M4"], default="all"
    )
    simulate.add_argument("--seed", type=int, default=260830)
    simulate.add_argument("--out", default="results/synthetic")

    status = subcommands.add_parser("status", help="summarize run-state markers")
    status.add_argument("--config", default="conf/base.yaml")
    status.add_argument("--canonical-root")
    return parser


def dispatch(args: argparse.Namespace) -> int:
    """Execute parsed arguments and print a JSON result."""

    if args.command == "config" and args.config_command == "validate":
        _print(validate_project(args.config))
        return 0
    if args.command == "manifest" and args.manifest_command == "resolve":
        project = load_project(args.config)
        root = _root(args, project, require_confirmation=args.out is None)
        _print(resolve_manifests(project, root, families=_families(args.family)))
        return 0
    if args.command == "acquire":
        project = load_project(args.config)
        root = _root(args, project, require_confirmation=args.canonical_root is None)
        expected_host = str(project.server["expected_hostname"])
        if args.canonical_root is None and socket.gethostname() != expected_host:
            raise FactorconError(
                f"Default acquisition root may be used only on {expected_host}; "
                f"current host is {socket.gethostname()}"
            )
        result = acquire_families(
            project,
            root,
            families=_families(args.family),
            workers=args.workers,
            resolve=not args.no_resolve,
        )
        _print(result)
        return 0 if result["all_public_success"] else 3
    if args.command == "dataset":
        project = load_project(args.config)
        root = Path(args.canonical_root) if args.canonical_root else project.canonical_root
        if args.dataset_command == "validate":
            result = validate_family(
                project,
                root,
                args.family,
                args.output,
                deep_hash=args.deep_hash,
            )
        else:
            result = harmonize_family(
                project,
                root,
                args.family,
                args.output,
                args.report,
            )
        _print(result)
        return 0
    if args.command == "model":
        if getattr(args, "dry_run", False):
            spec = load_analysis_spec(args.analysis_spec)
            arrays, design = load_canonical_rdm(args.input)
            _print(
                {
                    "dry_run": True,
                    "writes": False,
                    "family": args.family,
                    "train_groups": len(set(arrays["train_group_ids"])),
                    "test_groups": len(set(arrays["test_group_ids"])),
                    "implementation": spec["rdm_evaluation"]["implementation"],
                    "unavailable_reasons": {
                        m: unavailable_reason(m, design) for m in ARCHITECTURES
                    },
                }
            )
            return 0
        if args.model_command == "score":
            result = score_canonical_rdm(
                args.input, args.output, family=args.family, analysis_spec=args.analysis_spec
            )
        elif args.model_command == "synthesize":
            result = synthesize_scores(args.input, args.output, analysis_spec=args.analysis_spec)
        else:
            result = robustness_canonical_rdm(
                args.input,
                args.output,
                family=args.family,
                seed=args.seed,
                analysis_spec=args.analysis_spec,
            )
        _print(result)
        return 0
    if args.command == "report":
        _print(build_paper_tables(args.score, args.synthesis, args.output_directory))
        return 0
    if args.command == "simulate":
        architectures = (
            ["M0", "M1", "M2", "M3", "M4"] if args.architecture == "all" else [args.architecture]
        )
        _print(run_recovery_suite(architectures, seed=args.seed, output=args.out))
        return 0
    if args.command == "status":
        project = load_project(args.config)
        root = Path(args.canonical_root) if args.canonical_root else project.canonical_root
        _print(collect_status(root))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point with concise expected-error reporting."""

    try:
        return dispatch(build_parser().parse_args(argv))
    except (FactorconError, ValueError, FileNotFoundError) as exc:
        print(f"factorcon: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
