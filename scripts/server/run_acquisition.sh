#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
release_root="$(factorcon_repo_root)"
config_path="$release_root/conf/base.yaml"
action="${1:-}"
requested_family="${2:-}"
[[ "$action" == "resolve" || "$action" == "download" ]] || \
  factorcon_die "usage: run_acquisition.sh {resolve|download} [family]"

roots_status="$(factorcon_config_value "$config_path" server roots_status)"
[[ "$roots_status" == "owner_confirmed" ]] || \
  factorcon_die "conf/server_h100.yaml does not record owner_confirmed roots"
expected_host="$(factorcon_config_value "$config_path" server expected_hostname)"
expected_user="$(factorcon_config_value "$config_path" server expected_user)"
canonical_root="$(factorcon_config_value "$config_path" server canonical_root)"
fast_root="$(factorcon_config_value "$config_path" server fast_root)"
restart_root="$(factorcon_config_value "$config_path" server restart_root)"
factorcon_verify_identity "$expected_host" "$expected_user"
factorcon_require_root "$canonical_root" /private_nas/wangpeng
factorcon_require_root "$fast_root" /data1/wangpeng
factorcon_require_root "$restart_root" /data2/wangpeng

umask 027
mkdir -p -- \
  "$canonical_root/data/raw" \
  "$canonical_root/manifests/generated" \
  "$canonical_root/logs/acquisition" \
  "$canonical_root/run_state/P01" \
  "$canonical_root/run_state/P02" \
  "$canonical_root/provenance" \
  "$canonical_root/quarantine" \
  "$fast_root/tmp" \
  "$restart_root/checkpoints"

export PYTHONPATH="$release_root/src"
export PYTHONDONTWRITEBYTECODE=1
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$action${requested_family:+-$requested_family}"
state_phase="P01"
[[ "$action" == "resolve" ]] || state_phase="P02"
state_dir="$canonical_root/run_state/$state_phase"
log_path="$canonical_root/logs/acquisition/$run_id.log"
running="$state_dir/$run_id.RUNNING.json"
success="$state_dir/$run_id.SUCCESS.json"
failed="$state_dir/$run_id.FAILED.json"
lock_name="acquisition-$action${requested_family:+-$requested_family}"
lock_path="$state_dir/$lock_name.lock"
exec 9>"$lock_path"
flock -n 9 || factorcon_die "acquisition run already holds lock $lock_path"
exec > >(tee -a "$log_path") 2>&1

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
commit="$(git -C "$release_root" rev-parse HEAD 2>/dev/null || true)"
python3 - "$running" "$action" "$requested_family" "$started" "$commit" <<'PY'
import json, os, pathlib, sys
path = pathlib.Path(sys.argv[1])
record = {
    "action": sys.argv[2],
    "family": sys.argv[3] or None,
    "started_utc": sys.argv[4],
    "commit": sys.argv[5] or None,
    "pid": os.getpid(),
    "status": "running",
}
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY

finish() {
  local exit_code="$?"
  trap - EXIT
  local destination="$success"
  local status="success"
  if [[ "$exit_code" -ne 0 ]]; then
    destination="$failed"
    status="failed"
  fi
  python3 - "$destination" "$action" "$requested_family" "$started" "$status" "$exit_code" <<'PY'
import json, os, pathlib, sys
from datetime import datetime, timezone
path = pathlib.Path(sys.argv[1])
record = {
    "action": sys.argv[2],
    "family": sys.argv[3] or None,
    "started_utc": sys.argv[4],
    "ended_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "status": sys.argv[5],
    "exit_code": int(sys.argv[6]),
}
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY
  rm -f -- "$running"
  exit "$exit_code"
}
trap finish EXIT

families=(
  multisite_working_memory
  cogitate
  propofol_volition_fmri
  propofol_awakening_eeg
  masked_content_fmri
  bmvp
  dream
)
if [[ -n "$requested_family" ]]; then
  families=("$requested_family")
fi

overall=0
for family in "${families[@]}"; do
  if [[ "$action" == "download" ]]; then
    if ! python3 -m factorcon.acquisition_cli capacity \
      --config "$config_path" \
      --canonical-root "$canonical_root" \
      --family "$family"; then
      overall=3
      continue
    fi
  fi
  command=(
    python3 -m factorcon.acquisition_cli "$action"
    --config "$config_path"
    --canonical-root "$canonical_root"
    --family "$family"
  )
  if [[ "$action" == "download" ]]; then
    command+=(--no-resolve)
  fi
  if ! "${command[@]}"; then
    overall=3
  fi
done
exit "$overall"
