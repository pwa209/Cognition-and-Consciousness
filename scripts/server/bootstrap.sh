#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
repo_root="$(factorcon_repo_root)"
config_path="$repo_root/conf/base.yaml"

[[ "${1:-}" == "--confirm-roots" ]] || factorcon_die "explicit --confirm-roots is required"
deployment_scope="$(factorcon_config_value "$config_path" server deployment_scope)"
[[ "$deployment_scope" == "full" ]] || \
  factorcon_die "full bootstrap is disabled while deployment_scope=$deployment_scope"
roots_status="$(factorcon_config_value "$config_path" server roots_status)"
[[ "$roots_status" == "owner_confirmed" ]] || factorcon_die "conf/server_h100.yaml does not record owner_confirmed roots"

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
  "$canonical_root/source/releases" \
  "$canonical_root/data/raw" \
  "$canonical_root/manifests/generated" \
  "$canonical_root/logs" \
  "$canonical_root/run_state" \
  "$canonical_root/provenance" \
  "$canonical_root/quarantine" \
  "$canonical_root/reports/generated" \
  "$fast_root/stage" \
  "$fast_root/tmp" \
  "$restart_root/derivatives" \
  "$restart_root/checkpoints" \
  "$restart_root/environments"

"$repo_root/scripts/server/preflight.sh" "$config_path"
