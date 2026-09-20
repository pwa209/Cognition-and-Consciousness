"""Queue verified consolidation, qualification, and storage-monitored original-code retries."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from inode_recovery import terminal, verify_source
from submit_empirical import submit_one

from factorcon.alliance import validate_fresh_root
from factorcon.util import atomic_write_json, hash_file, load_structured, utc_now


def failed_replicates(root: Path, plan: dict[str, Any]) -> list[int]:
    """Select failures by exact technical error, never by simulation scores; units are seed IDs."""
    source = root / "releases" / plan["pattern_source"] / "source"
    hashes = {
        key: hash_file(source / "conf" / filename)
        for key, filename in [
            ("source_plan_sha256", "pattern_stress.yaml"),
            ("analysis_spec_sha256", "analysis_spec.yaml"),
        ]
    }
    failed = []
    for p in sorted(
        (root / "analysis/P05/patterns").glob(f"*/{plan['pattern_failed_array']}/status.json")
    ):
        value = load_structured(p)
        if value.get("status") != "FAILED":
            continue
        if (
            value.get("error")
            != "CapacityError: unrecognized diskusage_report personal quota format"
        ):
            raise ValueError("unexpected failure class needs separate diagnosis")
        index = value["original_replicate"]
        if (
            p.parent.parent.name != f"replicate-{index:03d}"
            or value["seed"] != 260830 + index
            or any(value.get(k) != h for k, h in hashes.items())
        ):
            raise ValueError("original replicate/seed/source identity mismatch")
        if any(
            load_structured(s).get("status") == "SUCCESS"
            for s in p.parent.parent.glob("*/status.json")
        ):
            raise ValueError("already successful replicate must not be resubmitted")
        failed.append(index)
    if len(failed) != plan["expected_failed_replicates"] or len(set(failed)) != len(failed):
        raise ValueError("failed-replicate census mismatch")
    return failed


def main() -> int:
    """Submit one recoverable chain, protected against duplicate dispatch by durable receipts."""
    import fcntl

    repair = Path(__file__).resolve().parents[2]
    plan = load_structured(repair / "conf/inode_recovery_plan.yaml")
    root = validate_fresh_root(Path(plan["root"]))
    for source in [
        repair,
        *(root / "releases" / plan[f"{m}_source"] / "source" for m in ["mri", "pattern"]),
    ]:
        verify_source(root, source)
    terminal(plan["old_mri_array"])
    terminal(plan["pattern_failed_array"])
    failed = failed_replicates(root, plan)
    os.umask(0o077)
    operations = root / "operations/inode-recovery" / repair.parent.name
    operations.mkdir(parents=True, exist_ok=True)
    with (operations / "submit.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def dispatch(
            label: str, mode: str, dependency: str | None, resources: list[str], extra: str = ""
        ) -> str:
            source = (
                root / "releases" / plan[f"{mode}_source"] / "source"
                if mode in {"mri", "pattern"}
                else repair
            )
            environment = (
                plan[f"{mode}_environment"]
                if mode in {"mri", "pattern"}
                else plan["qualification_environment"]
            )
            if not (root / "environments" / environment / "bin/python").is_file():
                raise ValueError("original study-owned environment unavailable")
            env = (
                f"ALL,FACTORCON_RELEASE={repair},FACTORCON_MODE={mode},"
                f"FACTORCON_ENVIRONMENT={environment},FACTORCON_SCIENCE_SOURCE={source}{extra}"
            )
            command = [
                "sbatch",
                "--parsable",
                "--account=def-ptewarie_cpu",
                f"--job-name=fc-recover-{label}",
                f"--output={operations}/{label}-%A_%a.log",
                "--kill-on-invalid-dep=yes",
                *resources,
                f"--export={env}",
            ]
            if dependency:
                command.append(f"--dependency=afterok:{dependency}")
            command.append(str(repair / "scripts/alliance/inode_recovery.sbatch"))
            return submit_one(operations / f"{label}.json", command)

        archive = dispatch(
            "archive", "archive", None, ["--cpus-per-task=2", "--mem=8G", "--time=12:00:00"]
        )
        qualification = dispatch(
            "qualification",
            "qualify",
            archive,
            ["--cpus-per-task=4", "--mem=16G", "--time=01:00:00"],
        )
        pattern = dispatch(
            "patterns",
            "pattern",
            qualification,
            [
                "--cpus-per-task=4",
                "--mem=16G",
                "--time=12:00:00",
                "--array=" + ",".join(map(str, failed)) + "%1",
            ],
        )
        jobs = {"archive": archive, "qualification": qualification, "patterns": pattern}
        previous = qualification
        for index in plan["mri_subject_indices"]:
            previous = dispatch(
                f"mri-{index}",
                "mri",
                previous,
                ["--cpus-per-task=8", "--mem=64G", "--time=5-00:00:00"],
                f",FACTORCON_SUBJECT_INDEX={index}",
            )
            jobs[f"mri-{index}"] = previous
        atomic_write_json(
            operations / "campaign.json",
            {
                "jobs": jobs,
                "failed_replicates": failed,
                "source": str(repair),
                "created_utc": utc_now(),
                "scientific_changes": False,
                "raw_and_derivatives_preserved": True,
                "mri_concurrency": 1,
            },
        )
        print(json.dumps(jobs), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
