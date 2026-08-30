#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname -- "$0")/lib.sh"
repo_root="$(factorcon_repo_root)"
phase="${1:-}"
family="${2:-}"
[[ "$phase" =~ ^P(0[0-9]|10)$ ]] || factorcon_die "usage: queue_phase.sh P00..P10 [family]"
session="factorcon-$phase${family:+-$family}"
if tmux has-session -t "$session" 2>/dev/null; then
  factorcon_die "tmux session already exists: $session"
fi
tmux new-session -d -s "$session" "$repo_root/scripts/server/run_phase.sh" "$phase" "$family"
printf '%s\n' "queued $session"

