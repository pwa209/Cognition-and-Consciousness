#!/usr/bin/env bash
#SBATCH --job-name=fc-report-nuts
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --signal=B:TERM@120
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?}"
: "${FACTORCON_PREPARED_SOURCE:?}"
: "${FACTORCON_PREPARED:?}"
: "${FACTORCON_PHASE:?}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/report-pymc-5.24.0-arviz-0.22.0-v1/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp"
export XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export MPLCONFIGDIR="$FACTORCON_ALLIANCE_ROOT/cache/matplotlib-sampler"
export PYTENSOR_FLAGS="base_compiledir=$FACTORCON_ALLIANCE_ROOT/cache/pytensor/$SLURM_JOB_ID,blas__ldflags="
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$FACTORCON_RELEASE"
extra=()
if [[ "$FACTORCON_PHASE" == CALIBRATE_NUTS ]]; then
  extra=(--qualification "$FACTORCON_ALLIANCE_ROOT/analysis/masked-neural/QUALIFY_NUTS/${FACTORCON_QUALIFICATION_JOB:?}/status.json")
fi
exec python -u scripts/alliance/repair_masked_report.py --root "$FACTORCON_ALLIANCE_ROOT" \
 --producer "$FACTORCON_PREPARED_SOURCE" --prepared "$FACTORCON_PREPARED" \
 --phase "$FACTORCON_PHASE" "${extra[@]}"
