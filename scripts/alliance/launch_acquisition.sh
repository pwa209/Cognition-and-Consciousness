#!/usr/bin/env bash
# Run on the network-enabled login/transfer surface, one low-priority HTTP worker.
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal fresh root required}"
: "${FACTORCON_RELEASE:?verified source release required}"
module load StdEnv/2023 python/3.12.4
export PYTHONPATH="$FACTORCON_RELEASE/src"
export PYTHONDONTWRITEBYTECODE=1
cd "$FACTORCON_RELEASE"
python scripts/alliance/acquire_fresh.py --root "$FACTORCON_ALLIANCE_ROOT" --dry-run
run="$FACTORCON_ALLIANCE_ROOT/operations/acquisition"
mkdir -p "$run"
# The process lock in acquire_fresh.py is the authority, not a stale PID file.
if [[ -f "$run/launch.pid" ]] && kill -0 "$(<"$run/launch.pid")" 2>/dev/null; then
  printf 'Existing acquisition PID is alive; reconcile instead of duplicate launch\n'
  exit 2
fi
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
nohup nice -n 10 python -u scripts/alliance/acquire_fresh.py \
  --root "$FACTORCON_ALLIANCE_ROOT" > "$run/console-$stamp.log" 2>&1 < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$run/launch.pid.tmp"
mv "$run/launch.pid.tmp" "$run/launch.pid"
printf 'ACQUISITION_LAUNCHED_PID=%s LOG=%s\n' "$pid" "$run/console-$stamp.log"
