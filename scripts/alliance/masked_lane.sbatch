#!/usr/bin/env bash
#SBATCH --job-name=fc-masked-lane
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?}"
: "${FACTORCON_INPUT:?}"
: "${FACTORCON_INPUT_SHA256:?}"
: "${FACTORCON_STAGE:?}"
module load StdEnv/2023 python/3.12.4
if [[ "$FACTORCON_STAGE" == EXTRACT || "$FACTORCON_STAGE" == QUALIFY ]]; then module load fmriprep/25.1.1; fi
source "$FACTORCON_ALLIANCE_ROOT/environments/report-pymc-5.24.0-arviz-0.22.0-v1/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
unset FACTORCON_HASH_QUEUE
cd "$FACTORCON_RELEASE"
if [[ "$FACTORCON_STAGE" == QUALIFY ]]; then
  python -u scripts/alliance/masked_lane_qualification.py --root "$FACTORCON_ALLIANCE_ROOT"
else
  python - "$FACTORCON_ALLIANCE_ROOT" "${FACTORCON_QUALIFICATION_JOB:?}" "$FACTORCON_RELEASE" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1])/'qualification'/sys.argv[2]/'status.json'
v=json.loads(p.read_text())
assert v['status']=='SUCCESS' and v['source_release']==sys.argv[3]
PY
  if [[ "$FACTORCON_STAGE" == P* ]]; then
    python -u scripts/alliance/masked_lane_downstream.py --root "$FACTORCON_ALLIANCE_ROOT" --input "$FACTORCON_INPUT" --input-sha256 "$FACTORCON_INPUT_SHA256"
  else
    python -u scripts/alliance/masked_lane_phase.py --root "$FACTORCON_ALLIANCE_ROOT" \
      --input "$FACTORCON_INPUT" --input-sha256 "$FACTORCON_INPUT_SHA256" \
      --attempt "$FACTORCON_ALLIANCE_ROOT/analysis/masked-lane/$FACTORCON_STAGE/$SLURM_JOB_ID"
  fi
fi
