# BMVP-to-masked-fMRI P08 compatibility audit (25 September 2026)

This is a transparent, non-preregistered secondary analysis. This audit concerns
technical estimability, not whether any model has a favorable result. It does not
replace or retrospectively alter the single-family P08 receipt (`21744876`).

## Evidence inspected

- The BMVP acquisition ledger reports 168/168 official archives complete on the
  owner's personal Rorqual scratch. P03 job `21409966` passed byte/schema
  inventory with no holds, but explicitly records
  `neural_preprocessing_validated: false` and no full archive CRC.
- A read-only, one-core scheduled inspection of the P03 inventory found 225
  report-context and 364 no-report-context CSV files. Report CSVs have nine
  distinct column signatures; no-report CSVs have six. Both include stimulus,
  trial, timing, and some perception-response fields. The inspected report MRI
  archive contains a trial CSV and NIfTI; the inspected no-report archive
  contains six trial CSVs, NIfTI, DICOM and eye/EEG files. These are **schema
  observations**, not validated event-to-BOLD correspondences.
- A second scheduled, read-only pilot of the original trial CSVs found that the
  representative report MRI CSV has 400 calibration and 128 task rows with
  nonempty task onset times. A representative no-report archive has both
  calibration and task rows, and its task rows still contain perception
  keypress/answer fields as well as `Task Relevant`, `First Stimulus`, and
  separate center/quadrant face fields. Therefore the archive label is **not**
  a trial-level absence-of-report label. The published paradigm calls the
  task-irrelevant location no-report while participants can still respond to
  the task-relevant location. Any adapter must infer report availability at
  the stimulus/location level, never from the archive name alone. See
  [Kronemer et al., Nature Communications (2022)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9707162/).
- `conf/construct_maps/masked_content_fmri.yaml` defines ordinal visibility
  report evidence for E, living/nonliving information for K_content, and
  choice/button R. `conf/construct_maps/bmvp.yaml` defines binary report or
  cross-fitted eye/pupil evidence for E, report context/response R, and
  stimulus presence/contrast S. It does not define K_content.
- `conf/masked_neural_plan.yaml` uses the anchor
  `masked_ordinal_report_probit_v1_not_universal_E`; no externally calibrated
  BMVP-to-masked anchor or common neural feature/condition scale exists.
- The implemented `generative_pattern_v1` leave-one-family-out evaluator
  requires at least two families, external common anchors, source support for
  target constructs and interactions, and three independent groups per family.
  M5's free condition covariance is deliberately nontransferable.

## Estimand decision

| Proposed transfer | Current disposition | Reason |
|---|---|---|
| Masked E–K_content–R to/from BMVP | Not estimable | BMVP has no K_content measurement; the E links and neural feature units are not common. |
| Restricted E–R transfer | Candidate only, not yet estimable | Binary report/eye probability and ordinal visibility liability are not automatically one scale; R also mixes task context and button events. |
| Within-BMVP E/R contrasts | Technically promising separate lane | Requires event/run linkage, eye-calibration independence and neural preprocessing. This is not cross-family validation. |

Merely setting the two `anchor_id` strings equal would not provide a measurement
link. Restricting the construct set to E/R is a new, explicitly versioned
estimand; it does not make the original masked E–K_content comparison transferable.
No result direction or low ceiling will determine whether this work proceeds.

## Implementation route and queue boundary

1. **P04 BMVP adapter:** parse official report/no-report CSV variants without
   treating an unrequested/missing response as E=0. Verify run identity and
   onset/volume alignment against the original MRI and eye recordings. Include
   parser fixtures, expected-count checks and archive path-traversal tests.
   Separate calibration from task trials and task-relevant from task-irrelevant
   stimulus locations; preserve simultaneous center/quadrant events explicitly.
2. **P05 pilot / P06 neural bundle:** select only a declared MRI-compatible
   cohort and fixed, cross-study-comparable ROIs, time basis and condition
   definition; perform preprocessing and estimate nuisance/noise exclusively
   from training or disjoint calibration participants. Keep archives packed to
   protect the personal scratch file count. Record every excluded run and reason.
3. **Independent measurement bridge:** validate, outside target neural outcomes,
   a common E measurement link across ordinal visibility and BMVP binary/ocular
   proxies, including report-context sensitivity; likewise define R and feature
   units. If no independent bridge is defensible, record the E–R transfer as
   not estimable and retain within-family analyses. Do not invent a universal E.
4. **New P08 campaign:** only after both verified bundles and source-only anchor
   checks exist, run a new multi-family release. Retain all M0–M5 rows, with
   unsupported constructs/architectures explicitly `not_estimable`; preserve
   the existing single-family receipt. P09/P10 for the masked lane continue
   independently of this compatibility work.

