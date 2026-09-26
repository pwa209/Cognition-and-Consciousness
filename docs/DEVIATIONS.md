# Analysis and implementation deviations

This ledger is part of the transparent non-preregistered record. Add entries chronologically; never rewrite an old entry to make a later choice appear prospective.

## 2026-08-30 — Initial implementation status

- **Source:** proposal dated 2026-08-30.
- **Change:** removed registration, preregistration, hidden lockbox, one-time confirmatory-run, and scientific gate language.
- **Reason:** explicit owner instruction. The study is a transparent non-preregistered secondary analysis.
- **Consequence:** configurations remain versioned and all changes/results are retained, but no claim of prospective registration is made and data are never deliberately hidden from the owner.

## 2026-08-30 — Server execution model

- **Source expectation:** Slurm, 5 TB fast scratch, containerized execution.
- **Observed:** H100 host with 256 logical CPUs and ~1 TiB RAM; no Slurm; Docker client exists but the user cannot access the daemon; `/data1` has ~2.3 TB free, NAS ~9.6 TB.
- **Change:** use NAS-first raw storage, bounded staging, Python virtual environments, `tmux`, file locks, logs, and atomic markers.
- **Consequence:** same scientific workflow, different scheduler/storage implementation.

## 2026-08-30 — Dataset access reality

- **Change:** COGITATE is represented as `WAITING_ACCESS`; DREAM is handled per constituent access state.
- **Reason:** COGITATE requires a user-created account and acceptance of terms; DREAM combines open and restricted packages.
- **Consequence:** public-family acquisition proceeds; unavailable families remain explicit and may enter later without replacing or suppressing earlier results.

## 2026-08-30 — Acquisition-only server deployment

- **Owner instruction:** after scripts are written, do not deploy anything except data acquisition.
- **Change:** use a commit-pinned sparse release containing only acquisition modules, configuration,
  and P01/P02 runners. Keep P03-P10 source in GitHub/local storage only.
- **Consequence:** the full roadmap and analysis implementation remain reproducible but are neither
  deployed nor queued until the owner explicitly expands server authorization.

## 2026-09-10 — Scientific review corrections (non-preregistered)

- **Basis:** owner requested scientific-nature review and script revisions; no participant
  outcomes analyzed. Full assessment: `docs/SCIENTIFIC_REVIEW_2026-09-10.md`.
- **Changes:** replace test-selected comparator with configured paired contrasts; use
  actual equal-family weighting; require independent train/test identities in canonical
  v2; aggregate by group; calibrate scoring variance on held-out training groups; keep
  unavailable models explicit; fix constant-column/intercept handling; use joint
  condition shuffling and group-level influence; report design aliases.
- **Scope correction:** mark the existing architectures as operational prototypes,
  the score as marginal Gaussian nats/pair rather than joint ELPD, and LOFO as not
  implemented. M5 is not a guaranteed ceiling. Unknown uncertainty is never fabricated.
- **Affected outputs:** canonical score, synthesis, robustness and paper-source tables.
  v1 canonical files need real source identities and rescoring, not guessed IDs.
  Prior outputs remain historical and must not be mixed with v2/specification hashes.
- **Preserved:** E/A/R and four separate K constructs, negative crossnobis values,
  all candidate IDs, no scientific gates, non-preregistered status, acquisition-only
  server authorization. Nothing was deployed by this review.

## 2026-09-10 — Follow-up fitted models and measurement implementation

- **Owner instruction:** fix the remaining identified scientific/implementation gaps.
- **Changes:** add a separate versioned generative-pattern likelihood and learned
  M0–M5 parameters; nested source-only LOFO; hierarchical ordinal-probit external
  report calibration; common/context-specific threshold checks and MNAR sensitivity;
  full nested subject-bootstrap refitting; independent stress generators; explicit
  multiplicity/equivalence utilities; verified masked-event adapter; BIDS timing and
  one-sided PSD corrections.
