"""User-operated Alliance SSH authentication; credentials never enter the queue/log.

Adapted from AI Collective Intelligence's independently flushed command-stream bridge.
The native console belongs to SSH for password and Duo/OTP input. Only remote stdout
is logged. This is a temporary connection, not a remote study scheduler.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import re
import subprocess
import time
from pathlib import Path


def main() -> int:
    """Run a bounded command bridge; queue scripts are trusted local operations only."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-directory", type=Path, required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--lifetime-seconds", type=int, default=7200)
    args = parser.parse_args()
    if not args.known_hosts.is_file() or not 60 <= args.lifetime_seconds <= 7200:
        parser.error("existing known-hosts file and lifetime 60..7200 seconds required")
    root = args.state_directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in ("queue", "sent"):
        (root / name).mkdir(exist_ok=True)
    if (root / "stop").exists():
        parser.error("state directory contains stop marker; use a new session directory")
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    log_path = root / f"session-{stamp}.log"
    print("Cognition and Consciousness: enter your Alliance password and Duo/OTP here.", flush=True)
    print("Credentials go directly to SSH and are not saved. Keep this window open.", flush=True)
    print(f"Remote stdout only: {log_path}", flush=True)
    command = [
        "ssh",
        "-T",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={args.known_hosts}",
        "-o",
        "ConnectTimeout=30",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "PreferredAuthentications=keyboard-interactive,password",
        "-o",
        "KbdInteractiveAuthentication=yes",
        "-o",
        "PasswordAuthentication=yes",
        "-o",
        "PubkeyAuthentication=no",
        "-o",
        "HostbasedAuthentication=no",
        "pwa209@rorqual.alliancecan.ca",
        "bash -l",
    ]
    with log_path.open("xb", buffering=0) as log:
        # stderr/console remain inherited for authentication; never tee this stream.
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log)
        (root / "bridge.json").write_text(
            json.dumps(
                {
                    "ssh_pid": process.pid,
                    "started_utc": stamp,
                    "log": str(log_path),
                    "remote": "pwa209@rorqual.alliancecan.ca",
                }
            )
        )

        def send(line: str) -> None:
            assert process.stdin is not None
            process.stdin.write((line + "\n").encode())
            process.stdin.flush()

        try:
            send("printf '\\nFACTORCON_ALLIANCE_CONNECTED\\n'; hostname; id -un")
            deadline = time.monotonic() + args.lifetime_seconds
            while (
                process.poll() is None
                and time.monotonic() < deadline
                and not (root / "stop").exists()
            ):
                for path in sorted((root / "queue").glob("*.sh")):
                    identifier = path.stem
                    if not re.fullmatch(r"[A-Za-z0-9_-]+", identifier) or path.is_symlink():
                        raise ValueError("invalid queue identity or symlink")
                    destination = root / "sent" / path.name
                    if destination.exists():
                        raise ValueError(
                            "sent identity already exists; inspect completion before retry"
                        )
                    payload = base64.b64encode(path.read_bytes().replace(b"\r\n", b"\n")).decode()
                    path.rename(destination)
                    send(
                        f"printf %s {payload} | base64 -d | bash -l; "
                        f"printf '\\nCOMMAND_DONE_{identifier}=%s\\n' $?"
                    )
                time.sleep(2)
            if process.poll() is None:
                send("exit")
            assert process.stdin is not None
            process.stdin.close()
            code = process.wait()
        except (BrokenPipeError, OSError) as exc:
            print(
                f"Connection interrupted: {type(exc).__name__}. Reconcile remote state.", flush=True
            )
            return 1
    (root / f"exit-{stamp}.json").write_text(json.dumps({"exit_code": code}))
    print(f"SSH ended ({code}). Sent scripts alone do not prove remote execution.", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
