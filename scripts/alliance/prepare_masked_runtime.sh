#!/usr/bin/env bash
set -euo pipefail
: "${FACTORCON_ALLIANCE_ROOT:?personal fresh root required}"
: "${FACTORCON_RELEASE:?source release required}"
module load StdEnv/2023 python/3.12.4
export PYTHONPATH="$FACTORCON_RELEASE/src" PYTHONDONTWRITEBYTECODE=1
python - "$FACTORCON_ALLIANCE_ROOT" "$FACTORCON_RELEASE" <<'PY'
import sys
from pathlib import Path
from factorcon.alliance import validate_fresh_root,read_source_record,ScratchQuotaGuard
from factorcon.util import hash_file
root=validate_fresh_root(sys.argv[1]); source=Path(sys.argv[2])
record=read_source_record(root,source)
assert record.get('analysis_execution_authorized') is True
assert all(hash_file(source/p)==h for p,h in record['files'].items())
ScratchQuotaGuard(root/'operations/masked-runtime/personal-quota.json')(100_000_000_000)
PY
root="$FACTORCON_ALLIANCE_ROOT"
module load fmriprep/25.1.1
umask 077
mkdir -p "$root/cache/templateflow" "$root/cache/apptainer" "$root/tmp/fmriprep" "$root/private/container-home" "$root/cache/fmriprep-xdg"
export APPTAINER_CACHEDIR="$root/cache/apptainer" APPTAINER_TMPDIR="$root/tmp/fmriprep"
export APPTAINERENV_TEMPLATEFLOW_HOME="$root/cache/templateflow" APPTAINERENV_NIPYPE_NO_ET=1
export APPTAINERENV_TEMPLATEFLOW_USE_DATALAD=0 APPTAINERENV_TMPDIR="$root/tmp/fmriprep"
export APPTAINERENV_XDG_CACHE_HOME="$root/cache/fmriprep-xdg"
exec apptainer exec --cleanenv --home "$root/private/container-home" \
 --bind "$root:$root,$root/tmp/fmriprep:/tmp,$root/tmp/fmriprep:/var/tmp" \
 /cvmfs/containers.computecanada.ca/content/containers/fmriprep-25.1.1 \
 python -u "$FACTORCON_RELEASE/scripts/alliance/prepare_masked_runtime.py" --root "$root"
