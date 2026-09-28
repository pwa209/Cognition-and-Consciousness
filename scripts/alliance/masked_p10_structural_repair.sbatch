#!/usr/bin/env bash
#SBATCH --job-name=fc-masked-p10-structural-repair
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?}"
: "${FACTORCON_REPAIR_STAGE:?}"
: "${FACTORCON_REPAIR_INPUT:?}"
: "${FACTORCON_REPAIR_INPUT_SHA256:?}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/report-pymc-5.24.0-arviz-0.22.0-v1/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
export MPLCONFIGDIR="$FACTORCON_ALLIANCE_ROOT/cache/matplotlib-sampler"
export PYTENSOR_FLAGS="base_compiledir=$FACTORCON_ALLIANCE_ROOT/cache/pytensor/$SLURM_JOB_ID,blas__ldflags="
unset FACTORCON_HASH_QUEUE
if [[ "$FACTORCON_REPAIR_STAGE" == P09 ]]; then
  mode=retry
elif [[ "$FACTORCON_REPAIR_STAGE" == P10 ]]; then
  mode=report
  export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
else
  echo 'unknown repair stage' >&2
  exit 2
fi
python -u "$FACTORCON_RELEASE/scripts/alliance/masked_p10_structural_repair.py" \
  --root "$FACTORCON_ALLIANCE_ROOT" --mode "$mode" \
  --input "$FACTORCON_REPAIR_INPUT" --input-sha256 "$FACTORCON_REPAIR_INPUT_SHA256"
