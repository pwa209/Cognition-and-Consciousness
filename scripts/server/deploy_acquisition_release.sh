#!/usr/bin/env bash
set -Eeuo pipefail

die() {
  printf '%s\n' "ERROR: $*" >&2
  exit 2
}

commit="${1:-}"
canonical_root="${2:-}"
fast_root="${3:-}"
restart_root="${4:-}"
confirmation="${5:-}"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || \
  die "usage: deploy_acquisition_release.sh COMMIT CANONICAL_ROOT FAST_ROOT RESTART_ROOT --confirm-roots"
[[ "$confirmation" == "--confirm-roots" ]] || die "explicit --confirm-roots is required"
[[ "$(hostname)" == "kemove-Rack-Server" ]] || die "unexpected hostname: $(hostname)"
[[ "$(id -un)" == "wangpeng" ]] || die "unexpected user: $(id -un)"
case "$canonical_root" in
  /private_nas/wangpeng/*) ;;
  *) die "unsafe canonical root: $canonical_root" ;;
esac
case "$restart_root" in
  /data2/wangpeng/*) ;;
  *) die "unsafe restart root: $restart_root" ;;
esac
case "$fast_root" in
  /data1/wangpeng/*) ;;
  *) die "unsafe fast root: $fast_root" ;;
esac

destination="$canonical_root/source/acquisition-releases/$commit"
if [[ -d "$destination/.git" ]]; then
  observed="$(git -C "$destination" rev-parse HEAD)"
  [[ "$observed" == "$commit" ]] || die "existing release has unexpected commit $observed"
  printf '%s\n' "$destination"
  exit 0
fi
[[ ! -e "$destination" ]] || die "unverified destination already exists: $destination"

temporary="$restart_root/checkpoints/acquisition-deploy-$commit"
[[ ! -e "$temporary" ]] || die "temporary deploy target already exists: $temporary"
mkdir -p -- "$(dirname -- "$temporary")"
git clone --filter=blob:none --no-checkout \
  https://github.com/pwa209/Cognition-and-Consciousness.git "$temporary"
git -C "$temporary" sparse-checkout set --no-cone \
  /conf/base.yaml \
  /conf/analysis_spec.yaml \
  /conf/server_h100.yaml \
  /conf/datasets/ \
  /conf/construct_maps/ \
  /src/factorcon/__init__.py \
  /src/factorcon/acquisition_cli.py \
  /src/factorcon/config.py \
  /src/factorcon/errors.py \
  /src/factorcon/util.py \
  /src/factorcon/acquire/ \
  /scripts/server/lib.sh \
  /scripts/server/run_acquisition.sh \
  /scripts/server/queue_acquisition.sh
git -C "$temporary" checkout --detach "$commit"
observed="$(git -C "$temporary" rev-parse HEAD)"
[[ "$observed" == "$commit" ]] || die "checkout mismatch: $observed"
[[ -f "$temporary/src/factorcon/acquisition_cli.py" ]] || die "acquisition entry point missing"
[[ ! -e "$temporary/src/factorcon/pipeline" ]] || die "analysis pipeline entered sparse release"
source "$temporary/scripts/server/lib.sh"
config_path="$temporary/conf/base.yaml"
[[ "$(factorcon_config_value "$config_path" server roots_status)" == "owner_confirmed" ]] || \
  die "release does not record owner-confirmed roots"
[[ "$(factorcon_config_value "$config_path" server deployment_scope)" == "acquisition_only" ]] || \
  die "release is not restricted to acquisition-only deployment"
[[ "$(factorcon_config_value "$config_path" server canonical_root)" == "$canonical_root" ]] || \
  die "canonical-root argument does not match release configuration"
[[ "$(factorcon_config_value "$config_path" server fast_root)" == "$fast_root" ]] || \
  die "fast-root argument does not match release configuration"
[[ "$(factorcon_config_value "$config_path" server restart_root)" == "$restart_root" ]] || \
  die "restart-root argument does not match release configuration"

mkdir -p -- "$(dirname -- "$destination")"
mv -- "$temporary" "$destination"
chmod -R u=rwX,g=rX,o= -- "$destination"
printf '%s\n' "$destination"
