#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
repo_root="$(factorcon_repo_root)"
config_path="$repo_root/conf/base.yaml"
commit="${1:-}"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || factorcon_die "usage: deploy_release.sh <40-character-git-commit>"
deployment_scope="$(factorcon_config_value "$config_path" server deployment_scope)"
[[ "$deployment_scope" == "full" ]] || \
  factorcon_die "full release deployment is disabled while deployment_scope=$deployment_scope"

expected_host="$(factorcon_config_value "$config_path" server expected_hostname)"
expected_user="$(factorcon_config_value "$config_path" server expected_user)"
canonical_root="$(factorcon_config_value "$config_path" server canonical_root)"
restart_root="$(factorcon_config_value "$config_path" server restart_root)"
factorcon_verify_identity "$expected_host" "$expected_user"
factorcon_require_root "$canonical_root" /private_nas/wangpeng
factorcon_require_root "$restart_root" /data2/wangpeng

destination="$canonical_root/source/releases/$commit"
if [[ -d "$destination/.git" ]]; then
  observed="$(git -C "$destination" rev-parse HEAD)"
  [[ "$observed" == "$commit" ]] || factorcon_die "existing release has unexpected commit $observed"
  printf '%s\n' "$destination"
  exit 0
fi
[[ ! -e "$destination" ]] || factorcon_die "release target exists but is not a verified Git checkout: $destination"

temporary="$restart_root/checkpoints/deploy-$commit"
[[ ! -e "$temporary" ]] || factorcon_die "temporary deploy path already exists: $temporary"
git clone --filter=blob:none --no-checkout https://github.com/pwa209/Cognition-and-Consciousness.git "$temporary"
git -C "$temporary" checkout --detach "$commit"
observed="$(git -C "$temporary" rev-parse HEAD)"
[[ "$observed" == "$commit" ]] || factorcon_die "checkout mismatch: $observed"
mkdir -p -- "$(dirname -- "$destination")"
mv -- "$temporary" "$destination"
chmod -R u=rwX,g=rX,o= -- "$destination"
printf '%s\n' "$destination"
