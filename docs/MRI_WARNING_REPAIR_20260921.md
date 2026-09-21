# MRI warning-handler compatibility repair — 21 September 2026

## Evidence and scope

At 05:24 UTC, MRI jobs 21450698 and 21450699 had completed and their work
directories had been byte-verified and archived. Together with the original pilot,
three of seven masked-fMRI participants were complete. Job 21450700 failed in the
`conf_plot` node with `TypeError: _warn() got an unexpected keyword argument
'skip_file_prefixes'`. Its three successors 21450701, 21450703 and 21450704 were
canceled without execution. Personal scratch had 750,576 entries (of 1,000,000)
and approximately 9.51 TB (of 20 TB); this failure was not quota exhaustion.

The exact installed fMRIPrep `_warnings.py` source was inspected, with SHA-256
`46b8867618f34511847d3c6036dc15a66123433036814415cf05a9001cf42e2f`.
Its custom warning function lacks Python 3.12's keyword-only `skip_file_prefixes`.
Matplotlib supplies that argument when emitting diagnostic warnings. The matching
failure is documented in [fMRIPrep issue 3478](https://github.com/nipreps/fmriprep/issues/3478).

## Repair and validation

`fmriprep_warning_compat.py` verifies the original file's exact SHA, then changes
only the `_warn` signature to accept `skip_file_prefixes=()`. Its logging body is
unchanged: warnings remain visible. Like the original handler, it logs the warning
rather than using Python's source-location machinery. This is a local narrow
compatibility patch, not an assertion that an upstream patch was installed.

The generated file is read-only bound over the single container source file.
The CVMFS image, old source releases and protected environments are unchanged.
Generated-source hashes and provenance are retained in personal scratch. No
participant inputs or neural transformations are modified. The original MRI
source, seed, spaces, templates, resources, preparation and cohort partition remain
unchanged; the completed three participants and converged report calibration are
not repeated. The failed participant receives a fresh attempt and is recomputed;
its old partial derivatives, work, logs and failure marker remain untouched.

Qualification runs the full test suite and two actual-container regressions:
the unmodified handler must reproduce the known TypeError; the patched handler
must log warnings and render >20 synthetic figures in both a parent process and
a forkserver worker. An unexpected baseline or missing warning fails qualification.
These are technical validity checks, never scientific outcome gates.

## Deployment contract

Plan: `conf/mri_warning_recovery_plan.yaml`. Dispatch:
`python scripts/alliance/submit_mri_warning_recovery.py` from a verified release.
It validates identity, ownership, quota, original terminal job states, absence of
successful target participants and active MRI retries. A shared dispatch lock and
durable intent/submission receipts prevent automatic duplicate/uncertain dispatch.

The sequence is qualification → participant indices 3 → 4 → 5 → 6. Each MRI job
uses unchanged numerical preprocessing and periodic quota guards, validates its
required outputs, and verifies/archives its own work before the next job starts.
The existing P05 pattern array is not resubmitted or modified. No automatic local
monitor is reactivated. A failed qualification or MRI job preserves failure records
and blocks its technical successors; repairs require a newly reconciled attempt.

## Remaining study work

This restores masked-MRI preprocessing, not the entire empirical pipeline.
Event alignment, neural feature extraction, independent neural-noise calibration,
and integration into the empirical M0–M5 evaluation still remain. The study remains
non-preregistered; null/unfavorable scientific results never stop later phases.

Local validation: 17 targeted tests passed; full suite 245 passed, 5 skipped
(Windows symlink permissions and unavailable local PyMC/ArviZ). Ruff and shell
syntax checks passed. The complete suite is also required on Rorqual, where the
protected qualification environment contains the scientific dependencies.

Submission IDs and live verification will be appended after deployment.
