# Masked MRI preprocessing and independent report calibration

This is a non-preregistered secondary analysis. The versioned plan records current
choices, not registration or an unopened lockbox. No scientific gates apply.

## Scope and phase mapping

| Stage | Input | Output | Remaining boundary |
|---|---|---|---|
| PREPARE (P04 extension) | P03-verified ds003927 1.0.3 | 380-run manifest, subject allocation, deduplicated calibration trials | Not a neural model input |
| CALIBRATE (P04 measurement) | Two ID-hash-reserved participants | Four-chain ordinal-probit report posterior, diagnostics | Not independent neural noise calibration or universal E |
| PREPROCESS (P06 prerequisite) | All seven participants' raw MRI | fMRIPrep volumes, confounds, anatomy, reports, hashes | Not GLM features or P06 pattern bundles |
| Future raw-to-model integration | Audited raw event alignment, preprocessed MRI, disjoint calibration | Runwise patterns, residuals, construct design | Not implemented by this release |
| P06–P10 | Validated real pattern bundles | Architectures, uncertainty, reporting | Existing wrappers remain input-blocked |

The source has seven participants and 380 runs, with 12,087 represented trials:
360 runs contain 32 trials, 18 contain 31, one contains eight and one contains one.
Short runs are retained, with coverage recorded. Published event rows repeat trial
metadata across volumes; collapsing by run and trial avoids pseudo-replication.
Any within-trial disagreement fails preparation rather than selecting one row.
Missing visibility is -1, never no experience. Source probe_frame=99 is a parser
failure sentinel, not physical duration; represent it by a fixed zero placeholder
plus a missingness indicator, retaining the trial. Other source frame counts are
not converted to seconds or treated as fully verified physical stimulus duration.

## Independent report calibration

Rank participant IDs by SHA-256 of `260830:masked_content_fmri:<subject>`, then
reserve the two smallest hashes for calibration. All their sessions stay together;
the other five participants supply neural evaluation. No report values, neural
values or model scores select this allocation. Reusing reserved participants under
another dataset alias is forbidden. Metadata schema auditing may read all events,
but the calibration fitting input contains reserved participants only.

Fixed design columns are intercept, source frame count/10 (zero if unavailable),
nonliving-category indicator and missing-frame indicator. The zero is a placeholder
with its own coefficient, not a claim of zero exposure. Hierarchical participant
and participant/session effects use the existing model: four chains, 1,000 warmup
and 1,000 retained draws each. Poor mixing is recorded, not suppressed. Interpretation
must respect diagnostics and missingness; operational success is not scientific
validation. This calibration alone does not distinguish E from S, motor response,
confidence, accuracy or image properties. Existing construct-map controls remain
required in future neural integration, and cross-family common anchors remain open.

## Timing warning, grounded in upstream source

At upstream `nmningmei/unconfeats` revision
`5560619d791cd16f2b8b1a0432870a90df60afb9`,
`scripts/fMRI/nipype_convert_create_folders/create event file.py` subtracts ten TRs
from behavioral stimulus onset before making volume-level events. `scripts/fMRI/utils.py`
uses 99 when digit extraction fails. These source files were read, not executed.
Raw-versus-published event alignment must be verified before GLM or neural windows;
do not blindly apply a ten-volume shift without header and behavioral checks.
fMRIPrep preprocessing does not use these event timings to fit task contrasts.

## Runtime and storage

Installed module `fmriprep/25.1.1` actually reports software **25.1.3**. Check the
runtime version, rather than claiming the module label is its version. Use the
installed read-only CVMFS container, public TemplateFlow references prefetched on
the login node, and an owner-only licence outside Git. All study downloads, home,
cache, temporary files, working directories and derivatives remain beneath the
personal fresh-run scratch root; never `/project`. No licence bytes appear in
source/provenance. Runtime receipts include package versions and template hashes.

Preprocessing uses T1w and MNI152NLin2009cAsym resolution-2 outputs, OASIS30ANTs
skull stripping, no FreeSurfer reconstruction, no spatial smoothing, default BIDS
validation, fixed random seed, eight CPUs (four per OpenMP process), 64 GB Slurm
memory with a 56,000 MB application limit, and five-day walltime per participant.
Eight CPUs/four OpenMP threads do not imply bitwise ANTs reproducibility.

## Execution and restart

`scripts/alliance/submit_masked_neural.py --root ROOT --p03 P03_STATUS --producer P03_SOURCE`
checks source integrity, ownership, live personal quota, runtime readiness and a
PREPARE dry-run. It submits a fresh qualification job, PREPARE after qualification,
CALIBRATE after PREPARE, a first-subject MRI pilot after PREPARE, then subjects 2–7
as an array at concurrency two after successful pilot preprocessing. The pilot is
technical validation only; effects and report outcomes never decide continuation.
Calibration and preprocessing do not depend on each other's scientific results.

Each stage has atomic status and provenance; completed outputs are hash-bound.
Repeated dispatch with identical receipts does not duplicate jobs. An uncertain
submission requires scheduler reconciliation. Failed attempts remain untouched;
a retry needs a new Slurm ID/attempt directory. This version restarts failed MRI
participants in a fresh work directory, not by silently reusing incomplete output.
SIGTERM records failure; SIGKILL/node failure requires scheduler reconciliation.
Only verified outputs count as complete, not a queued job or zero exit alone.

Local tests use tiny synthetic path/event fixtures, not real MRI. A real cluster
pilot is still needed to validate container behavior and empirical output naming.
No other dataset family is declared preprocessed by this release.

## Deployment receipt (2026-09-19 15:29:55 UTC)

Code `5c3cb879099efd4b59b210d6fc109af218a74447` is on the project GitHub branch and
installed as an immutable fresh-run release; 204 transferred source files verified.
Local full suite: 207 passed. Reference prefetch completed (256 hashed files).
Licence contents are private and absent from this repository.

| Scheduler job | Scope | State at 15:31 UTC |
|---|---|---|
| 21417196 | Isolated software/tests | Running |
| 21417197 | Trial/run preparation | Pending qualification |
| 21417198 | Independent report posterior | Pending preparation |
| 21417199 | First-participant actual fMRIPrep | Pending preparation |
| 21417200_[1-6%2] | Remaining six participants | Pending technical pilot |

Receipt directory, relative to the personal fresh root:
`operations/masked-neural/5c3cb879099efd4b59b210d6fc109af218a74447/`.
Private stage outputs are under `analysis/masked-neural/`. Submitted is not complete.

### Initial execution (15:33 UTC)

Qualification passed all 207 tests remotely. PREPARE completed with 12,087 actual
trials, 521 missing reports, 186 missing frame counts and 3,447 calibration trials.
The first report fit completed at 15:31:56 UTC but has R-hat 2.51947 and minimum
bulk ESS 4.79452: **not reliable for interpretation**. A sampling-only extension is
specified in `conf/masked_report_sampling_extension.yaml`: four chains, 20,000
warmup and 10,000 retained draws each. Its runner verifies producer and consumer
releases, unchanged scientific configuration and every prepared-input hash; it
preserves the original posterior. Future warnings remain visible. MRI pilot 21417199
was running at 15:33 UTC, with the six remaining participants pending that technical
predecessor. No neural inference depends on this unconverged posterior yet.