- **Rationale:** replace fixed-proxy and missing-method gaps with explicit executable
  models while preserving a truthful distinction between code tests and scientific
  validation. Operational E is report-liability probability, not a universal measure
  or ground truth. M5 remains an empirical within-family benchmark, not a ceiling.
- **Affected outputs:** new `measurement`, `patterns`, `stress` artifacts; new
  harmonized masked events; any newly regenerated spectral features. Previous RDM
  scores and historical outputs remain distinct and unchanged.
- **Calibration restriction:** new pattern v1 accepts independent external calibration
  only. It refuses all-subject empirical designs; within-neural-subject cross-fitting
  and a fully joint behavioral/neural measurement model are not silently claimed.
- **Remaining limits:** detailed in `docs/IMPLEMENTATION_FOLLOWUP_2026-09-10.md`.
  Raw-to-feature validation, shared anchors, complete simulation/inference calibration
  and production restart/concurrency remain outstanding. Unfavorable results continue.
- **Server:** read-only schema checks only; no analysis deployment or queue changes.

## 2026-09-16 — Fresh Compute Canada execution

- **Owner instruction:** build a fresh Rorqual study using personal 20 TB storage;
  separately authorized ready analysis phases as well as acquisition/environment tests.
- **Operational change:** isolated fresh personal-scratch root, native SSH password/MFA,
  quota-aware single-worker downloads and Slurm CPU jobs. University state unchanged.
- **P05 scheduling:** split each original 200-replicate plan into independent jobs.
  Original seed = 260830 + original replicate ID; every scenario retained. Each shard
  result has local replicate zero, with original identity in wrapper provenance.
  No estimand, model, penalty, scenario, chain length or success-based selection changes.
- **Affected artifacts:** separate fresh manifests/ledgers, environments, qualification
  evidence and P05 shards. A completed shard is not a completed 200-replicate campaign;
  original-identity aggregation and completeness checks are required before summaries.
- **Preserved:** non-preregistered status, distinct constructs, no scientific gates,
  access controls and explicit missing empirical adapters/calibration evidence.

- **Cluster qualification repair:** job 21169188 exposed login-only hostname
  validation on CPU node rc32623. Add observed compute-node naming plus Rorqual
  Slurm identity checks, and immutable per-release manifests for source-only repairs.
  Acquisition continues on its original source; failed qualification records remain.

- **First eligible empirical preparation:** after all 146 WM files completed, add
  scoped P03/P04 Slurm wrappers around the existing validator and WM harmonizer.
  Explicitly stop affected preparation on non-null ZIP CRC test results (previously
  recorded without enforcement). No raw archive extraction or downloaded code execution.
  Preserve PAS as observed ordinal evidence and all original grouping identities.

- **2026-09-16 acquisition-source repairs:** add dataset-scoped SHA256E OpenNeuro
  retrieval without relaxing snapshot/count/byte checks; treat DREAM v6's 22 rows
  as 20 sets plus amendment history; resolve explicit Figshare versions and the
  public FreiData v1 record. Add an owner-authorized private COGITATE catalog with
  modality/format/size/ETag validation. The mislabeled raw-MEEG link and private
  DREAM set 8 remain explicit access/source holds. No analysis labels change.
  Isolate repair locks, manifests, ledgers and provenance from the active campaign.
  See `ACQUISITION_REPAIRS_20260916.md` for commands and identity boundaries.

- **2026-09-17 acquisition recovery:** retry transient personal-quota service
  failures without writing under unknown quota; exhausted retries stop new transfers
  as a capacity hold. Resume DREAM/COGITATE with frozen manifests and partials.
  Add BMVP original-ledger recovery guarded by both campaign locks after verifying
  the old process is absent. No integrity criteria or scientific rules are weakened.
  See `ACQUISITION_RECOVERY_20260917.md`.

