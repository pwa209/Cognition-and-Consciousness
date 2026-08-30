#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
repo_root="$(factorcon_repo_root)"
config_path="${1:-$repo_root/conf/base.yaml}"
expected_host="$(factorcon_config_value "$config_path" server expected_hostname)"
expected_user="$(factorcon_config_value "$config_path" server expected_user)"
canonical_root="${FACTORCON_CANONICAL_ROOT:-$(factorcon_config_value "$config_path" server canonical_root)}"
fast_root="${FACTORCON_FAST_ROOT:-$(factorcon_config_value "$config_path" server fast_root)}"
restart_root="${FACTORCON_RESTART_ROOT:-$(factorcon_config_value "$config_path" server restart_root)}"

factorcon_verify_identity "$expected_host" "$expected_user"
factorcon_require_root "$canonical_root" /private_nas/wangpeng
factorcon_require_root "$fast_root" /data1/wangpeng
factorcon_require_root "$restart_root" /data2/wangpeng

for command in python3 git tmux curl wget rsync sha256sum flock; do
  command -v "$command" >/dev/null 2>&1 || factorcon_die "required command missing: $command"
done

for root in "$canonical_root" "$fast_root" "$restart_root"; do
  [[ -d "$root" ]] || factorcon_die "configured root does not exist: $root"
  [[ -w "$root" ]] || factorcon_die "configured root is not writable: $root"
done

mkdir -p -- "$canonical_root/reports/generated/preflight"
report="$canonical_root/reports/generated/preflight/$(date -u +%Y%m%dT%H%M%SZ).json"
python3 - "$report" "$canonical_root" "$fast_root" "$restart_root" <<'PY'
import json, os, pathlib, platform, shutil, socket, subprocess, sys

def disk(path):
    usage = shutil.disk_usage(path)
    return {"total": usage.total, "used": usage.used, "free": usage.free}

def command(args):
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    return {"exit_code": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}

report = {
    "hostname": socket.gethostname(),
    "user": os.environ.get("USER"),
    "python": sys.version,
    "platform": platform.platform(),
    "cpu_count": os.cpu_count(),
    "roots": {path: disk(path) for path in sys.argv[2:]},
    "gpu": command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
    "slurm": shutil.which("sbatch"),
    "tmux": shutil.which("tmux"),
}
path = pathlib.Path(sys.argv[1])
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(temporary, path)
print(json.dumps(report, indent=2, sort_keys=True))
PY

PYTHONPATH="$repo_root/src" python3 -m factorcon config validate --config "$config_path"

