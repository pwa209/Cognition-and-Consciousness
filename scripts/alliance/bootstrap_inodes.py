"""Small, in-memory verified archive to recover initial inode headroom at hard quota."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
from pathlib import Path

from factorcon.alliance import validate_fresh_root


def main(previous_empty_files: dict | None = None) -> None:
    """Archive only inactive pip cache and tiny test fixtures; record removed empty work files.

    No raw data, derivatives, licence, environments, scientific results or logs are
    removed. The in-memory tar is checked before persistence and read back after
    fsync before originals are unlinked. Empty failed-work files are reconstructable
    from the embedded exact-path/mode/time manifest. All paths are study-owned.
    """
    root = validate_fresh_root(Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916"))
    os.umask(0o077)
    q = subprocess.run(
        ["squeue", "-h", "-j", "21417200", "-o", "%i|%T"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if q.stdout.strip():
        raise ValueError("old array not quiescent")
    if q.returncode != 0:
        accounting = subprocess.run(
            ["sacct", "-n", "-X", "-P", "-j", "21417200", "--format=State"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        states = [s.split()[0].split("|")[0] for s in accounting.stdout.splitlines() if s.strip()]
        if not states or any(
            s not in {"CANCELLED", "FAILED", "COMPLETED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"}
            for s in states
        ):
            raise ValueError("cannot verify array quiescence")
    archive = root / "operations/inode-bootstrap-20260920.tar"
    if archive.exists():
        raise FileExistsError("bootstrap archive exists; reconcile, never repeat")
    candidates = [root / "cache/pip"]
    for job in sorted((root / "qualification").iterdir()):
        marker = job / "status.json"
        if (
            job.name.isdigit()
            and marker.is_file()
            and json.loads(marker.read_text()).get("status") in {"SUCCESS", "FAILED"}
        ):
            candidates.extend(p for p in [job / "pytest-temp", job / "pytest-cache"] if p.is_dir())
    rows = {}
    for base in candidates:
        if base.resolve() != base:
            raise ValueError("redirected cache/fixture root")
        # Test fixtures can deliberately contain unsafe/dangling links. Leave the
        # entire linked fixture tree untouched, rather than following those links.
        if any(
            (Path(folder) / name).is_symlink()
            for folder, dirs, files in os.walk(base, followlinks=False)
            for name in dirs + files
        ):
            print("BOOTSTRAP_SKIP_LINKED_FIXTURES", str(base), flush=True)
            continue
        for folder, dirs, files in os.walk(base, followlinks=False):
            for path in [Path(folder), *(Path(folder) / n for n in sorted(files))]:
                s = path.lstat()
                if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
                    raise ValueError("unsupported fixture member")
                rows[path.relative_to(root).as_posix()] = {
                    "inode": s.st_ino,
                    "size": s.st_size,
                    "mode": stat.S_IMODE(s.st_mode),
                    "mtime_ns": s.st_mtime_ns,
                    "ctime_ns": s.st_ctime_ns,
                    "directory": stat.S_ISDIR(s.st_mode),
                }
            if any((Path(folder) / n).is_symlink() for n in dirs):
                raise ValueError("fixture link")
    if sum(v["size"] for v in rows.values() if not v["directory"]) > 100_000_000:
        raise ValueError("bootstrap payload exceeds 100 MB memory budget")
    zeros = dict(previous_empty_files or {})
    for attempt in ["21417200-1", "21417200-2"]:
        base = root / "analysis/masked-neural/PREPROCESS" / attempt / "work"
        if base.resolve() != base:
            raise ValueError("redirected work root")
        for folder, _dirs, files in os.walk(base, followlinks=False):
            for name in files:
                p = Path(folder) / name
                s = p.lstat()
                if stat.S_ISREG(s.st_mode) and s.st_size == 0:
                    zeros[p.relative_to(root).as_posix()] = {
                        "inode": s.st_ino,
                        "mode": stat.S_IMODE(s.st_mode),
                        "mtime_ns": s.st_mtime_ns,
                        "ctime_ns": s.st_ctime_ns,
                    }
    if not zeros:
        raise ValueError("no safely reconstructable empty files for bootstrap")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, row in sorted(rows.items()):
            p = root / name
            if row["directory"]:
                tar.add(p, arcname=name, recursive=False)
            else:
                value = p.read_bytes()
                row["sha256"] = hashlib.sha256(value).hexdigest()
                info = tar.gettarinfo(str(p), arcname=name)
                tar.addfile(info, io.BytesIO(value))
        value = json.dumps(
            {"schema_version": 1, "root": str(root), "members": rows, "empty_work_files": zeros},
            sort_keys=True,
        ).encode()
        info = tarfile.TarInfo("RECOVERY-MANIFEST.json")
        info.size = len(value)
        info.mode = 0o600
        tar.addfile(info, io.BytesIO(value))
    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as tar:
        for name, row in rows.items():
            if (
                not row["directory"]
                and hashlib.sha256(tar.extractfile(name).read()).hexdigest() != row["sha256"]
            ):
                raise ValueError("in-memory verification failed")
    # Exact zero-file reconstruction information is also emitted to the owner's
    # private local bridge receipt before unlinking, protecting a bootstrap crash.
    print("BOOTSTRAP_EMPTY_FILE_RECONSTRUCTION", json.dumps(zeros, sort_keys=True), flush=True)
    for name, row in zeros.items():
        p = root / name
        if previous_empty_files and name in previous_empty_files and not p.exists():
            continue
        s = p.lstat()
        if (
            not stat.S_ISREG(s.st_mode)
            or s.st_size != 0
            or s.st_ino != row["inode"]
            or s.st_ctime_ns != row["ctime_ns"]
        ):
            raise ValueError("empty work file changed")
        p.unlink()
    try:
        with archive.open("xb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        # Hard inode quota can deny even one archive inode. Use one existing,
        # regenerable pip-cache inode; its exact old bytes are in the tar AND
        # emitted first to the private bridge receipt. Never use research files.
        if exc.errno != 122 or archive.exists():
            raise
        carriers = [
            n
            for n, row in rows.items()
            if n.startswith("cache/pip/") and not row["directory"] and row["size"] <= 65536
        ]
        if not carriers:
            raise ValueError("no small cache-only carrier inode available") from exc
        carrier_name = min(carriers, key=lambda n: rows[n]["size"])
        carrier = root / carrier_name
        before = carrier.read_bytes()
        if hashlib.sha256(before).hexdigest() != rows[carrier_name]["sha256"]:
            raise ValueError("cache carrier changed") from exc
        print(
            "BOOTSTRAP_CARRIER_RECOVERY",
            json.dumps(
                {
                    "path": carrier_name,
                    "base64": base64.b64encode(before).decode(),
                    "metadata": rows[carrier_name],
                }
            ),
            flush=True,
        )
        with carrier.open("r+b") as f:
            f.write(payload)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())
        if hashlib.sha256(carrier.read_bytes()).hexdigest() != digest:
            raise ValueError("carrier archive mismatch; use private recovery receipt") from exc
        carrier.rename(archive)
        # The original cache bytes are now a verified tar member, not a loose file.
        rows.pop(carrier_name)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError("persisted archive mismatch")
    for name, row in rows.items():
        p = root / name
        s = p.lstat()
        if s.st_ino != row["inode"] or (
            not row["directory"] and (s.st_size != row["size"] or s.st_ctime_ns != row["ctime_ns"])
        ):
            raise ValueError("fixture/cache changed; archive retained, source retirement stopped")
    for name in sorted(rows, key=lambda n: (n.count("/"), n), reverse=True):
        p = root / name
        if rows[name]["directory"]:
            p.rmdir()
        else:
            p.unlink()
    print(
        "BOOTSTRAP_VERIFIED",
        json.dumps(
            {
                "archive": str(archive),
                "sha256": digest,
                "bytes": len(payload),
                "cache_fixture_members_retired": len(rows),
                "empty_work_files_recorded": len(zeros),
                "raw_and_derivatives_untouched": True,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