- **2026-09-18 transfer/digest separation:** full-sized ETag-pinned partials are
  source-checked by HEAD before scheduled hashing and atomic promotion. Hashing
  files >=256 MiB moves to one allocated compute CPU; Internet transfers stay on
  the network-enabled login surface after a compute-node connectivity probe failed.
  Preserve file identity, quota controls, all partials and original manifests.
  Termination causes for previous workers remain unknown; do not label this an
  established root-cause fix. See `ACQUISITION_HASH_RECOVERY_20260918.md`.

- **2026-09-19 empirical preparation:** owner instructed implementation and submission
  of technically ready empirical phases. Add a six-family P03 runner binding each
  source to the completed original or repaired acquisition manifest and per-file
  SHA-256 receipts, plus an immutable-attempt P04 wrapper for the existing masked
  fMRI adapter. All data remain in personal scratch. ZIP central-directory safety
  and bounded metadata inspection are distinct from full decompression/CRC and
  scientific preprocessing validation. No source label becomes a ground-truth E
  value; no favorable result is needed to continue. Reconcile the stale global
  `pattern_evaluation.deployment` string with the already authorized Compute Canada
  scope; university restrictions remain unchanged. Affected outputs: new P03/P04
  artifacts only, not existing simulations or acquired bytes.
  Source inspection also verified COGITATE Exp1 BIDS fMRI's seven-column event schema,
  944 event tables and 118 participants. Add its observed-event adapter, preserving
  all stimulus/nonstimulus rows without assigning E or button timestamps. Record
  MEEG (501 event files/100 participants) and iEEG (38/38) inventory counts only;
  their distinct trigger streams are not parsed by the fMRI adapter. Add safe TAR
  metadata census for BMVP; RAR remains explicitly unparsed.
  Qualification 21409777 retained a filesystem-sensitive mutation-test failure
  (177 passed, one failed): a same-size rewrite had no distinguishable mtime in
  that run. Extend the before/after identity tuple with ctime and inode, and make
  the concurrent-rewrite test use a guaranteed size change. The separate test of
  same-size corruption with restored mtime still verifies SHA-256 rejection. This
  is not a guarantee against a writer mutating bytes after verification; production
  raw inputs must remain quiescent. Preserve failed qualification and job receipts.
  P03 awakening job 21409961 then exposed a raw-versus-analysis cohort-count
  distinction: the pinned 1.0.0 manifest has 21 subject roots and participants.tsv
  has 21 rows (20 upstream excluded=False, one excluded=True). Add an explicit
  expected_raw_participants=21 while preserving expected_participants=20. Validate
  all 21 raw subjects; do not discard the upstream flagged subject or infer its
  eligibility from a count. The failed count-check attempt remains preserved.

- **2026-09-19 downstream execution layer:** add personal-scratch P06 prepared-pattern
  assembly with fixed 0.1 independent-residual covariance ridge, P07/P08 generative
  wrappers, 1,000 P09 within-family subject-bootstrap shards (concurrency two), and
  P10 lossless candidate tables/coverage. Replicate RNG is SeedSequence([260830,index])
  rather than the historical monolithic bootstrap stream, ensuring array-order
  independence. No empirical model results were inspected in choosing these settings.
  This does not complete raw preprocessing, calibration resampling, dataset-specific
  robustness, simultaneous inference or equivalence testing. Require hash-bound
  empirical bundles before dispatch, and do not queue mock empirical jobs if absent.
  Preserve all unavailable/numerically failed candidate rows and all missing bootstrap
  replicates. Also repair paired_pattern_summary to require identical scored dimensions,
  as well as subjects and weights, before model comparison. Earlier paired artifacts
  were not rewritten. See DOWNSTREAM_EXECUTION_20260919.md for exact scope/contracts.
  A subsequent live audit found masked P04 21409960 failed on the literal visibility
  token `missing data`. Census across 380 source event files found 8,235 such rows,
  alongside the three recognized visibility levels and 760 n/a rows. Normalize only
  this verified literal to unknown experience/report availability and no ordinal
  value, retaining the row and original source token. Never equate it with E=0 or
  silently omit it. Preserve the failed attempt; a new qualified release is needed
  before a retry. This is a source-missingness repair, not outcome-based selection.
  Allow explicitly named earlier same-run P03 evidence for a newer P04 adapter only
  after checking producer release authorization, all producer source hashes, unchanged
  family acquisition configuration, same family/manifest identity and all P03 output
  hashes. Default remains same-release. Record both producer and consumer releases;
  do not falsify the old marker or rehash 159 GB solely because an event parser changed.

