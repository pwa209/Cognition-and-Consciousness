"""Storage and quota regression checks do not connect to a cluster or read secrets."""

from pathlib import Path

import pytest

from factorcon.alliance import parse_personal_quota, scratch_environment, validate_fresh_root
from factorcon.errors import CapacityError, IntegrityError


def test_rorqual_cpu_allocation_not_arbitrary_hostname():
    from factorcon.alliance import is_rorqual_execution

    assert is_rorqual_execution("rorqual1", {})
    assert is_rorqual_execution("rc32623", {"SLURM_CLUSTER_NAME": "rorqual", "SLURM_JOB_ID": "42"})
    assert not is_rorqual_execution("rc32623", {})
    assert not is_rorqual_execution(
        "rc32623", {"SLURM_CLUSTER_NAME": "other", "SLURM_JOB_ID": "42"}
    )
    assert not is_rorqual_execution("rorqual-attacker", {})


def test_personal_quota_not_shared_capacity():
    report = (
        "/scratch (user pwa209) 25KB/ 20TB 1 /1000K\n"
        "/project (project def-ptewarie) 98KB/1000GB 4 /500K"
    )
    quota = parse_personal_quota(report)
    assert quota.used_bytes == 26000
    assert quota.limit_bytes == 20_000_000_000_000
    assert quota.limit_files == 1_000_000
    with pytest.raises(CapacityError):
        parse_personal_quota("/scratch (group def-ptewarie) 1GB/100TB 4/1000K")


@pytest.mark.parametrize(
    "root",
    [
        "/project/def-ptewarie/pwa209/x",
        "/scratch/other/fresh-1",
        "/scratch/pwa209/artificial-anaesthesia/fresh-1",
        "/scratch/pwa209/cognition-and-consciousness/fresh-1/../../elsewhere",
    ],
)
def test_other_or_shared_storage_rejected(root):
    with pytest.raises(IntegrityError):
        validate_fresh_root(root, check_host=False)


def test_all_cache_destinations_are_personal():
    root = Path("/scratch/pwa209/cognition-and-consciousness/fresh-fixture")
    for value in scratch_environment(root).values():
        assert Path(value).is_relative_to(root)


def test_quota_guard_stops_before_byte_reserve(tmp_path, monkeypatch):
    import factorcon.alliance as module

    quota = parse_personal_quota("/scratch (user pwa209) 1GB/20TB 10 /1000K")
    monkeypatch.setattr(module, "read_personal_quota", lambda: quota)
    guard = module.ScratchQuotaGuard(tmp_path / "quota.json", reserve_bytes=500_000_000_000)
    guard(1024)
    with pytest.raises(CapacityError):
        guard(20_000_000_000_000)
    assert (tmp_path / "quota.json").is_file()


def test_quota_timeout_retries_before_writing(monkeypatch):
    import subprocess
    from types import SimpleNamespace

    import factorcon.alliance as module

    calls = []

    def run(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise subprocess.TimeoutExpired("diskusage_report", 45)
        return SimpleNamespace(returncode=0, stdout="/scratch (user pwa209) 3TB/20TB 300K/1000K")

    monkeypatch.setattr(module.subprocess, "run", run)
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    assert module.read_personal_quota().limit_bytes == 20_000_000_000_000
    assert len(calls) == 3 and sleeps == [5, 10]


def test_quota_service_exhaustion_fails_closed(monkeypatch, tmp_path):
    import subprocess

    import factorcon.alliance as module

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("diskusage_report", 45)

    monkeypatch.setattr(module.subprocess, "run", fail)
    monkeypatch.setattr(module.time, "sleep", lambda n: None)
    guard = module.ScratchQuotaGuard(tmp_path / "quota.json")
    with pytest.raises(CapacityError, match="after 3 attempts"):
        guard(1024)
    assert guard.bound == 0 and guard.quota is None