**Current boundary:** BMVP P03 is complete; BMVP P04/P05/P06, independent
cross-family calibration, and the new multi-family P08 are **not queued**. The
existing P08 result remains correctly `not_applicable` for the one-family lane.
This is an honest technical dependency, not a scientific gate.

## First parser pilot deployed, 25 September 2026

Immutable source release `4516b7e3426b783480c7e46983dd0328d3508d08`
adds `factorcon.pipeline.bmvp_csv`, a read-only TAR/CSV pilot that validates
archive member safety and expected CSV counts, retains the source clock as
unverified, counts calibration separately, and emits separate center/quadrant
stimulus candidates. A response attaches only to the task-relevant stimulus;
the task-irrelevant candidate is `not_requested`, never E=0. Focused parser
tests passed 10/10, and the full local suite passed 275 tests (five skipped for
documented environment limitations).

Compute-node pilot `21790807` completed successfully without extraction:

| Original archive | Trial CSVs | Calibration rows | Task rows | Stimulus candidates | Task-irrelevant/unrequested |
|---|---:|---:|---:|---:|---:|
| `191_RP_MRI.tar` | 1 | 400 | 128 | 128 | 0 |
| `238_NRP.tar` | 6 | 1,600 | 480 | 960 | 480 |

The per-attempt SUCCESS/provenance receipt is stored only on personal scratch
under `operations/bmvp-csv-pilot/<release>/`. This validates two representative
archive schemas; it does **not** establish correct trial-to-BOLD timing, prove
eye calibration, qualify all archive variants, activate P04, make a neural
bundle, or justify P08 transfer. The active masked-fMRI release and jobs were
not changed by installing this separate pilot source.

## Alternative-family search