- **2026-09-19 masked MRI implementation:** add real raw-MRI fMRIPrep and disjoint
  ordinal-report calibration jobs. Reserve two of seven participants by a fixed
  seed/ID SHA-256 rule, before fitting reports or neural outcomes; all sessions stay
  together. Remaining five participants are evaluation-only. This is an explicit
  non-preregistered design revision, not a lockbox. Collapse volume-repeated event
  metadata into trials, retaining shortened runs (12,087 represented trials total),
  missing reports, and missing probe durations. Upstream code identifies probe=99
  as parse failure; use a fixed zero placeholder plus missingness indicator, never
  99 frames as dose. Current predictors do not identify E separately from S.
  Upstream event generation subtracts ten TRs; raw timing alignment remains unverified
  and blocks only task-feature construction, not raw preprocessing. Installed module
  label 25.1.1 actually reports fMRIPrep 25.1.3; pin/check the actual version. Use all
  seven subjects for raw preprocessing, technical pilot then remaining-subject array;
  no scientific outcome controls dependencies. See MASKED_NEURAL_EXECUTION_20260919.md.
  This does not complete neural residual/feature calibration, dataset-general raw
  integration, common anchors, or empirical P06–P10 input bundles.

- **2026-09-19 calibration computational extension:** the first empirical masked
  report posterior (job 21417198) completed but had maximum rank/folded split R-hat
  2.51947 and minimum bulk ESS 4.79452. Preserve it; do not interpret its success
  marker as calibrated inference. Add one fixed larger run of the identical model,
  prior, cohort and predictors: four chains, 20,000 warmup and 10,000 retained draws
  per chain. This responds to Monte Carlo diagnostics, not scientific model scores;
  no neural evaluation rows are opened and MRI jobs continue independently. Keep
  diagnostics even if warnings remain; longer sampling is not guaranteed to resolve
  convergence or identifiability. The derived full analysis configuration is private,
  hashed and tied to the tracked extension plan. No original posterior is replaced.

- **2026-09-19 same-model sampler repair:** the longer Gibbs run 21417467 remained
  unconverged. ArviZ independently confirmed worst R-hat 1.2876434610 and minimum
  bulk ESS 11.45541, isolating the upper report threshold as the principal problem.
  Add PyMC NUTS using the exact marginalized three-category ordered-probit
  likelihood and prior-equivalent noncentered effects. Preserve priors, anchor,
  fixed predictors, missingness, two/five calibration/evaluation allocation and
  every historical posterior. Fix four chains with 4,000 warmup/4,000 retained
  draws, seed 260830, target_accept 0.95 before the new fit. Record parameter-wise
  diagnostics, divergences, tail ESS and BFMI; no scientific result controls
  execution. Synthetic density/gradient and quadrature tests qualify computation,
  not the study's hypothesis. See REPORT_SAMPLER_REPAIR_20260919.md. Numerical
  convergence alone does not resolve calibration sample size or construct validity.
  Initial NUTS qualification 21420706 passed 218 implementation tests and scalar
  quadrature, but its hierarchical synthetic fixture had 26 divergences (minimum
  bulk/tail ESS 391.69/273.55); its SUCCESS did not establish reliable sampling.
  Preserve it and empirical attempt 21420707. Change only sampling coordinates to
  centered effects and target_accept to 0.99, with 2,000 warmup/retained synthetic
  draws per chain. Verify equivalent joint densities and gradients for both
  parameterizations. Require clean synthetic numerical diagnostics before the new
  empirical attempt, retaining failed qualification artifacts. The synthetic
  threshold interval's failure to cover truth is reported and is not a gate or
  basis for revision; one fixture is not a coverage study. Centered release `8e8f837`
  passed 219 server tests and clean synthetic diagnostics (qualification 21421581).
  Empirical job 21421582 then completed with maximum R-hat 1.000616, minimum
  bulk/tail ESS 12374.73/8186.17 and zero divergences; all numerical flags clear.
  This resolves the observed sampling problem, not broader scientific limitations.

