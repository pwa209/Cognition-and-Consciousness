#!/usr/bin/env bash
#SBATCH --job-name=fc-environment-consolidation
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=04:00:00
set -euo pipefail
: "${FACTORCON_RELEASE:?immutable release required}"
root=/scratch/pwa209/cognition-and-consciousness/fresh-20260916
module load StdEnv/2023 python/3.12.4
source "$root/environments/report-pymc-5.24.0-arviz-0.22.0-v1/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$root/tmp" XDG_CACHE_HOME="$root/cache/xdg"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
cd "$FACTORCON_RELEASE"
exec python -u scripts/alliance/archive_environments.py
