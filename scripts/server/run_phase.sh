#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
repo_root="$(factorcon_repo_root)"
config_path="$repo_root/conf/base.yaml"
phase="${1:-}"
family="${2:-}"
[[ "$phase" =~ ^P(0[0-9]|10)$ ]] || factorcon_die "phase must be P00 through P10"

expected_host="$(factorcon_config_value "$config_path" server expected_hostname)"
expected_user="$(factorcon_config_value "$config_path" server expected_user)"
canonical_root="${FACTORCON_CANONICAL_ROOT:-$(factorcon_config_value "$config_path" server canonical_root)}"
fast_root="${FACTORCON_FAST_ROOT:-$(factorcon_config_value "$config_path" server fast_root)}"
restart_root="${FACTORCON_RESTART_ROOT:-$(factorcon_config_value "$config_path" server restart_root)}"
factorcon_verify_identity "$expected_host" "$expected_user"
factorcon_require_root "$canonical_root" /private_nas/wangpeng
factorcon_require_root "$fast_root" /data1/wangpeng
factorcon_require_root "$restart_root" /data2/wangpeng

run_label="$phase${family:+-$family}"
state_dir="$canonical_root/run_state/$phase"
log_dir="$canonical_root/logs/$phase"
mkdir -p -- "$state_dir" "$log_dir"
lock_path="$state_dir/$run_label.lock"
exec 9>"$lock_path"
flock -n 9 || factorcon_die "phase already running: $run_label"

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
running="$state_dir/$run_label.RUNNING.json"
success="$state_dir/$run_label.SUCCESS.json"
failed="$state_dir/$run_label.FAILED.json"
python3 - "$running" "$phase" "$family" "$started" "$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)" <<'PY'
import json, os, pathlib, sys
path = pathlib.Path(sys.argv[1])
record = {"phase": sys.argv[2], "family": sys.argv[3] or None, "started_utc": sys.argv[4], "commit": sys.argv[5] or None, "pid": os.getpid(), "status": "running"}
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY

finish() {
  local exit_code="$?"
  trap - EXIT
  local status_path="$success"
  local status="success"
  if [[ "$exit_code" -ne 0 ]]; then
    status_path="$failed"
    status="failed"
  fi
  python3 - "$status_path" "$phase" "$family" "$started" "$status" "$exit_code" <<'PY'
import json, os, pathlib, sys
from datetime import datetime, timezone
path = pathlib.Path(sys.argv[1])
record = {"phase": sys.argv[2], "family": sys.argv[3] or None, "started_utc": sys.argv[4], "ended_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "status": sys.argv[5], "exit_code": int(sys.argv[6])}
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY
  rm -f -- "$running"
  exit "$exit_code"
}
trap finish EXIT

export PYTHONPATH="$repo_root/src"
export FACTORCON_CANONICAL_ROOT="$canonical_root"
export FACTORCON_FAST_ROOT="$fast_root"
export FACTORCON_RESTART_ROOT="$restart_root"
export PYTHONDONTWRITEBYTECODE=1
source_commit="$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)"
phase_python="python3"
if [[ "$source_commit" =~ ^[0-9a-f]{40}$ && -x "$restart_root/environments/$source_commit/bin/python" ]]; then
  phase_python="$restart_root/environments/$source_commit/bin/python"
fi

case "$phase" in
  P00)
    "$repo_root/scripts/server/preflight.sh" "$config_path"
    "$phase_python" -m pytest -q "$repo_root/tests"
    ;;
  P01)
    command=("$phase_python" -m factorcon manifest resolve --config "$config_path" --out "$canonical_root")
    [[ -z "$family" ]] || command+=(--family "$family")
    "${command[@]}"
    ;;
  P02)
    command=("$phase_python" -m factorcon acquire --config "$config_path" --canonical-root "$canonical_root" --eligible-only)
    [[ -z "$family" ]] || command+=(--family "$family")
    "${command[@]}"
    ;;
  P03) target="validate_data" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 16 "$target" ;;
  P04) target="harmonize" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 32 "$target" ;;
  P05) target="pilot" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 32 "$target" ;;
  P06) target="features" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 128 --resources high_io=2 "$target" ;;
  P07) target="models" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 192 "$target" ;;
  P08) target="synthesis" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 128 "$target" ;;
  P09) target="robustness" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 128 "$target" ;;
  P10) target="reproduce" ; "$phase_python" -m snakemake --snakefile "$repo_root/workflow/Snakefile" --configfile "$config_path" --cores 32 "$target" ;;
esac