- **2026-09-20 file-count recovery:** preserve all completed outputs and historical
  failures while repairing the personal quota parser for its `->` warning marker.
  Cancel the quota-stalled MRI array 21417200, consolidate only quiescent work and
  regenerable cache/test files into verified archives, and queue original-code,
  original-seed retries. MRI concurrency changes from two to one with periodic
  quota checks and per-participant work archiving. This is storage/runtime repair,
  not a change in scientific specification or an outcome gate. The 45 failed
  pattern replicates are selected by the exact quota-parser exception, not scores.
  Completed MRI pilot and converged calibration are retained without repetition.
  See INODE_RECOVERY_20260920.md and conf/inode_recovery_plan.yaml for scope,
  provenance, reconstruction and restart safeguards.

- **2026-09-20 additional inode consolidation:** the owner requested a significant
  further reduction. Add lossless archiving of seven terminal, unconsumed older
  qualification environments (43,953 entries), protecting the three runtimes used
  by current work. Keep original source releases, package inventories, logs, all
  raw data and completed derivatives directly readable. Reconstruct old environments
  at their original paths when needed. Current MRI archive/retry jobs are unchanged.
  No scientific specification, seed, participant partition or outcome is altered.
  See FILE_COUNT_REDUCTION_20260920.md for targets and consumer/restore safeguards.

- **2026-09-21 MRI plotting compatibility:** after two additional MRI participants
  completed, job 21450700 failed in diagnostic plotting because fMRIPrep's custom
  warning handler does not accept Python 3.12's `skip_file_prefixes` keyword. Add an
  exact-checksum, read-only single-file container bind accepting that keyword while
  retaining the original warning logging body. Test the baseline failure and fixed
  plotting/warnings in the original container and a forkserver worker before four
  unfinished participant retries. Preserve completed subjects, original source,
  settings, cohort partition, calibration, old failed work and all failure records.
  Fresh retries recompute from raw inputs; no incomplete outputs are promoted.
  This technical repair is not a scientific change or outcome gate. See
  MRI_WARNING_REPAIR_20260921.md and conf/mri_warning_recovery_plan.yaml.

- **2026-09-21 initial masked-fMRI empirical lane:** owner approved proceeding with
  the existing five evaluation/two calibration subjects and P08 not applicable
  until a compatible second family exists. Add pinned original behavioural timing,
  same-space Schaefer400 parcel extraction, independent AR(1)/feature-noise calibration,
  and a producer-bound P06–P10 dependency graph. Extend the generative input contract
  to participant-specific construct/sensory/design-noise matrices without changing
  architecture definitions. The initial cortical association analysis is explicitly
  narrower than the full whole-brain/multifamily study; report-liability E is not
  ground-truth experience, and exact-image/category confounding remains. Fixed
  implementation settings, approximations, leakage boundaries and affected outputs
  are documented in MASKED_EMPIRICAL_LANE_20260921.md and conf/masked_feature_plan.yaml.
  No observed model score informed these choices; no unfavorable result stops later
  phases. Missing/invalid inputs produce technical failure records, not null findings.

  The source audit additionally identified lossy first-digit stimulus-frame decoding
  in the publisher helper, 20-character image-name truncation, 18 unreconciled timing
  runs and 50 sub-03 acquisition/crosswalk problems (including a 13-volume scan).
  Correct full physical frame counts and rerun the same reserved-subject report
  model/priors; preserve the original posterior. Resolve only unique exact truncated
  prefixes. Quarantine 68 unverified neural runs with explicit failure ledgers while
  retaining 312 verified runs and all seven participants. No neural outcome was read
  to make these source-integrity decisions. The incomplete run coverage and unresolved
  crosswalks are limitations, not operational completion of the full study.

  The 1,000-task P09 array was rejected by the scheduler; accounting/live-queue
  reconciliation found no submitted job. Pack the same 1,000 global replicate IDs
  into 50 tasks of 20, retaining concurrency two, the qualified analysis source,
  every seed and every failure record. This changes scheduling only, not inference.

