#!/usr/bin/env bash
# Network transfer stays on the network-enabled login surface. Large digests run
# through the study's scheduled hash service. No restart loop or limit overrides.
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?}"
: "${FACTORCON_FAMILY:?}"
module load StdEnv/2023 python/3.12.4
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export FACTORCON_HASH_QUEUE="$FACTORCON_ALLIANCE_ROOT/operations/hash-service"
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
cd "$FACTORCON_RELEASE"
run="$FACTORCON_ALLIANCE_ROOT/operations/acquisition-repair-v1/$FACTORCON_FAMILY"
export FACTORCON_EXIT_RECORD="$run/worker-exit-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
finish() {
 code=$?
 trap - EXIT
 python - "$code" <<'PY'
import os,sys
from factorcon.util import atomic_write_json,utc_now
atomic_write_json(os.environ['FACTORCON_EXIT_RECORD'],{
 'exit_code':int(sys.argv[1]),'ended_utc':utc_now(),'host':os.uname().nodename,
 'source':os.environ['FACTORCON_RELEASE'],'family':os.environ['FACTORCON_FAMILY'],
 'note':'137 is consistent with SIGKILL; scheduler or admin evidence needed for cause.'})
PY
 exit "$code"
}
trap finish EXIT
extra=()
if [[ "$FACTORCON_FAMILY" == cogitate ]]; then
 extra=(--catalog "$FACTORCON_ALLIANCE_ROOT/operations/private-catalogs/cogitate-exp1-20260916.json")
fi
python -u scripts/alliance/repair_acquisition.py --root "$FACTORCON_ALLIANCE_ROOT" --family "$FACTORCON_FAMILY" "${extra[@]}"
