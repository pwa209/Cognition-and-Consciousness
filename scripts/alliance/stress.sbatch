#!/usr/bin/env bash
#SBATCH --job-name=fc-P05
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal fresh root required}"
: "${FACTORCON_RELEASE:?source required}"
: "${FACTORCON_QUALIFICATION_JOB:?successful qualification job required}"
: "${FACTORCON_STRESS_SUITE:?reports or patterns required}"
module load StdEnv/2023 python/3.12.4
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp"
export PIP_CACHE_DIR="$FACTORCON_ALLIANCE_ROOT/cache/pip"
export XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
source "$FACTORCON_ALLIANCE_ROOT/environments/qualification-$FACTORCON_QUALIFICATION_JOB/bin/activate"
cd "$FACTORCON_RELEASE"
python - "$FACTORCON_ALLIANCE_ROOT/qualification/$FACTORCON_QUALIFICATION_JOB/status.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['status']=='SUCCESS', 'technical qualification not successful'
PY
python scripts/alliance/stress_shard.py --root "$FACTORCON_ALLIANCE_ROOT" \
  --suite "$FACTORCON_STRESS_SUITE" --replicate "$SLURM_ARRAY_TASK_ID" --dry-run
python scripts/alliance/stress_shard.py --root "$FACTORCON_ALLIANCE_ROOT" \
  --suite "$FACTORCON_STRESS_SUITE" --replicate "$SLURM_ARRAY_TASK_ID"
