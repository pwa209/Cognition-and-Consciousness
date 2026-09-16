#!/usr/bin/env bash
#SBATCH --job-name=fc-WM
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal fresh root required}"
: "${FACTORCON_RELEASE:?immutable source release required}"
: "${FACTORCON_QUALIFICATION_JOB:?successful environment qualification required}"
: "${FACTORCON_WM_PHASE:?P03 or P04 required}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/qualification-$FACTORCON_QUALIFICATION_JOB/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp"
export XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
cd "$FACTORCON_RELEASE"
python - "$FACTORCON_ALLIANCE_ROOT/qualification/$FACTORCON_QUALIFICATION_JOB/status.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['status']=='SUCCESS'
PY
python -m pytest -q tests/integration/test_alliance_lifecycle.py \
  tests/integration/test_working_memory_adapter.py \
  -o cache_dir="$FACTORCON_ALLIANCE_ROOT/operations/wm-tests-$SLURM_JOB_ID"
python scripts/alliance/wm_phase.py --root "$FACTORCON_ALLIANCE_ROOT" --phase "$FACTORCON_WM_PHASE" --dry-run
python scripts/alliance/wm_phase.py --root "$FACTORCON_ALLIANCE_ROOT" --phase "$FACTORCON_WM_PHASE"
