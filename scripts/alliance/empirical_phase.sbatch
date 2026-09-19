#!/usr/bin/env bash
#SBATCH --job-name=fc-empirical
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=48:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal fresh root required}"
: "${FACTORCON_RELEASE:?immutable source release required}"
: "${FACTORCON_QUALIFICATION_JOB:?successful qualification required}"
: "${FACTORCON_PHASE:?P03 or P04 required}"
: "${FACTORCON_FAMILY:?family required}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/qualification-$FACTORCON_QUALIFICATION_JOB/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
unset FACTORCON_HASH_QUEUE
cd "$FACTORCON_RELEASE"
python - "$FACTORCON_ALLIANCE_ROOT/qualification/$FACTORCON_QUALIFICATION_JOB/status.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['status']=='SUCCESS'
PY
args=(--root "$FACTORCON_ALLIANCE_ROOT" --phase "$FACTORCON_PHASE" --family "$FACTORCON_FAMILY")
if [[ -n "${FACTORCON_PREDECESSOR:-}" ]]; then args+=(--predecessor "$FACTORCON_PREDECESSOR"); fi
if [[ -n "${FACTORCON_PREDECESSOR_SOURCE:-}" ]]; then args+=(--predecessor-source "$FACTORCON_PREDECESSOR_SOURCE"); fi
python -u scripts/alliance/empirical_phase.py "${args[@]}"