- **2026-09-22 transient quota service and inode recovery:** MRI job 21500396 was
  terminated while actively processing sub-05 because three personal-quota service
  calls timed out. Later fresh counters showed capacity remained; this is a technical
  service failure, not scientific evidence. Preserve the failed attempt and archive
  its loose work tree with checksums before a fresh retry. Require a fresh 180K-file
  start margin, then permit a bounded 30-minute stale-reading grace only for the
  already-running MRI monitor, charging 50 GB and 10K files per failed refresh and
  enforcing stricter 1 TB/100K reserves. Acquisition remains fail-closed. Retry
  sub-05/06/07 serially and archive each successful work tree before the next.
  Requeue the unchanged extraction/noise/bundle/P06-P10 graph, retaining all 1,000
  bootstrap identities and adding a successful-bundle prerequisite to P10. See
  MRI_QUOTA_RECOVERY_20260922.md and conf/mri_quota_recovery_plan.yaml.

- **2026-09-24 masked-fMRI calibration design-rank repair:** Job 21654493 failed
  because one retained sub-07 recognition run has 29 volumes and nuisance rank 29;
  it provides zero residual degrees of freedom. Its previous projected-task rank
  appeared as one from floating-point remnants, producing a misleading df of -1.
  Compute df from the joint nuisance/task design rank. Exclude calibration runs
  with fewer than the existing 10 residual df **before using their BOLD values
  in noise fitting**, preserve a per-run design exclusion ledger, and require
  both reserved calibration participants to retain estimable runs. The known
  affected run is `sub-07_ses-05_task-recog_run-1.npz`; the other 91 retained
  calibration runs remain eligible. This is a technical estimability rule, not
  outcome selection or a scientific gate. The repaired AR(1)/residual covariance
  and all dependent BUNDLE/P06-P10 outputs need a new immutable source release;
  prior successful extraction ZIPs are reused only by an explicit same-run,
  manifest-verified producer release. The prior failure and all excluded-run
  records remain preserved. See conf/masked_noise_recovery_20260924.yaml.

- **2026-09-25 P09 scheduling acceleration and P08 compatibility audit:** The
  existing 50-task × 20-replicate P09 array (`21744877`) was already running
  with a concurrency cap of two four-core tasks. After confirming no failures,
  ownership, account, resource request and remaining tasks, raise only
  `ArrayTaskThrottle` to 25 (at most 100 allocated CPUs). Keep all replicate
  IDs, seeds, statistical specifications, output files and failure receipts
  unchanged. This is an execution-time change, not outcome-dependent selection.
  The scheduler subsequently ran 25 tasks concurrently. The separate BMVP
  audit found usable report/no-report trial schemas but no verified BMVP neural
  bundle or externally justified E/R-and-feature anchor shared with masked
  fMRI. Do not submit a nominal multi-family P08 by relabeling these scales;
  preserve the existing single-family `not_applicable` receipt and define a
  restricted E–R estimand only after independent calibration. These are
  technical estimability conditions, never scientific result gates. See
  docs/P08_BMVP_COMPATIBILITY_AUDIT_20260925.md.

