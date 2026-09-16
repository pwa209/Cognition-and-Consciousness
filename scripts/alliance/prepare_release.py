"""Build a reviewed Git-only source transfer for the already-authenticated SSH queue.

No participant data, working-tree caches, credentials or unrelated project files are
read. The receiver refuses an existing target and verifies every source file.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


def build_transfer(commit: str, root: str, repository: Path, *, existing_run: bool = False) -> str:
    """Return a fresh-only shell transfer of committed source, with SHA-256 verification.

    ``root`` is a single fresh-* run in personal scratch. Source files are byte-for-byte
    Git blobs; generated scientific outputs and secrets are not input to this function.
    """
    from factorcon.alliance import validate_fresh_root

    validate_fresh_root(root, check_host=False)
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=repository, text=True
    ).strip()
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar.gz", revision], cwd=repository
    )
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise ValueError("unsafe source archive path/link")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("nonregular source archive member")
            handle = tar.extractfile(member)
            assert handle is not None
            files[member.name] = hashlib.sha256(handle.read()).hexdigest()
    payload = {
        "root": root,
        "commit": revision,
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "files": files,
        "archive_base64": base64.b64encode(archive).decode(),
        "existing_run": existing_run,
    }
    # The embedded receiver uses only the verified cluster Python standard library.
    return """#!/usr/bin/env bash
set -euo pipefail
module load StdEnv/2023 python/3.12.4
python - <<'FACTORCON_RECEIVE'
import base64,datetime,hashlib,io,json,os,pathlib,pwd,socket,tarfile
payload=json.loads(PAYLOAD_LITERAL)
assert pwd.getpwuid(os.getuid()).pw_name=='pwa209'
assert socket.gethostname().startswith('rorqual')
personal=pathlib.Path('/scratch/pwa209')
assert personal.is_dir() and personal.stat().st_uid==os.getuid()
root=pathlib.Path(payload['root'])
assert root.parent==personal/'cognition-and-consciousness' and root.name.startswith('fresh-')
assert root.resolve()==root
if payload['existing_run']:
    initial=json.loads((root/'FRESH_RUN.json').read_text())
    assert initial['download_root']==str(root) and initial['reuse_prior_data'] is False
else:
    assert not root.exists(), 'Fresh target exists: reconcile; never overwrite or import prior data'
archive=base64.b64decode(payload['archive_base64'],validate=True)
assert hashlib.sha256(archive).hexdigest()==payload['archive_sha256']
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    seen=set()
    for member in tar.getmembers():
        path=pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isdir() or member.isfile()
        if member.isfile():
            assert member.name not in seen
            seen.add(member.name)
            digest=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
            assert digest==payload['files'][member.name]
    assert seen==set(payload['files'])
    root.parent.mkdir(exist_ok=True)
    if not payload['existing_run']:
        root.mkdir(mode=0o700)
    release=root/'releases'/payload['commit']/'source'
    assert not release.parent.exists(), 'Version already exists: reconcile, never overwrite'
    release.mkdir(parents=True)
    tar.extractall(release,filter='data')
for relative,digest in payload['files'].items():
    assert hashlib.sha256((release/relative).read_bytes()).hexdigest()==digest
    (release/relative).chmod(0o444)
(release.parent/'source.tar.gz').write_bytes(archive)
record={k:v for k,v in payload.items() if k!='archive_base64'}
record.update(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              download_root=str(root),reuse_prior_data=False,release=str(release),
              shared_storage_downloads=False,analysis_execution_authorized=True)
target=release.parent/'RELEASE.json' if payload['existing_run'] else root/'FRESH_RUN.json'
tmp=target.with_suffix('.json.tmp')
tmp.write_text(json.dumps(record,indent=2)); tmp.replace(target)
print(json.dumps({'status':'SOURCE_INSTALLED','root':str(root),'release':str(release),
                  'files_verified':len(payload['files']),'archive_sha256':payload['archive_sha256']}))
FACTORCON_RECEIVE
""".replace("PAYLOAD_LITERAL", repr(json.dumps(payload)))


def main() -> int:
    """Write one local queue artifact; transmitting/executing it is a separate action."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--queue-file", type=Path, required=True)
    parser.add_argument("--existing-run", action="store_true")
    args = parser.parse_args()
    script = build_transfer(
        args.commit, args.root, Path(__file__).resolve().parents[2], existing_run=args.existing_run
    )
    args.queue_file.parent.mkdir(parents=True, exist_ok=True)
    if args.queue_file.exists():
        raise FileExistsError("queue identity already exists; reconcile before retry")
    pending = args.queue_file.with_suffix(".pending")
    with pending.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(script)
    pending.rename(args.queue_file)
    print(json.dumps({"queue_file": str(args.queue_file), "bytes": args.queue_file.stat().st_size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
