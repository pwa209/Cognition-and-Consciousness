#!/usr/bin/env bash
#SBATCH --job-name=fc-downstream
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=48:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal scratch root required}"
: "${FACTORCON_RELEASE:?immutable release required}"
: "${FACTORCON_QUALIFICATION_JOB:?qualification required}"
: "${FACTORCON_CAMPAIGN:?private empirical campaign required}"
: "${FACTORCON_CAMPAIGN_SHA256:?submitted campaign identity required}"
: "${FACTORCON_PHASE:?P06-P10 required}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/qualification-$FACTORCON_QUALIFICATION_JOB/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp" XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
unset FACTORCON_HASH_QUEUE
cd "$FACTORCON_RELEASE"
python - "$FACTORCON_ALLIANCE_ROOT/qualification/$FACTORCON_QUALIFICATION_JOB/provenance.json" "$FACTORCON_RELEASE" <<'PY'
import json,sys
v=json.load(open(sys.argv[1]))
assert v['status']=='SUCCESS' and v['source_release']==sys.argv[2]
PY
args=(--root "$FACTORCON_ALLIANCE_ROOT" --campaign "$FACTORCON_CAMPAIGN" --campaign-sha256 "$FACTORCON_CAMPAIGN_SHA256" --phase "$FACTORCON_PHASE")
if [[ -n "${FACTORCON_P06_STATUS:-}" ]]; then args+=(--p06 "$FACTORCON_P06_STATUS"); fi
if [[ -n "${FACTORCON_GRAPH:-}" ]]; then args+=(--graph "$FACTORCON_GRAPH" --graph-sha256 "${FACTORCON_GRAPH_SHA256:?}"); fi
if [[ "$FACTORCON_PHASE" == P09 ]]; then args+=(--replicate "${SLURM_ARRAY_TASK_ID:?}"); fi
python -u scripts/alliance/downstream_phase.py "${args[@]}"
