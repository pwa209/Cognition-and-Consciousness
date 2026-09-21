#!/usr/bin/env bash
#SBATCH --job-name=fc-masked-P09-packed
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=48:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?original analysis release required}"
: "${FACTORCON_BATCH_RELEASE:?batch runner release required}"
: "${FACTORCON_INPUT:?}"
: "${FACTORCON_INPUT_SHA256:?}"
: "${FACTORCON_QUALIFICATION_JOB:?}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/report-pymc-5.24.0-arviz-0.22.0-v1/bin/activate"
export PYTHONPATH="$FACTORCON_BATCH_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
unset FACTORCON_HASH_QUEUE
python -u "$FACTORCON_BATCH_RELEASE/scripts/alliance/masked_bootstrap_batch.py" \
 --root "$FACTORCON_ALLIANCE_ROOT" --analysis "$FACTORCON_RELEASE" \
 --input "$FACTORCON_INPUT" --input-sha256 "$FACTORCON_INPUT_SHA256" \
 --qualification-job "$FACTORCON_QUALIFICATION_JOB"
