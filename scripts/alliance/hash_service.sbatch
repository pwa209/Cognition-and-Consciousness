#!/usr/bin/env bash
#SBATCH --job-name=fc-acq-hashing
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=2-00:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?}"
module load StdEnv/2023 python/3.12.4
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp"
cd "$FACTORCON_RELEASE"
python -u scripts/alliance/hash_service.py --root "$FACTORCON_ALLIANCE_ROOT"
