"""Second inode bootstrap: preserve inactive synthetic fixture trees including link metadata."""

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


def main() -> None:
    """Combine only terminal qualification pytest-temp trees; never follow their test symlinks.

    Archive bytes stay in personal scratch using one existing fixture inode. Every
    file is checksum-verified before originals are retired; link targets are stored
    as metadata only and are not resolved, read or executed. Payload cap is 100 MB.
    This does not touch raw data, derivatives, scientific results or environment code.
    """
    root = validate_fresh_root(Path("/scratch/pwa209/cognition-and-consciousness/fresh-20260916"))
    os.umask(0o077)
    output = root / "operations/inode-fixtures-20260920.tar"
    if output.exists():
        raise FileExistsError("fixture archive exists; reconcile, never overwrite")
    active = subprocess.run(
        ["squeue", "-h", "-u", "pwa209", "-o", "%A"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.split()
    rows = {}
    for job in sorted((root / "qualification").iterdir()):
        marker = job / "status.json"
        base = job / "pytest-temp"
        if (
            not job.name.isdigit()
            or job.name in active
            or not marker.is_file()
            or not base.is_dir()
        ):
            continue
        if json.loads(marker.read_text()).get("status") not in {"SUCCESS", "FAILED"}:
            continue
        if base.resolve() != base:
            raise ValueError("redirected fixture root")
        paths = [base]
        for folder, dirs, files in os.walk(base, followlinks=False):
            paths.extend(Path(folder) / name for name in dirs + files)
        for path in paths:
            s = path.lstat()
            kind = (
                "link"
                if stat.S_ISLNK(s.st_mode)
                else "directory"
                if stat.S_ISDIR(s.st_mode)
                else "file"
                if stat.S_ISREG(s.st_mode)
                else "special"
            )
            if kind == "special":
                raise ValueError("special fixture object")
            rows[path.relative_to(root).as_posix()] = {
                "kind": kind,
                "size": s.st_size,
                "inode": s.st_ino,
                "mode": stat.S_IMODE(s.st_mode),
                "mtime_ns": s.st_mtime_ns,
                "ctime_ns": s.st_ctime_ns,
                "link": os.readlink(path) if kind == "link" else None,
            }
    if not rows or sum(v["size"] for v in rows.values() if v["kind"] == "file") > 100_000_000:
        raise ValueError("empty or oversized fixture census")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, row in sorted(rows.items()):
            p = root / name
            info = tar.gettarinfo(str(p), arcname=name)
            if row["kind"] == "file":
                value = p.read_bytes()
                row["sha256"] = hashlib.sha256(value).hexdigest()
                info.type, info.linkname, info.size = tarfile.REGTYPE, "", len(value)
                tar.addfile(info, io.BytesIO(value))
            else:
                tar.addfile(info)
        value = json.dumps(
            {"schema_version": 1, "root": str(root), "members": rows}, sort_keys=True
        ).encode()
        info = tarfile.TarInfo("RECOVERY-MANIFEST.json")
        info.size, info.mode = len(value), 0o600
        tar.addfile(info, io.BytesIO(value))
    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as tar:
        if set(tar.getnames()) != set(rows) | {"RECOVERY-MANIFEST.json"}:
            raise ValueError("fixture archive inventory mismatch")
        for name, row in rows.items():
            member = tar.getmember(name)
            if (
                row["kind"] == "file"
                and hashlib.sha256(tar.extractfile(member).read()).hexdigest() != row["sha256"]
            ):
                raise ValueError("fixture checksum mismatch")
            if row["kind"] == "link" and (not member.issym() or member.linkname != row["link"]):
                raise ValueError("fixture link metadata mismatch")
    for name, row in rows.items():
        s = (root / name).lstat()
        if s.st_ino != row["inode"] or s.st_ctime_ns != row["ctime_ns"]:
            raise ValueError("fixture changed before consolidation")
    carrier_name = min(
        (n for n, v in rows.items() if v["kind"] == "file" and v["size"] <= 65536),
        key=lambda n: rows[n]["size"],
    )
    carrier = root / carrier_name
    print(
        "FIXTURE_CARRIER_RECOVERY",
        json.dumps(
            {
                "path": carrier_name,
                "metadata": rows[carrier_name],
                "base64": base64.b64encode(carrier.read_bytes()).decode(),
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
        raise ValueError("persisted fixture archive mismatch")
    carrier.rename(output)
    # Each original file/link is rechecked immediately before removal. Directories
    # can have changed times from removing children, but never inode/type/ownership.
    for name in sorted(rows, key=lambda n: (n.count("/"), n), reverse=True):
        if name == carrier_name:
            continue
        p, row = root / name, rows[name]
        s = p.lstat()
        if s.st_ino != row["inode"] or (
            row["kind"] != "directory" and s.st_ctime_ns != row["ctime_ns"]
        ):
            raise ValueError("fixture changed during retirement")
        if row["kind"] == "directory":
            p.rmdir()
        else:
            p.unlink()
    print(
        "FIXTURE_BOOTSTRAP_VERIFIED",
        json.dumps(
            {
                "archive": str(output),
                "sha256": digest,
                "bytes": len(payload),
                "members_consolidated": len(rows),
                "symlinks_metadata_only": sum(v["kind"] == "link" for v in rows.values()),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
