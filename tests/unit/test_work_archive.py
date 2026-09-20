"""Small byte-exact archive fixtures, never participant data."""

import io
import json
import tarfile

import pytest

from factorcon.util import hash_file
from factorcon.work_archive import pack, retire, verify_archive, work_target


def fixture(tmp_path):
    root = tmp_path.resolve() / "study"
    work = root / "analysis/masked-neural/PREPROCESS/123-0/work"
    (work / "nested/empty").mkdir(parents=True)
    (work / "nested/data.bin").write_bytes(b"fixture data" * 100)
    (work / "zero").write_bytes(b"")
    dest = root / "archives/mri-work/123-0-test"
    return root, work, dest


def test_pack_verify_retire_and_idempotent_restart(tmp_path):
    root, work, dest = fixture(tmp_path)
    assert pack(root, work, dest, dry_run=True)["members"] == 5
    assert not dest.exists()
    result = pack(root, work, dest)
    assert result["status"] == "VERIFIED" and work.exists()
    manifest = json.loads((dest / "manifest.json").read_text())
    assert verify_archive(dest / "work.tar", manifest["members"]) == hash_file(dest / "work.tar")
    assert retire(root, work, dest)["status"] == "RETIRED"
    assert not work.exists() and retire(root, work, dest)["source_removed"]
    # Restoration is possible without recreating or guessing original bytes.
    with tarfile.open(dest / "work.tar") as tar:
        assert tar.extractfile("work/nested/data.bin").read() == b"fixture data" * 100


def test_no_raw_derivative_or_broad_path_targets(tmp_path):
    root, work, _dest = fixture(tmp_path)
    for wrong in [
        root,
        root / "data/raw",
        work.parent / "derivatives",
        work.parent.parent / "work",
    ]:
        with pytest.raises(ValueError):
            work_target(root, wrong)
    with pytest.raises(ValueError):
        pack(root, work, root / "outside")


def test_corrupt_archive_never_removes_source(tmp_path):
    root, work, dest = fixture(tmp_path)
    pack(root, work, dest)
    with (dest / "work.tar").open("r+b") as f:
        data = f.read()
        offset = data.index(b"fixture data")
        f.seek(offset)
        f.write(b"X")
    with pytest.raises(ValueError, match="checksum"):
        retire(root, work, dest)
    assert (work / "nested/data.bin").exists()


def test_source_mutation_never_removes_source(tmp_path):
    root, work, dest = fixture(tmp_path)
    pack(root, work, dest)
    (work / "nested/data.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="source identity"):
        retire(root, work, dest)
    assert (work / "zero").exists()


def test_resume_interrupted_retirement(tmp_path):
    root, work, dest = fixture(tmp_path)
    pack(root, work, dest)
    marker = json.loads((dest / "status.json").read_text())
    marker["status"] = "RETIRING"
    (dest / "status.json").write_text(json.dumps(marker))
    (work / "zero").unlink()
    assert retire(root, work, dest)["status"] == "RETIRED"


def test_archive_duplicate_member_rejected(tmp_path):
    root, work, dest = fixture(tmp_path)
    pack(root, work, dest)
    rows = json.loads((dest / "manifest.json").read_text())["members"]
    with tarfile.open(dest / "work.tar", "a") as tar:
        info = tarfile.TarInfo("work/zero")
        info.mode = rows["work/zero"]["mode"]
        tar.addfile(info, io.BytesIO())
    with pytest.raises(ValueError, match="duplicate"):
        verify_archive(dest / "work.tar", rows)


def test_pack_failure_preserves_source_and_marker(tmp_path, monkeypatch):
    import factorcon.work_archive as module

    root, work, dest = fixture(tmp_path)

    def fail(*_):
        raise ValueError("synthetic verify failure")

    monkeypatch.setattr(module, "verify_archive", fail)
    with pytest.raises(ValueError, match="synthetic"):
        pack(root, work, dest)
    assert json.loads((dest / "status.json").read_text())["status"] == "FAILED"
    assert (work / "nested/data.bin").exists()
    with pytest.raises(FileExistsError):
        pack(root, work, dest)
    assert pack(root, work, root / "archives/mri-work/dry", dry_run=True)["dry_run"]
