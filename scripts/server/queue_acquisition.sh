#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
release_root="$(factorcon_repo_root)"
action="${1:-}"
family="${2:-}"
[[ "$action" == "resolve" || "$action" == "download" ]] || \
  factorcon_die "usage: queue_acquisition.sh {resolve|download} [family]"
session="factorcon-acquisition-$action${family:+-$family}"
if tmux has-session -t "$session" 2>/dev/null; then
  factorcon_die "tmux session already exists: $session"
fi
tmux new-session -d -s "$session" \
  "$release_root/scripts/server/run_acquisition.sh" "$action" "$family"
printf '%s\n' "queued $session"
