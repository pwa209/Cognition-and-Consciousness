#!/usr/bin/env bash
#SBATCH --job-name=fc-neural-input-audit
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal scratch root required}"
: "${FACTORCON_RELEASE:?immutable release required}"
: "${FACTORCON_QUALIFICATION_JOB:?qualification required}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/qualification-$FACTORCON_QUALIFICATION_JOB/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
cd "$FACTORCON_RELEASE"
python -u scripts/alliance/neural_readiness.py --root "$FACTORCON_ALLIANCE_ROOT" --job "$SLURM_JOB_ID"
