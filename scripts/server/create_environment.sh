#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
repo_root="$(factorcon_repo_root)"
config_path="$repo_root/conf/base.yaml"
commit="${1:-$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)}"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || factorcon_die "usage: create_environment.sh [40-character-git-commit]"

expected_host="$(factorcon_config_value "$config_path" server expected_hostname)"
expected_user="$(factorcon_config_value "$config_path" server expected_user)"
canonical_root="$(factorcon_config_value "$config_path" server canonical_root)"
restart_root="$(factorcon_config_value "$config_path" server restart_root)"
factorcon_verify_identity "$expected_host" "$expected_user"
factorcon_require_root "$canonical_root" /private_nas/wangpeng
factorcon_require_root "$restart_root" /data2/wangpeng

release="$canonical_root/source/releases/$commit"
[[ -d "$release" ]] || factorcon_die "source release is not deployed: $release"
[[ "$(git -C "$release" rev-parse HEAD)" == "$commit" ]] || factorcon_die "release commit mismatch"
environment="$restart_root/environments/$commit"
[[ ! -e "$environment" ]] || factorcon_die "environment already exists: $environment"

temporary="$restart_root/checkpoints/environment-$commit"
[[ ! -e "$temporary" ]] || factorcon_die "temporary environment path already exists: $temporary"
python3 -m venv "$temporary"
"$temporary/bin/python" -m pip install --upgrade pip wheel setuptools
"$temporary/bin/python" -m pip install -r "$release/requirements/server.in"
"$temporary/bin/python" -m pip install --no-deps "$release"
"$temporary/bin/python" -m pytest -q "$release/tests"
mkdir -p -- "$canonical_root/manifests/generated/environments"
"$temporary/bin/python" -m pip freeze --all > "$canonical_root/manifests/generated/environments/$commit.txt"
mv -- "$temporary" "$environment"
printf '%s\n' "$environment"

