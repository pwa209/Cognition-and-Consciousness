"""Technical recovery using original science releases, immutable attempts and verified tars."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from factorcon.alliance import read_source_record, validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def load_module(name: str, path: Path) -> ModuleType:
    """Load reviewed, release-verified local Python; never execute downloaded dataset code."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("missing module loader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_source(root: Path, source: Path) -> None:
    """Require authorized source and exact tracked hashes; no participant outcomes inspected."""
    record = read_source_record(root, source)
    if not record.get("analysis_execution_authorized") or any(
        hash_file(source / p) != digest for p, digest in record["files"].items()
    ):
        raise ValueError("authorized intact source required")


def terminal(job: str) -> list[str]:
    """Require Slurm accounting to show only terminal states, in scheduler state units."""
    if not job.isdigit():
        raise ValueError("numeric job required")
    result = subprocess.run(
        ["sacct", "-n", "-X", "-P", "-j", job, "--format=State"],
        capture_output=True,
        text=True,
        check=True,
        timeout=45,
    )
    states = [line.split("|")[0].split()[0] for line in result.stdout.splitlines() if line.strip()]
    allowed = {"COMPLETED", "CANCELLED", "FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"}
    if not states or any(s not in allowed for s in states):
        raise ValueError(f"job {job} not proven quiescent: {states}")
    return states


def resolve_qualification_job(operations: Path) -> str:
    """Resolve the exact qualification job explicitly, with legacy receipt fallback."""
    job = os.environ.get("FACTORCON_QUALIFICATION_JOB")
    if job is None:
        job = load_structured(operations / "qualification.json").get("job_id")
    if not isinstance(job, str) or not job.isdigit():
        raise ValueError("numeric recovery qualification job required")
    return job


def archive_work(root: Path, repair: Path, work: Path, destination: Path) -> dict[str, Any]:
    """Copy/verify then retire only an MRI work tree; byte reserve remains 500 GB.

    This inode-reducing operation needs only 50 free files, not the analysis reserve.
    The caller must prove that no process writes this tree. No data fitting occurs.
    """
    fixed = load_module("repair_archive_quota", repair / "src/factorcon/alliance.py")
    archive = load_module("repair_work_archive", repair / "src/factorcon/work_archive.py")
    if destination.exists():
        return archive.retire(root, work, destination)
    description = archive.pack(root, work, destination, dry_run=True)
    quota = fixed.read_personal_quota()
    # Include PAX headers and final padding, not just source payload sizes.
    archive_budget = description["source_bytes"] + description["members"] * 8192 + 10240
    if quota.limit_bytes - quota.used_bytes < archive_budget + 500_000_000_000:
        raise ValueError("insufficient personal byte headroom for verified archive")
    if quota.limit_files - quota.used_files < 50:
        raise ValueError("insufficient archive metadata headroom")
    print("ARCHIVE_BEGIN", json.dumps(description), flush=True)
    archive.pack(root, work, destination)
    result = archive.retire(root, work, destination)
    print("ARCHIVE_RETIRED", json.dumps(result), flush=True)
    return result


def monitored_run(command: list[str], *, guard: Any, interval: float = 60, **kwargs: Any) -> Any:
    """Run fMRIPrep with periodic personal quota checks, killing its process group on failure.

    Guard measures bytes/files, not results. This POSIX helper never changes command
    arguments. Original child logs remain at their attempt paths after interruption.
    """
    check = kwargs.pop("check", False)
    process = subprocess.Popen(command, start_new_session=True, **kwargs)
    try:
        while True:
            try:
                code = process.wait(timeout=interval)
                break
            except subprocess.TimeoutExpired:
                guard(0)
        if check and code:
            raise subprocess.CalledProcessError(code, command)
        return subprocess.CompletedProcess(command, code)
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=30)
        raise


class _ProcessProxy:
    def __init__(self, guard: Any, interval: float) -> None:
        self.guard, self.interval = guard, interval

    def __getattr__(self, key: str) -> Any:
        return getattr(subprocess, key)

    def run(self, command: list[str], **kwargs: Any) -> Any:
        if "fmriprep" not in command:
            raise ValueError("live monitor only accepts original fMRIPrep invocation")
        return monitored_run(command, guard=self.guard, interval=self.interval, **kwargs)


