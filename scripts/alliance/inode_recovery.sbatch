#!/usr/bin/env bash
#SBATCH --job-name=fc-inode-recovery
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=12:00:00
set -euo pipefail
: "${FACTORCON_RELEASE:?repair release required}"
: "${FACTORCON_MODE:?recovery mode required}"
: "${FACTORCON_ENVIRONMENT:?study environment required}"
: "${FACTORCON_SCIENCE_SOURCE:?original scientific release required}"
root=/scratch/pwa209/cognition-and-consciousness/fresh-20260916
module load StdEnv/2023 python/3.12.4
if [[ "$FACTORCON_MODE" == mri \
  || "${FACTORCON_RECOVERY_PLAN:-}" == mri_warning_recovery_plan.yaml \
  || "${FACTORCON_RECOVERY_PLAN:-}" == mri_quota_recovery_plan.yaml ]]; then
  module load fmriprep/25.1.1
fi
source "$root/environments/$FACTORCON_ENVIRONMENT/bin/activate"
export PYTHONPATH="$FACTORCON_SCIENCE_SOURCE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$root/tmp" XDG_CACHE_HOME="$root/cache/xdg" PIP_CACHE_DIR="$root/cache/pip"
export MPLCONFIGDIR="$root/cache/matplotlib-sampler" NUMBA_CACHE_DIR="$root/cache/numba"
export PYTENSOR_FLAGS="base_compiledir=$root/cache/pytensor/$SLURM_JOB_ID,blas__ldflags="
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
unset FACTORCON_HASH_QUEUE
cd "$FACTORCON_RELEASE"
exec python -u scripts/alliance/inode_recovery.py --mode "$FACTORCON_MODE" --plan "${FACTORCON_RECOVERY_PLAN:-inode_recovery_plan.yaml}"
