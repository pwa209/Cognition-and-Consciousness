#!/usr/bin/env bash
#SBATCH --job-name=fc-mri-work-quota-relief
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=24:00:00
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?}"
: "${FACTORCON_RELEASE:?}"
module load StdEnv/2023 python/3.12.4
source "$FACTORCON_ALLIANCE_ROOT/environments/report-pymc-5.24.0-arviz-0.22.0-v1/bin/activate"
export PYTHONPATH="$FACTORCON_RELEASE/src:$FACTORCON_RELEASE/scripts/alliance"
export PYTHONDONTWRITEBYTECODE=1
cd "$FACTORCON_RELEASE"
python -m pytest -q -p no:cacheprovider \
  --basetemp "$FACTORCON_ALLIANCE_ROOT/tmp/archive-quota-tests-$SLURM_JOB_ID" \
  tests/unit/test_work_archive.py tests/unit/test_archive_quota_work_20260928.py
python -u "$FACTORCON_RELEASE/scripts/alliance/archive_quota_work_20260928.py"
