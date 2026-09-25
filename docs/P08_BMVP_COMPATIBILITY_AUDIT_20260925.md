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

## Alternative-family search

The [Hatamimajoumerd et al. visual-masking fMRI study](https://par.nsf.gov/servlets/purl/10353317)
is scientifically closer to masked-content fMRI: it used animal/object stimuli
and report/no-report conditions. Its article lists public ROI-level results and
code, but says additional material for reanalysis is available from the lead
contact upon request; it does not establish a downloadable, verified raw
participant-level neural bundle for this project. It is a possible future
access inquiry, not a substitute for the missing BMVP calibration or a queued
second-family P08 run.
