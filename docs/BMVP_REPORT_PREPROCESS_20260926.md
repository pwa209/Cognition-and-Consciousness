# BMVP report-MRI preprocessing extension (26 September 2026)

This is a transparent, non-preregistered secondary analysis. Technical failures
stop only affected jobs; null or unfavorable scientific results do not stop work.
The original masked-only P08 receipt remains unchanged and not applicable to
cross-family transfer.

## Fixed scope and evidence

The existing BMVP acquisition/P03 ledger and conversion receipts identify 13
converted 720-volume, 1-second report-MRI runs: four for participant 191,
five for 223, and four for 238. These three participants were chosen earlier
using log/CSV/series completeness, before neural outcomes. Each original TAR
contains one defaced structural NIfTI, behavioral CSV and PsychoPy log.
Conversion success did not establish usable event timing or neural preprocessing.

`conf/bmvp_report_preprocess.yaml` fixes the subjects, run order, conversion
jobs, counts, container settings and measurement limits. The preparation
worker verifies the original P03 archive record, independently rehashes all
13 converted functional NIfTI and JSON outputs, validates all TAR members
before reading, checks 720 scanner triggers against each run and 32 task
trials against each block, and checks DICOM/behavioral inter-run timing. It
then stages BIDS files on personal scratch. Functional NIfTI are hard-linked,
not copied; the three structural NIfTI are extracted to separate BIDS inputs.
The original TARs and conversion outputs are untouched. Event onsets are
seconds from the first scanner trigger; zero duration is documented as an
*onset impulse*, not a claim about stimulus duration. Missing perception
answers remain missing, never no-experience labels.

The subsequent three subject fMRIPrep jobs are serial and use the previously
qualified study runtime. Each requires MNI and T1w preprocessed functional
files plus confounds for every declared run. Only its quiescent `work` tree is
packed, byte-verified, and retired; raw archives, BIDS inputs, derivatives,
logs and failure records are never deletion targets. If archiving fails, the
source work tree is preserved and later jobs remain dependency-held. Every
attempt writes status/provenance JSON, and retries require a fresh job ID.
No controller or image processing runs on the login node. The dispatcher
requires at least 200 GB and 100,000 personal-scratch file slots free before
submission; it uses no shared `/project` storage.

## Phase map and inference limit

- The 13-run preparation is a BMVP P04 event-alignment and P05 input stage.
- Serial fMRIPrep is raw neural preprocessing, not a P06 pattern bundle.
- Independent neural-noise and report calibration, feature/condition mapping,
  and no-report neural coverage remain necessary for BMVP P06.
- Cross-study E and R scales cannot be validated by matching labels. These
  three report-only participants do not supply a no-report contrast, and
  reserving one for calibration would leave fewer than the required three
  independent BMVP evaluation participants. The acquired `238_NRP.tar` has
  one 600-volume and five 700-volume NIfTI but is not yet aligned or
  preprocessed; other no-report archives need technical review. Consequently
  no `independent_external_reviewed` bridge can yet be asserted and a new
  exploratory E–R P08 fit must remain not estimable. This is a measurement
  limitation, not a scientific-result gate.

## Operational contract

Deploy only a fresh immutable committed source release through
`scripts/alliance/prepare_release.py`. On Rorqual, first run
`submit_bmvp_report_preprocess.py --root ... --dry-run`; the real dispatcher
then submits full-suite qualification, one preparation job, and three serial
preprocessing jobs using `afterok` technical dependencies. Reconcile the
durable submission receipts with `squeue`/`sacct` before any retry. A Slurm
COMPLETED state is insufficient: inspect SUCCESS markers, output hashes,
per-run counts, and archived-work receipts. Do not promote P08 on the basis
of successful fMRIPrep alone.

## Rorqual execution checkpoint (26 September 2026, 19:06 UTC)

The first immutable release `a93debe600319bbabb3084aa21d5e5452012e7c9`
qualified, but PREPARE `21862964` failed on a sub-millisecond behavioral-clock
sign discrepancy. Its three fMRIPrep successors were cancelled before starting.
The outcome-blind 13-run timing audit justified the bounded symmetric correction
in `0afe38f5ce85463826a1d0e8495104c4ddbae1ec`. That release's PREPARE
`21863173` completed with 3 participants and 13 runs. Its first fMRIPrep job
`21863174` failed before imaging because the cluster container module was not
loaded; its successors were cancelled. A separate compute-node and exact
`sbatch --wrap` smoke test both resolved `apptainer` and returned fMRIPrep
v25.1.3 after `module load fmriprep/25.1.1`.

The current immutable release is `4d55ec8bcfa4d5fac999aa9923b15eff29ee22f8`.
QUALIFY `21864041` and PREPARE `21864042` have completed successfully;
PREPARE's receipt records 3 participants and 13 runs. PREPROCESS-191 `21864043`
is RUNNING with the container startup check passed; PREPROCESS-223 `21864044`
and PREPROCESS-238 `21864045` are dependency-pending, one at a time. None has
a SUCCESS derivative receipt yet. All failed attempts and their records remain
intact; no raw archive or completed output was deleted.

A read-only P03 ledger census found 37 report-MRI and 67 no-report BMVP
archives, with only two participant IDs present in both classes. Among the
fixed three report-MRI participants, only `238` has a no-report archive.
Archive presence is not task/run alignment or an independent measurement
bridge. It does not yet support a validated cross-study E/R scale or a new
multi-family P08 fit. The next technical route is to finish these derivatives,
audit additional no-report run/event coverage and disjoint calibration
participants, then test whether common E/R and neural feature units can be
established without target-outcome fitting. If not, retain `not_estimable`.
