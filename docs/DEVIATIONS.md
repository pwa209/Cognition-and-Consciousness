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