def retry_legacy(root: Path, repair: Path, plan: dict[str, Any], mode: str) -> None:
    """Execute original MRI/simulation code with quota and optional warning-signature repairs.

    Python must start with the original release's PYTHONPATH. Preserve seeds,
    scenario counts, model code, calibration partition and configuration hashes.
    Every retry has a new Slurm attempt; no historical status file is rewritten.
    """
    import factorcon.alliance as legacy_quota

    source = root / "releases" / plan[f"{mode}_source"] / "source"
    verify_source(root, source)
    if Path(legacy_quota.__file__).resolve() != source / "src/factorcon/alliance.py":
        raise ValueError("legacy science must be imported from its original release")
    fixed = load_module("repair_live_quota", repair / "src/factorcon/alliance.py")
    legacy_quota.parse_personal_quota = fixed.parse_personal_quota
    sys.path.insert(0, str(source / "scripts/alliance"))
    if mode == "pattern":
        module = load_module("legacy_pattern_shard", source / "scripts/alliance/stress_shard.py")
        task = int(os.environ["SLURM_ARRAY_TASK_ID"])
        old = (
            root
            / "analysis/P05/patterns"
            / f"replicate-{task:03d}"
            / plan["pattern_failed_array"]
            / "status.json"
        )
        previous = load_structured(old)
        if (
            previous.get("status") != "FAILED"
            or previous.get("error")
            != "CapacityError: unrecognized diskusage_report personal quota format"
        ):
            raise ValueError("retry only original quota-parser failures")
        if hash_file(source / "conf/pattern_stress.yaml") != previous["source_plan_sha256"]:
            raise ValueError("simulation plan changed")
        base = [
            "stress_shard.py",
            "--root",
            str(root),
            "--suite",
            "patterns",
            "--replicate",
            str(task),
        ]
        sys.argv = [*base, "--dry-run"]
        module.main()
        sys.argv = base
        module.main()
        return
    index = int(os.environ["FACTORCON_SUBJECT_INDEX"])
    if index not in plan["mri_subject_indices"]:
        raise ValueError("MRI retry excludes completed pilot")
    module = load_module("legacy_masked_neural", source / "scripts/alliance/masked_neural_phase.py")
    job = os.environ["SLURM_JOB_ID"]
    attempt = root / "analysis/masked-neural/PREPROCESS" / f"{job}-{index}"
    guard = fixed.ScratchQuotaGuard(
        root / "operations/inode-recovery" / repair.parent.name / f"live-quota-{job}.json",
        reserve_files=plan["mri_start_free_files"],
        reserve_bytes=plan["live_reserve_bytes"],
        stale_grace_seconds=plan.get("quota_stale_grace_seconds", 0),
        stale_charge_bytes=plan.get("quota_stale_charge_bytes", 0),
        stale_charge_files=plan.get("quota_stale_charge_files", 0),
        stale_reserve_bytes=plan.get("quota_stale_reserve_bytes"),
        stale_reserve_files=plan.get("quota_stale_reserve_files"),
    )
    guard(0)
    guard.reserve_files = plan["live_reserve_files"]
    guard.stale_reserve_files = max(
        plan["live_reserve_files"], plan.get("quota_stale_reserve_files", 0)
    )
    module.subprocess = _ProcessProxy(guard, plan["quota_interval_seconds"])
    if spec := plan.get("warning_compatibility"):
        compatibility = load_module(
            "warning_compatibility", repair / "scripts/alliance/fmriprep_warning_compat.py"
        )
        patch = compatibility.prepare_patch(root, repair, spec)
        original_runtime = module.runtime

        def patched_runtime(*args: Any) -> Any:
            prefix, env = original_runtime(*args)
            return compatibility.bind_patch(prefix, patch, spec), env

        module.runtime = patched_runtime
    kwargs = {
        "p03": root / "analysis/P03/masked_content_fmri" / plan["p03_job"] / "status.json",
        "producer": root / "releases" / plan["p03_source"] / "source",
        "prepared": root / "analysis/masked-neural/PREPARE" / plan["prepared_job"] / "status.json",
        "subject_index": index,
    }
    module.run_phase(root, source, "PREPROCESS", attempt, dry_run=True, **kwargs)
    module.run_phase(root, source, "PREPROCESS", attempt, **kwargs)
    archive_work(root, repair, attempt / "work", root / "archives/mri-work" / attempt.name)


