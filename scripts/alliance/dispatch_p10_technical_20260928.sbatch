#!/usr/bin/env bash
#SBATCH --job-name=fc-p10-technical-dispatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/report-pymc-5.24.0-arviz-0.22.0-v1/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src:$FACTORCON_RELEASE/scripts/alliance"
export PYTHONDONTWRITEBYTECODE=1
python -u "$FACTORCON_RELEASE/scripts/alliance/masked_p10_structural_repair.py" \
  --root "$FACTORCON_ALLIANCE_ROOT" --mode dispatch-technical
