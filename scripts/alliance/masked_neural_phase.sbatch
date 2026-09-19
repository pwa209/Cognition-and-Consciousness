#!/usr/bin/env bash
#SBATCH --job-name=fc-masked-neural
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=24:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal root required}"
: "${FACTORCON_RELEASE:?immutable source required}"
: "${FACTORCON_QUALIFICATION_JOB:?qualification required}"
: "${FACTORCON_PHASE:?phase required}"
: "${FACTORCON_P03:?full SHA predecessor required}"
: "${FACTORCON_P03_SOURCE:?predecessor release required}"
module load StdEnv/2023 python/3.12.4
if [[ "$FACTORCON_PHASE" == PREPROCESS ]]; then module load fmriprep/25.1.1; fi
source "$FACTORCON_ALLIANCE_ROOT/environments/qualification-$FACTORCON_QUALIFICATION_JOB/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
unset FACTORCON_HASH_QUEUE
cd "$FACTORCON_RELEASE"
python - "$FACTORCON_ALLIANCE_ROOT/qualification/$FACTORCON_QUALIFICATION_JOB/status.json" "$FACTORCON_RELEASE" <<'PY'
import json,pathlib,sys
assert json.load(open(sys.argv[1]))['status']=='SUCCESS'
assert json.load(open(pathlib.Path(sys.argv[1]).with_name('provenance.json')))['source_release']==sys.argv[2]
PY
args=(--root "$FACTORCON_ALLIANCE_ROOT" --phase "$FACTORCON_PHASE" --p03 "$FACTORCON_P03" --producer "$FACTORCON_P03_SOURCE")
if [[ -n "${FACTORCON_PREPARED:-}" ]]; then args+=(--prepared "$FACTORCON_PREPARED"); fi
if [[ "$FACTORCON_PHASE" == PREPROCESS ]]; then args+=(--subject-index "${SLURM_ARRAY_TASK_ID:-0}"); fi
python -u scripts/alliance/masked_neural_phase.py "${args[@]}"
