#!/usr/bin/env bash
#SBATCH --job-name=fc-qualify
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?fresh personal scratch root required}"
: "${FACTORCON_RELEASE:?immutable source release required}"
: "${FACTORCON_PYTHON_MODULE:?preflight-verified Python 3.12 module required}"
case "$FACTORCON_ALLIANCE_ROOT" in /scratch/pwa209/cognition-and-consciousness/fresh-*) ;; *) exit 2;; esac
[[ "$(id -un)" == pwa209 ]]
module load StdEnv/2023 "$FACTORCON_PYTHON_MODULE"
cd "$FACTORCON_RELEASE"
run="$FACTORCON_ALLIANCE_ROOT/qualification/$SLURM_JOB_ID"
envdir="$FACTORCON_ALLIANCE_ROOT/environments/qualification-$SLURM_JOB_ID"
mkdir -p "$run" "$FACTORCON_ALLIANCE_ROOT/cache/pip" "$FACTORCON_ALLIANCE_ROOT/tmp"
export TMPDIR="$FACTORCON_ALLIANCE_ROOT/tmp"
export PIP_CACHE_DIR="$FACTORCON_ALLIANCE_ROOT/cache/pip"
export XDG_CACHE_HOME="$FACTORCON_ALLIANCE_ROOT/cache/xdg"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
export PYTHONPATH="$FACTORCON_RELEASE/src"
export PYTHONDONTWRITEBYTECODE=1
finish() {
  result=$?
  python - "$run" "$result" <<'PY'
import datetime,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); code=int(sys.argv[2])
record={'status':'SUCCESS' if code==0 else 'FAILED','exit_code':code,
        'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'environment_and_synthetic_tests_only','participant_data_analyzed':False}
tmp=root/'status.json.tmp'; tmp.write_text(json.dumps(record,indent=2)); tmp.replace(root/'status.json')
prov=json.loads((root/'provenance.json').read_text()); prov.update(record)
tmp=root/'provenance.json.tmp'; tmp.write_text(json.dumps(prov,indent=2)); tmp.replace(root/'provenance.json')
PY
  exit "$result"
}
trap finish EXIT
python - "$run" <<'PY'
import datetime,hashlib,json,os,pathlib,sys
assert sys.version_info[:2]==(3,12), sys.version
p=pathlib.Path(sys.argv[1]); source=pathlib.Path.cwd()
record={'status':'RUNNING','python':sys.version,'job_id':os.environ['SLURM_JOB_ID'],
        'source_release':str(source),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'analysis_spec_sha256':hashlib.sha256((source/'conf/analysis_spec.yaml').read_bytes()).hexdigest(),
        'participant_data_analyzed':False,'cpus':4,'memory_gib':16,'gpus':0}
for name in ('status.json','provenance.json'):
    tmp=p/(name+'.tmp'); tmp.write_text(json.dumps(record,indent=2)); tmp.replace(p/name)
PY
module list 2> "$run/modules.txt"
python -m venv "$envdir"
source "$envdir/bin/activate"
# Compute nodes have restricted internet: use cluster wheels, never another study's env.
python -m pip install --no-index 'numpy>=2,<3' 'scipy>=1.14,<2' 'pytest>=8.3,<9' > "$run/install.log" 2>&1
python -m pip freeze > "$run/packages.txt"
python -m factorcon config validate --config conf/base.yaml > "$run/config.json"
python scripts/alliance/acquire_fresh.py --root "$FACTORCON_ALLIANCE_ROOT" --dry-run > "$run/acquisition-dry-run.json"
for suite in reports patterns; do
  python scripts/alliance/stress_shard.py --root "$FACTORCON_ALLIANCE_ROOT" --suite "$suite" \
    --replicate 0 --dry-run > "$run/stress-$suite-dry-run.json"
done
python -m pytest -q --cache-clear -o cache_dir="$run/pytest-cache" --basetemp="$run/pytest-temp" --junitxml="$run/tests.xml" > "$run/tests.log" 2>&1
printf 'ENVIRONMENT=%s\n' "$envdir" > "$run/environment.txt"
