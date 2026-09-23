"""Synthetic warning compatibility and dispatch tests; no participant data."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2]


def module(name, monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE / "scripts/alliance"))
    spec = importlib.util.spec_from_file_location(name, SOURCE / "scripts/alliance" / f"{name}.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_exact_patch_preserves_warning_body_and_accepts_new_keyword(monkeypatch):
    m = module("fmriprep_warning_compat", monkeypatch)
    original = m.ORIGINAL + b"\n    return (message, category, stacklevel, source)\n"
    digest = hashlib.sha256(original).hexdigest()
    patched = m.patched_bytes(original, digest)
    assert patched.replace(m.REPLACEMENT, m.ORIGINAL) == original
    scope = {}
    exec(compile(patched, "synthetic-fixture", "exec"), scope)
    assert scope["_warn"]("visible", UserWarning, skip_file_prefixes=("matplotlib",)) == (
        "visible",
        UserWarning,
        1,
        None,
    )
    with pytest.raises(ValueError, match="checksum"):
        m.patched_bytes(original + b"\n", digest)
    doubled = original * 2
    with pytest.raises(ValueError, match="exactly one"):
        m.patched_bytes(doubled, hashlib.sha256(doubled).hexdigest())


def test_overlay_idempotence_and_container_boundary(tmp_path, monkeypatch):
    m = module("fmriprep_warning_compat", monkeypatch)
    original = m.ORIGINAL + b"\n    pass\n"
    image = tmp_path / "read-only-image"
    file = image / "site/_warnings.py"
    file.parent.mkdir(parents=True)
    file.write_bytes(original)
    repair = tmp_path / "study/releases/abc/source"
    spec = {
        "image": str(image),
        "container_path": "/site/_warnings.py",
        "original_sha256": hashlib.sha256(original).hexdigest(),
    }
    patch = m.prepare_patch(tmp_path / "study", repair, spec)
    assert m.prepare_patch(tmp_path / "study", repair, spec) == patch
    assert file.read_bytes() == original
    provenance = patch.with_name("provenance.json").read_bytes()
    assert m.prepare_patch(tmp_path / "study", repair, spec) == patch
    assert patch.with_name("provenance.json").read_bytes() == provenance
    prefix = ["apptainer", "exec", "--cleanenv", str(image)]
    assert m.bind_patch(prefix, patch, spec) == [
        *prefix[:-1],
        "--bind",
        f"{patch}:/site/_warnings.py:ro",
        prefix[-1],
    ]
    with pytest.raises(ValueError, match="unexpected"):
        m.bind_patch(["apptainer", "exec", "other"], patch, spec)
    patch.chmod(0o600)
    patch.write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs"):
        m.prepare_patch(tmp_path / "study", repair, spec)


def test_only_unfinished_targets_and_original_settings(tmp_path, monkeypatch):
    m = module("submit_mri_warning_recovery", monkeypatch)
    plan = json.loads((SOURCE / "conf/mri_warning_recovery_plan.yaml").read_text())
    monkeypatch.setattr(m, "terminal", lambda job: ["FAILED" if job == "21450700" else "CANCELLED"])
    m.check_targets(tmp_path, plan)
    for env in [plan["mri_environment"], plan["qualification_environment"]]:
        p = tmp_path / "environments" / env / "bin/python"
        p.parent.mkdir(parents=True)
        p.touch()
    repair = tmp_path / "releases/abc/source"
    label, cmd = m.command_for(tmp_path, repair, plan, "qualify")
    assert label == "qualification" and not any(x.startswith("--dependency") for x in cmd)
    label, cmd = m.command_for(tmp_path, repair, plan, "mri", 3, "123")
    assert label == "mri-3" and "--dependency=afterok:123" in cmd
    assert "--mem=64G" in cmd and "--kill-on-invalid-dep=yes" in cmd
    assert plan["mri_source"] in next(x for x in cmd if x.startswith("--export"))
    with pytest.raises(ValueError, match="eligible"):
        m.command_for(tmp_path, repair, plan, "mri", 0, "123")
    p = tmp_path / "analysis/masked-neural/PREPROCESS/999-3/status.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"status":"SUCCESS"}')
    with pytest.raises(ValueError, match="completed"):
        m.check_targets(tmp_path, plan)


def test_warning_recovery_lifecycle_markers(tmp_path, monkeypatch):
    m = module("inode_recovery", monkeypatch)
    plan = json.loads((SOURCE / "conf/mri_warning_recovery_plan.yaml").read_text())
    repair = tmp_path / "releases/abc/source"
    path = repair / "conf/mri_warning_recovery_plan.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(m, "__file__", str(repair / "scripts/alliance/inode_recovery.py"))
    monkeypatch.setattr(m, "validate_fresh_root", lambda _: tmp_path)
    monkeypatch.setattr(m, "verify_source", lambda *a: None)
    monkeypatch.setenv("SLURM_JOB_ID", "456")
    monkeypatch.delenv("SLURM_ARRAY_TASK_ID", raising=False)
    monkeypatch.setattr(sys, "argv", ["recovery", "--mode", "mri", "--plan", path.name])
    operations = tmp_path / "operations/inode-recovery/abc"
    operations.mkdir(parents=True)
    (operations / "qualification.json").write_text('{"job_id":"123"}')
    state = operations / "qualify-123-single/status.json"
    state.parent.mkdir()
    from factorcon.util import hash_file

    state.write_text(
        json.dumps(
            {
                "status": "SUCCESS",
                "repair_source": str(repair),
                "plan_sha256": hash_file(path),
                "warning_smoke_passed": False,
            }
        )
    )
    with pytest.raises(ValueError, match="regression"):
        m.main()
    failed = operations / "mri-456-single/status.json"
    assert json.loads(failed.read_text())["status"] == "FAILED"
    assert failed.with_name("provenance.json").exists()
    value = json.loads(state.read_text())
    value["warning_smoke_passed"] = True
    state.write_text(json.dumps(value))
    monkeypatch.setattr(m, "retry_legacy", lambda *a: None)
    monkeypatch.setenv("SLURM_JOB_ID", "457")
    assert m.main() == 0
    assert (
        json.loads((operations / "mri-457-single/status.json").read_text())["status"] == "SUCCESS"
    )
    assert json.loads(failed.read_text())["status"] == "FAILED"
    with pytest.raises(FileExistsError):
        m.main()


def test_explicit_qualification_job_avoids_wrong_receipt_directory(tmp_path, monkeypatch):
    m = module("inode_recovery", monkeypatch)
    operations = tmp_path / "operations/inode-recovery/repair"
    monkeypatch.setenv("FACTORCON_QUALIFICATION_JOB", "21571206")
    assert m.resolve_qualification_job(operations) == "21571206"
    monkeypatch.setenv("FACTORCON_QUALIFICATION_JOB", "not-a-job")
    with pytest.raises(ValueError, match="numeric"):
        m.resolve_qualification_job(operations)