def main() -> int:
    """Run a Slurm recovery stage with atomic status/provenance and unchanged scientific fitting."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["archive", "qualify", "mri", "pattern"], required=True)
    parser.add_argument(
        "--plan",
        choices=[
            "inode_recovery_plan.yaml",
            "mri_warning_recovery_plan.yaml",
            "mri_quota_recovery_plan.yaml",
        ],
        default="inode_recovery_plan.yaml",
    )
    args = parser.parse_args()
    repair = Path(__file__).resolve().parents[2]
    plan_path = repair / "conf" / args.plan
    plan = load_structured(plan_path)
    root = validate_fresh_root(Path(plan["root"]))
    verify_source(root, repair)
    job = os.environ["SLURM_JOB_ID"]
    task = os.environ.get("SLURM_ARRAY_TASK_ID", "single")
    if not job.isdigit():
        raise ValueError("Slurm numeric identity required")
    os.umask(0o077)
    operations = root / "operations/inode-recovery" / repair.parent.name
    attempt = operations / f"{args.mode}-{job}-{task}"
    attempt.mkdir(parents=True, exist_ok=False)
    details = {
        "status": "RUNNING",
        "mode": args.mode,
        "repair_source": str(repair),
        "plan_sha256": hash_file(plan_path),
        "plan": args.plan,
        "job": job,
        "task": task,
        "started_utc": utc_now(),
        "scientific_changes": False,
        "original_source": plan.get(f"{args.mode}_source"),
        "python": sys.executable,
    }

    def record() -> None:
        atomic_write_json(attempt / "status.json", details)
        atomic_write_json(attempt / "provenance.json", details)

    def stop(signum: int, _frame: object) -> None:
        raise InterruptedError(f"scheduler signal {signum}")

    signal.signal(signal.SIGTERM, stop)
    record()
    try:
        if args.mode == "archive":
            details["old_scheduler_states"] = {
                j: terminal(j) for j in ["21417199", plan["old_mri_array"]]
            }
            record()
            # Run byte-exact lifecycle tests before touching any large work trees.
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp",
                    str(attempt / "tests"),
                    "tests/unit/test_work_archive.py",
                    "tests/unit/test_alliance.py",
                ],
                cwd=repair,
                check=True,
            )
            for name in plan["archive_attempts"]:
                terminal(name.split("-")[0])
                archive_work(
                    root,
                    repair,
                    root / "analysis/masked-neural/PREPROCESS" / name / "work",
                    root / "archives/mri-work" / name,
                )
        elif args.mode == "qualify":
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp",
                    str(attempt / "tests"),
                    "--junitxml",
                    str(attempt / "tests.xml"),
                ],
                cwd=repair,
                check=True,
            )
            if spec := plan.get("warning_compatibility"):
                compatibility = load_module(
                    "warning_compatibility", repair / "scripts/alliance/fmriprep_warning_compat.py"
                )
                patch = compatibility.prepare_patch(root, repair, spec)
                source = root / "releases" / plan["mri_source"] / "source"
                verify_source(root, source)
                sys.path.insert(0, str(source / "scripts/alliance"))
                legacy = load_module(
                    "qualify_masked_runtime", source / "scripts/alliance/masked_neural_phase.py"
                )
                prefix, env = legacy.runtime(
                    root, load_structured(source / "conf/masked_neural_plan.yaml")
                )
                for mode in ["baseline", "patched"]:
                    command = (
                        prefix
                        if mode == "baseline"
                        else compatibility.bind_patch(prefix, patch, spec)
                    )
                    with (attempt / f"warning-smoke-{mode}.log").open("x") as stream:
                        subprocess.run(
                            [
                                *command,
                                "python",
                                str(repair / "scripts/alliance/warning_compat_smoke.py"),
                                "--mode",
                                mode,
                                "--output",
                                str(attempt / f"smoke-{mode}"),
                            ],
                            env=env,
                            stdout=stream,
                            stderr=subprocess.STDOUT,
                            check=True,
                            timeout=300,
                        )
                details["warning_smoke_passed"] = True
                details["warning_patch_sha256"] = hash_file(patch)
                details["warning_smoke_sha256"] = {
                    path.name: hash_file(path) for path in attempt.glob("warning-smoke-*.log")
                }
        else:
            qualification = resolve_qualification_job(operations)
            state = load_structured(operations / f"qualify-{qualification}-single/status.json")
            if (
                state.get("status") != "SUCCESS"
                or state.get("repair_source") != str(repair)
                or state.get("plan_sha256") != hash_file(plan_path)
            ):
                raise ValueError("successful same-repair qualification required")
            if plan.get("warning_compatibility") and state.get("warning_smoke_passed") is not True:
                raise ValueError("container warning regression must pass")
            retry_legacy(root, repair, plan, args.mode)
        details.update(status="SUCCESS", ended_utc=utc_now())
    except BaseException as exc:
        details.update(status="FAILED", ended_utc=utc_now(), error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        record()
    print(json.dumps(details), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