- **2026-09-25 BMVP schema pilot (not P04 activation):** After inspecting the
  official archives and published task design, add a parser pilot that
  distinguishes calibration from task rows and the task-relevant from the
  task-irrelevant stimulus within a no-report archive. Preserve original
  source-clock values without claiming scan alignment or latent E labels.
  Run two representative archives on a one-core compute allocation without
  extraction; both passed with a hashed, immutable source release and
  personal-scratch SUCCESS/provenance receipts. Do not add BMVP to
  `harmonization_ready` or queue its neural/P08 phases until full schema,
  timing, and independent anchor checks are done. This change addresses
  measurement validity, not scientific result direction; see the P08 audit.

- **2026-09-25 BMVP MRI conversion pilot (not P08 activation):** The owner
  elected to continue with already acquired BMVP material and not request
  additional data by email. Read-only compute-node inventory showed that the
  report-MRI exemplar's lone NIfTI is 3D structural, while functional DICOM
  series are present; no-report has one archive with explicit 4D BOLD NIfTIs.
  Add a bounded, fixed-series DICOM conversion pilot on personal scratch with
  temporary extraction and hashed provenance. Conversion checks geometry only;
  do not treat it as event synchronization, neural preprocessing, disjoint
  calibration, or a common E/R anchor. The new restricted E–R transfer remains
  exploratory and not yet estimable. No scientific result controls this work.

- **2026-09-25 BMVP report-MRI timing pilot:** The original report archive's
  PsychoPy log was found to contain 720 scanner triggers for each of the four
  720-volume task series, with first task trials about ten seconds after the
  first trigger. Add a fixed, versioned behavioral-log/CSV alignment check and
  DICOM inter-run clock cross-check. This validates a pilot run origin only,
  not the complete BMVP neural bundle or any cross-family E/R anchor. Retain
  calibration trains and the isolated trigger as distinct, never as task runs.

- **2026-09-25 BMVP fixed report-cohort conversion extension:** Following
  non-neural archive/log/CSV inventory, define 191/223/238 as the first three
  report-MRI pilot archives with complete 720-trigger task runs. The four 191
  conversions already exist; submit only the five 223 and four 238 DICOM
  series in two bounded Slurm lanes. The plan does not use P07/P08 scores or
  neural values to select subjects or runs. Conversion is not P04/P06/P08
  completion; no common E/R/feature anchor is claimed. See the P08 BMVP audit.

- **2026-09-25 restricted P08 compatibility contract:** Add a separately
  labeled exploratory E–R transfer branch for a future two-family campaign.
  Before model fitting it checks empirical provenance, an independently
  reviewed measurement-bridge declaration, joint E/R design support, and
  identical condition/feature/partition/sensory axes and units. Failed checks
  retain all M0–M5 rows as `not_estimable`, never substitute scores or affect
  the existing masked-only P08 receipt. This is a technical anti-mislabeling
  check, not evidence that a declared bridge is scientifically valid and not
  a result-based stopping rule. BMVP preprocessing and bridge validation are
  still required before a real cross-family fit can be queued.

- **2026-09-26 P09 quota-service recovery:** Six packed bootstrap array tasks
  stopped on personal-quota-report timeouts, after 25 total replicate SUCCESS
  receipts; their model results did not determine retries. Lower new-start
  concurrency from 25 to 8 to reduce quota-service pressure. Preserve the
  original attempts and all 1,000 replicate IDs/seeds. Retry only the 95
  technically missing IDs at four concurrent Slurm tasks using the unchanged
  analysis source, then submit a new P10 with all original/retry paths. The
  original P10 remains a provenance record. No scientific gate or selective
  result exclusion is introduced. See REMOTE_STATE_AND_RECOVERY_20260926.md.
