# Initial masked-fMRI empirical lane

This is a transparent non-preregistered secondary analysis. On 2026-09-21 the owner
approved starting with masked fMRI, retaining the existing five evaluation and two
independent calibration participants, and recording P08 as not applicable until a
compatible second family is available. No scientific outcome gates are introduced.

## Scope and limits

This first lane is **cortical, within-family, report-associated neural geometry**.
It is not the complete whole-brain/multifamily primary study. It does not establish
causal separation of consciousness from stimulus strength, report, confidence or
content. E is the existing external report-liability predictor, not a ground-truth
experience label or a universally validated probability of consciousness. Its
condition means depend on duration/category composition; this limitation must
accompany every interpretation. No E=0 label is assigned to missing reports.

The existing report posterior and all completed MRI outputs are preserved. Reserved
subjects sub-02/sub-07 supply report and neural-noise calibration; sub-01/sub-03/
sub-04/sub-05/sub-06 enter participant-grouped neural evaluation. A, K_memory,
K_task and K_volition remain absent, not silently equated with other constructs.

## Fixed implementation choices

- Original PsychoPy CSVs are fetched from `nmningmei/unconfeats`, revision
  `5560619d791cd16f2b8b1a0432870a90df60afb9`. Each of 380 acquired runs maps to one
  Git-blob-verified CSV; the extra source CSV is listed, not silently substituted.
  Upstream bytes and MIT licence are kept in one tar on personal scratch.
- Reproduce the publisher's volume-row membership, labels and 4–7-second window
  from original image-onset times. Published event rows have ten fewer volumes
  than raw scans and are not image onsets. Original scanner-coordinate image times
  are used with each preprocessed image's explicit `StartTime` and TR.
- Same-space TemplateFlow MNI152NLin2009cAsym res-2 Schaefer400/7-network labels,
  revision `15d7c02160f79f5218d2545b4febebeecc11531d`, with annex SHA-256 verification.
  Nearest-neighbour label resampling reconciles grids only; no template-space
  substitution or smoothing. Parcel means retain unscaled fMRIPrep intensity.
- Six conditions: living/nonliving × three observed ordinal reports. Missing
  reports have separate category-specific nuisance events. Image exposures use
  impulses, not an assumed conversion of source frame counts into seconds.
- Canonical double-gamma HRF plus temporal derivative; motion24, first five retained
  aCompCor columns, 128-second DCT drift, intercept, and FD>0.5 mm/nonsteady-volume
  spikes. Runs with >20% censored volumes have explicit technical exclusion records.
  First-level contrasts are design-determined linear operators; no evaluation
  noise covariance or predictive scaling is fitted.
- Temporal AR(1) is estimated from reserved-subject residuals, excluding run
  boundaries, clipped to the declared stationary range [0,0.95]. Residuals corrected
  for fitted degrees of freedom calibrate feature covariance. This is a pooled
  AR(1) approximation, not proof of complete temporal independence.
- Conditions with no information remain zero-information until run aggregation;
  a rank-deficient partition is not assigned fabricated betas. Alternate numerically
  sorted runs form two fixed partitions. Coverage selection is mask geometry only:
  at least 80% of a parcel must be covered in every retained run, including calibration.
- Construct metadata and condition-noise matrices may differ by participant. The
  model now supports this explicitly and slices them together with participant folds.
  Posterior designs use 32 evenly spaced draws, preserving shared calibration
  parameters and independently seeded new-participant effects. These are fixed
  Monte Carlo draws, not a full posterior refit in each bootstrap replicate.
- All architectures include the same exact-image-frequency, duration, missingness
  and accuracy nuisance kernel. R is button-2 frequency; K_content is category.
  Exact-image controls do not causally disentangle category from physical images.
  Conditions are population summaries shared across partitions; residual partition
  composition differences remain a modeling approximation.

## Commands and dependency roadmap

All paths below are beneath the study's personal scratch run, never shared `/project`.
Source is a committed immutable release. All actual job IDs belong in the deployment
receipt, not inferred from these planned steps.

| Stage | Actual command implementation | Technical dependency |
| --- | --- | --- |
| Auxiliary inputs | `masked_lane_phase.py`, stage AUX | verified P03/PREPARE; pinned source/atlas and all-run timing audit |
| Neural extraction | same runner, EXTRACT, one job/participant | release qualification, AUX and that participant's MRI SUCCESS |
| Independent neural noise | same runner, NOISE | sub-02 and sub-07 extraction SUCCESS |
| Model input bundle | same runner, BUNDLE | noise calibration, all five evaluation extractions, converged report calibration |
| P06 | existing `downstream_phase.run_phase` via producer-bound wrapper | hash-verified real BUNDLE SUCCESS |
| P07 | nested participant-held-out M0–M5 | P06 SUCCESS |
| P08 | explicit single-family not-applicable record | P06 SUCCESS; not a transfer result |
| P09 | 1,000 nested subject bootstrap refits, concurrency two | P06 SUCCESS; failed/non-estimable draws retained |
| P10 | paired scores, intervals when supported, failure coverage | afterany P07/P08/P09 |

`submit_masked_lane.py` queues actual downstream commands before the future bundle
exists. The wrapper accepts that future campaign only from the exact submitted
BUNDLE job path, same source release, successful marker and matching artifact hashes.
There is no placeholder/synthetic campaign and no automatic selection of a favorable
input. Durable submission receipts prevent blind duplicate submissions.

Retries use new attempt/job IDs and preserve failures. A failure of a technical
predecessor requires repair/rebinding of affected descendants; it is not scientific
evidence against any architecture. First-level series are packed into one ZIP per
participant to limit file counts. Existing environments are reused; no new full
environment is created. Long-running stages have atomic status/provenance sidecars.

## Validation and remaining work

Local tests cover source parsing/path traversal/counts/missingness, numerical GLS,
participant-specific likelihood equivalence, calibration-cohort isolation, bundle
integrity, immutable attempts/failure/restart and dependency construction. Server
qualification additionally runs the full test suite in the protected study runtime
and a real-NIfTI parcel fixture inside the existing fMRIPrep image.

Remaining beyond this initial lane: subcortical/whole-brain primary representation,
compatible additional families and common calibration, fuller missingness/measurement
and temporal-noise sensitivity, direct low-level image descriptors, decoder-transfer
contrasts, justified equivalence margins and multiplicity policy. P09 is conditional
on fixed external calibration, conditions and families; P10 is evidence-table
generation, not a completed manuscript. None of these limitations is hidden by a
successful Slurm exit. The hourly local monitor remains paused.

Deployment receipt: pending live qualification/queue verification at authoring.
