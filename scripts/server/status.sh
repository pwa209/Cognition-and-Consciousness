#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
repo_root="$(factorcon_repo_root)"
config_path="$repo_root/conf/base.yaml"
canonical_root="${FACTORCON_CANONICAL_ROOT:-$(factorcon_config_value "$config_path" server canonical_root)}"
export PYTHONPATH="$repo_root/src"
python3 -m factorcon status --config "$config_path" --canonical-root "$canonical_root"
printf '\nActive tmux sessions:\n'
tmux list-sessions -F '#{session_name}\t#{session_created_string}\t#{session_attached}' 2>/dev/null | awk '$1 ~ /^factorcon-/' || true