The [Hatamimajoumerd et al. visual-masking fMRI study](https://par.nsf.gov/servlets/purl/10353317)
is scientifically closer to masked-content fMRI: it used animal/object stimuli
and report/no-report conditions. Its article lists public ROI-level results and
code, but says additional material for reanalysis is available from the lead
contact upon request; it does not establish a downloadable, verified raw
participant-level neural bundle for this project. It is a possible future
access inquiry, not a substitute for the missing BMVP calibration or a queued
second-family P08 run.

## MRI-cohort census and restricted-transfer decision, 25 September 2026

Read-only inspections ran as one-core Slurm jobs on Rorqual. In the verified
P03 inventory, all 37 report-MRI archives have DICOM and one NIfTI each, but
none has a NIfTI named as functional BOLD. The inspected report-MRI NIfTI is
3D (256 × 256 × 176), hence structural rather than an fMRI time series. Of
67 no-report archives, 65 contain DICOM, nine contain NIfTI, and only one
archive contains explicitly named BOLD NIfTI runs. Its six such runs have
600/700 volumes at 1 s TR. This is an imaging-file census, not a qualified
cohort: conversion, run/event synchronization, preprocessing, and disjoint
calibration remain. The personal `/scratch` quota readout showed 11.62 TB and
824,826 files used; any conversion must keep temporary DICOM material bounded
and avoid exploding the file count.

The owner asked to pursue **both** routes. Route A is a separately labeled,
exploratory E–R transfer between masked fMRI and BMVP, conditional on a
validated common report/visibility measurement link and fixed neural feature
units. It must not be presented as the original E–K_content–R P08. Route B
seeks an independent masking/content fMRI family with raw participant-level
neural data and defensible links for E, K_content, R and S. The original P08
remains not estimable with BMVP alone, irrespective of Route A's outcome.

Initial external-source audit: [Hatamimajoumerd et al. (2022)](https://doi.org/10.1016/j.cub.2022.07.068)
has an attractive animal/object masking and report/no-report design, but the
paper offers ROI-level/code resources and states that additional reanalysis
material is available from its lead contact upon request. A public raw neural
bundle has not been verified. [Stein et al. (2021)](https://doi.org/10.1371/journal.pbio.3001241)
has face/house masking, trialwise category and subjective visibility responses,
and 43 fMRI participants, but its OSF availability statement establishes
quantitative observations underlying published figures, not a verified raw
participant-level fMRI release. The openly available [OIID](https://www.nature.com/articles/s41597-025-05414-w)
is an occlusion/recognition study; its 10–90% physical occlusion conditions
cannot automatically be interpreted as E reports. None of these has been
promoted to a second P08 family or downloaded on this evidence alone.

The owner subsequently chose to continue with already acquired BMVP data and
not to request new data by email. No author was contacted. The external-source
search is retained as context, not an active acquisition route.

## Predeclared single-series conversion pilot

The report-MRI exemplar has DICOM series with 3, 60, 270, 270, 720, 720,
720 and 720 files (from the P03 member inventory). The fixed first pilot is
`report/191_RP_MRI.tar`, series `191_RP_MRI_0006` (720 DICOM files).
`scripts/alliance/bmvp_mri_pilot.py` validates the entire TAR member list,
extracts only those 720 members into a temporary directory **inside personal
scratch**, invokes the Alliance-provided `dcm2niix` on a scheduled compute
node, checks for a single four-dimensional NIfTI with a time unit in seconds,
hashes persistent conversion outputs, and deletes the temporary DICOM copies.
Original archives are untouched. The output is a conversion-only pilot:
event-to-scan alignment, usable task runs, preprocessing, participant split,
and cross-family E/R/feature anchors remain unverified. A conversion SUCCESS
must never be promoted to P04/P06/P08 success.

## Independent report-MRI clock pilot, 25 September 2026

The fixed report exemplar's PsychoPy `.log` contains exactly four long
`Keypress: 5` trigger trains of 720 entries, plus two earlier 270-entry
calibration trains and one isolated late trigger. The four long trains have
starts at 1386.8777, 2158.5457, 2919.6478 and 3687.3724 seconds on the
behavioral clock. Each task block has 32 trials; its first trial is 10.0173,
10.0173, 10.0172 and 10.0166 seconds after the corresponding train start.
The converted DICOM series `0006`–`0009` each have 720 volumes at 1 s TR.
Their scanner start-time intervals track the behavioral trigger-train intervals
within about 0.3 s. This supports a fixed run-order/event-origin mapping
without selecting on BOLD outcomes. The companion `logs_anon.txt` is empty;
the PsychoPy log, not that file, supplies the triggers.

`factorcon.pipeline.bmvp_timing` and `scripts/alliance/bmvp_timing_pilot.py`
make these non-neural checks executable with explicit run/trial/trigger counts,
cadence and DICOM interval tolerances, plus a personal-scratch status/provenance
receipt. This is a **report-exemplar timing pilot only**. It does not verify
slice timing, motion/QC, all BMVP subjects, independent E measurement, common
feature units, or multi-family P08. No missing report is coded as E=0.

Immutable Rorqual release `05ebff9e6d4f62e1466d60c0262edbc98a03982a`
ran the check as one-core Slurm job `21818154`. Its personal-scratch receipt is
`SUCCESS`, with four runs and scanner-minus-trigger inter-run residuals
−0.058, −0.135 and +0.278 seconds. The work used the owner's scratch
(`12/20 TB`, `830k/1,000k` files reported before submission), not `/project`.

A separate read-only census of `601_NRP.tar` found two MRI behavioral logs:
the center-relevant session has five 700-trigger task trains and the
quadrant-relevant session has four; each also has a 600-trigger calibration
train. Their task CSVs have 24 trials per task block. A second compute-node
count found exactly **one** trial onset outside a task scan: center-relevant
block 3, 707.916 seconds after its first trigger despite a 700-volume,
1-second train. The other 215 of 216 no-report task-trial onsets fall within
their respective trains. That one onset is a technical exception to resolve
or mark unavailable for neural analysis; it is not evidence about E and must
not be silently shifted or discarded because of a model result. No no-report
run has yet been promoted to a P04/P06 bundle.

## Fixed three-participant report conversion extension

A scheduled, read-only scan of the BMVP P03 inventory found 37 report-MRI TAR
archives. Thirteen contain at least three filename-pattern-matched long DICOM
series; 24 do not match that specific DICOM filename/count check and are not
declared unusable. Among the first three report-MRI archives with complete
task logs/CSVs and long scanner-trigger trains, `191` has four 720-trigger
task runs, `223` has five and `238` has four. Every task block has 32 task
trials; first onsets follow the run's first trigger by approximately ten
seconds. These are design/timing checks, not outcome-based cohort selection.

The versioned `conf/bmvp_report_cohort_pilot.yaml` fixes the five 223 and four
238 720-DICOM series for bounded conversion, supplementing the four already
converted 191 series. `submit_bmvp_report_cohort.py` limits active conversions
to two 2-CPU Slurm lanes, uses durable per-series submission receipts, personal
scratch quota reserves and immutable source, and refuses unreconciled duplicate
attempts. DICOM conversion alone is not neural preprocessing or multi-family
transfer readiness. The original P08 remains not applicable; the exploratory
E–R route requires a new, separately labeled campaign and independent anchors.

## Restricted P08 execution contract

The downstream runner now treats a two-family, E/R-only input as the separately
labeled `exploratory_report_evidence_E_R` estimand. It requires a matching
independently reviewed bridge declaration plus compatible design and neural
axes before calling the leave-one-family-out fitter. Otherwise it writes
all twelve family-by-M0–M5 rows as `not_estimable` with explicit reasons,
without invented scores. The single-family masked receipt is unchanged.
Matching metadata is necessary but cannot itself establish cross-study
measurement equivalence; an independent review of the actual report and
feature calibration remains a human scientific task. No such bridge or BMVP
P06 bundle exists yet, so a multi-family P08 fit is not currently queueable.
