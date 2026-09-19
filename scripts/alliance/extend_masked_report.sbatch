#!/usr/bin/env bash
#SBATCH --job-name=fc-masked-calibrate-extended
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=04:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?root required}"
: "${FACTORCON_RELEASE:?consumer required}"
: "${FACTORCON_PREPARED_SOURCE:?producer required}"
: "${FACTORCON_PREPARED:?preparation status required}"
: "${FACTORCON_QUALIFICATION_JOB:?qualification required}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/qualification-$FACTORCON_QUALIFICATION_JOB/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
cd "$FACTORCON_RELEASE"
python - "$FACTORCON_ALLIANCE_ROOT/qualification/$FACTORCON_QUALIFICATION_JOB/status.json" "$FACTORCON_RELEASE" <<'PY'
import json,pathlib,sys
assert json.load(open(sys.argv[1]))['status']=='SUCCESS'
assert json.load(open(pathlib.Path(sys.argv[1]).with_name('provenance.json')))['source_release']==sys.argv[2]
PY
python -u scripts/alliance/extend_masked_report.py --root "$FACTORCON_ALLIANCE_ROOT" \
 --producer "$FACTORCON_PREPARED_SOURCE" --prepared "$FACTORCON_PREPARED"
