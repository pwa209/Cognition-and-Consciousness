# Phase-mapped implementation roadmap

> **Transient-quota recovery follow-up, 2026-09-23:** the 61,755-entry failed MRI
> work tree was checksum-archived and retired successfully, reducing personal scratch
> use to 791K/1M files. Qualification 21571206 and archive 21571207 completed. MRI
> 21571208 then failed before preprocessing because its runtime looked for the new
> qualification receipt in `operations/inode-recovery` while the dispatcher had
> written it in `operations/mri-quota-recovery`; dependent jobs 21571209–21571220
> were cancelled automatically. This was a four-second operational path error, not
> a data, quota, fMRIPrep or scientific-result failure. The repair now passes the
> same-dispatch qualification job explicitly and retains the legacy receipt fallback;
> the exact regression and full local suite pass. Immutable release `cabee37` is
> installed and fresh jobs 21654485–21654499 are queued. Qualification 21654485
> completed with 268 server tests and both real-container smokes; verified-archive
> job 21654486 is running, with every later stage dependency-held. See
> [repair and inode controls](MRI_QUOTA_RECOVERY_20260922.md).

> **Transient-quota recovery deployed, 2026-09-22:** sub-05 MRI job 21500396
> stopped when the personal quota-reporting service timed out three times, not on
> a measured capacity exceedance. Its serial successors and P06-P09 were cancelled;
> P10 failed immediately because its bundle was absent. A tested repair now requires
> fresh start evidence, uses bounded and pessimistically charged stale readings only
> during active MRI, archives the failed work tree before retry, archives every
> successful MRI work tree serially, and prevents P10 from starting without a
> successful bundle. Release `f4de98e` passed 267 server tests and real-container
> smokes. The initial recovery graph used jobs 21571207–21571220; its final state and
> follow-up are recorded above. See
> [repair and inode controls](MRI_QUOTA_RECOVERY_20260922.md).

> **Initial empirical lane implementation, 2026-09-21:** owner approved masked fMRI
> first, with five evaluation/two calibration subjects and explicit P08 not applicable.
> Analysis release `6c92cf2` passed 260 server tests and actual NIfTI runtime checks.
> At 07:09 UTC, corrected report calibration and sub-02/sub-03 extraction completed;
> sub-01 extraction is running. Remaining extractions, independent neural
> calibration, bundle assembly and P06–P08 are queued behind their technical inputs.
> P09 `21502684` is queued as 50 tasks covering all 1,000 unchanged replicates;
> P10 `21502685` is queued after P07/P08/P09. All initial-lane stages are submitted,
> not completed. This first cortical lane uses 312 verified
> runs; 68 have explicit unresolved source-integrity exclusions, not null results.
> See [scope, commands, dependencies and limits](MASKED_EMPIRICAL_LANE_20260921.md).

> **Repair deployed, 2026-09-21 05:39 UTC:** release `5a62fa4` passed 250 server
> tests plus real-container baseline/fixed-warning regressions, including a
> forkserver worker. Qualification 21500394 succeeded; MRI retry 21500395 is
> running, followed by queued 21500396–21500398. Original science settings,
> three completed participants and report calibration are preserved. The existing
> P05 simulations continue; the hourly local monitor remains paused. See
> [verified repair and exact queue](MRI_WARNING_REPAIR_20260921.md).

> **MRI runtime repair, 2026-09-21 05:24 UTC:** three of seven masked-MRI
> participants are complete. The fourth failed in diagnostic plotting with a
> warning-handler compatibility error; its three successors were canceled.
> P05 reports are 200/200 complete; patterns are 188/200 with one running and 11
> queued. The September 20 cleanup completed, consolidating 252,681 entries; two
> further successful MRI work trees are also archived. At that check a runtime
> repair was needed for the four unfinished participants (deployed above). Empirical neural
> feature integration and M0–M5 comparisons remain incomplete. See
> [repair scope, validation and deployment receipts](MRI_WARNING_REPAIR_20260921.md).

> **Additional consolidation, 2026-09-20 07:26 UTC:** job 21451328 successfully
> combined 43,953 entries from seven inactive software environments into verified,
> recoverable archives, protecting current MRI/P05/PyMC runtimes. MRI work archiving
> continues separately. Combined target is approximately 253K fewer project entries
> (~59% of the measured project count), not yet a completed reduction. Raw data,
> completed outputs and scientific specifications remain unchanged. See
> [file-count reduction and verified completion receipt](FILE_COUNT_REDUCTION_20260920.md).

> **Storage recovery, 2026-09-20 07:07 UTC:** completed MRI pilot 21417199 and
> converged report calibration 21421582 are retained. The quota-stalled MRI array
> 21417200 is canceled, preserving failed attempts. Verified work-archive job
> 21450695 is running; server qualification 21450696, original-code retries for
> 45 quota-parser-failed P05 patterns (21450697), and six serial MRI retries
> (21450698–21450704, excluding 21450702) are queued behind technical dependencies.
> Every successful MRI retry archives its work before the next participant starts.
> This restores operational prerequisites, not empirical P06–P10 findings. See
> [storage repair, exact job IDs and preservation safeguards](INODE_RECOVERY_20260920.md).

> **Report-sampler repair, 2026-09-19:** longer Gibbs run 21417467 finished but remains
> unconverged. Independent ArviZ diagnostics confirm the upper-threshold bottleneck.
> A same-probability-model marginal NUTS backend and synthetic qualification workflow
> were deployed as release `09cf7b2`, but its empirical job 21420707 retained 216
> divergences despite improved R-hat/ESS. The equivalent centered revision `8e8f837`
> passed all 219 server tests and clean synthetic diagnostics in qualification
> 21421581. Empirical calibration **21421582 completed**: maximum R-hat 1.000616,
> minimum bulk/tail ESS 12,374.73/8,186.17, zero divergences, all numerical flags clear.
> This resolves the observed report-calibration sampling warnings and repairs
> a P04/P07 measurement prerequisite, not neural-noise calibration or the full P06–P10
> inputs. MRI preprocessing continues independently. See
> [sampler equivalence, diagnostics and limitations](REPORT_SAMPLER_REPAIR_20260919.md).

> **Masked raw-MRI update, 2026-09-19 15:29 UTC:** release `5c3cb87` passed 207 local
> tests and is deployed. Actual masked-fMRI preprocessing and independent report
> calibration are now submitted: qualification 21417196, PREPARE 21417197,
> CALIBRATE 21417198, MRI pilot 21417199 and remaining six-subject array 21417200.
> This advances the P04 measurement/P06 raw-preprocessing prerequisites; it does
> not complete independent neural-noise calibration, task-feature assembly or
> empirical P06–P10 model inputs. Other families are not declared preprocessed.
> See [exact scope, source issues and phase mapping](MASKED_NEURAL_EXECUTION_20260919.md).
> At 15:38 UTC remote qualification passed 207 tests, preparation and initial report
> fitting completed, and actual MRI processing was running. The first posterior
> has severe convergence warnings; fixed longer-sampling job 21417467 is submitted
> behind qualification 21417466 using release `41da85c` (208 local tests passed).

> **Compute Canada update, 2026-09-19:** empirical P03 integrity/schema checks are
> deployed for six families; masked-fMRI and COGITATE-fMRI P04 harmonizers are queued
> behind their own technical predecessors. The initial repaired preparation release
> passed 179 tests; the later downstream/missing-report repair passed **194** remotely.
> See [commands, job IDs, restart behavior and remaining dependencies](EMPIRICAL_IMPLEMENTATION_20260919.md).
> P06–P10 now have a separate tested generative execution/dispatch layer; actual
> empirical execution remains blocked by raw preprocessing and independent calibration.
> The P06 builder starts from prepared neural summaries, not recordings; P09 covers
> subject bootstrap only. See [downstream contracts and remaining work](DOWNSTREAM_EXECUTION_20260919.md).
> Masked P04 retry **21410794 completed**: 192,089 records from 380 event files and
> seven participants, retaining all 8,235 explicit missing-report rows as unknown.

> **Follow-up, 2026-09-10:** phase entries describe intended deliverables, not universal
> operational completion. A separate generative-pattern/measurement engine now provides
> source-only LOFO and refitted subject bootstrap. Raw-to-feature integration, shared
> empirical anchors and calibrated simultaneous inference remain unfinished. See
> [the updated implementation ledger](IMPLEMENTATION_FOLLOWUP_2026-09-10.md) and
> [local command contracts](PATTERN_AND_MEASUREMENT_COMMANDS.md). Existing Snakemake
> targets have not been silently redirected from historical RDM scores to pattern scores.

This roadmap is operational, not a scientific stop/go tree. Every phase proceeds when its inputs are technically available; unfavorable or null results never block later work. Access-controlled families can remain `WAITING_ACCESS` while public families continue.

## Server authorization

**Compute Canada update (2026-09-16):** fresh personal-scratch acquisition,
environment/test jobs and ready analysis phases are now owner-authorized on Rorqual.
See [the separate fresh-run roadmap](ALLIANCE_FRESH_RUN.md). The following historical
university-server workflow and its acquisition-only restriction remain unchanged.

Only acquisition is authorized for deployment. P01 (source resolution) and P02 (direct-to-NAS
download) may be deployed and queued after the owner confirms the three server roots. P03-P10 are
fully mapped and remain in GitHub/local source only; they must not be deployed or queued without a
new explicit owner instruction. P00 is limited to the identity/storage checks embedded in the
acquisition runner.

| Phase | Purpose | Main command | Canonical output | Compute / storage | Completion evidence |
|---|---|---|---|---|---|
| P00 | Verify host identity, roots, storage, tools, licenses, and repository commit | `scripts/server/run_phase.sh P00` | `run_state/P00/` | minutes; negligible | `SUCCESS.json` plus preflight report |
| P01 | Resolve immutable source metadata and per-file inventories | `factorcon manifest resolve` | `manifests/generated/` | minutes-hours; MB | source IDs, versions, URLs, sizes, licenses, access states, hashes where supplied |
| P02 | Acquire all eligible public raw data directly to NAS | `factorcon acquire --eligible-only` | `data/raw/<family>/<snapshot>/` | ~3.44 TB plus open DREAM subsets; network/I/O bound | per-file size/checksum ledger and atomic family marker |
| P03 | Validate archives, BIDS structures, expected counts, and metadata identity | Snakemake target `validate_data` | `reports/generated/data_validation/` | CPU-light, I/O-heavy | errors/warnings report; invalid inputs quarantined, never deleted |
| P04 | Normalize behavior/events to the common schema and generate deterministic grouped splits | Snakemake target `harmonize` | `data/derived/common_schema/` | hours-days | schema, count, rank, and split-isolation reports |
| P05 | Run synthetic recovery and one-subject/one-site pilot execution for every available family | Snakemake target `pilot` | `reports/generated/pilot/` | days; controlled sample | runtime/memory benchmarks, numerical tests, all model outputs retained |
| P06 | Full modality-specific preprocessing and canonical feature extraction | Snakemake target `features` | fast/restart work roots and NAS derivatives | weeks; high CPU/I/O | provenance sidecars, QC tables, feature inventories |
| P07 | Fit measurement models and M0-M5 with identical nested grouped splits | Snakemake target `models` | `results/intermediates/model_scores/` | days-weeks; CPU and H100 only for secondary network | fold-level scores, effective complexity, calibration, convergence |
| P08 | Leave-one-family-out transfer, hierarchical synthesis, subspaces, temporal generalization | Snakemake target `synthesis` | `results/intermediates/synthesis/` | days-weeks | complete family matrix including null/negative/low-ceiling outcomes |
| P09 | Robustness, missingness, influence, and specification-curve analyses | Snakemake target `robustness` | `results/intermediates/robustness/` | days | branch-complete ledger, no branch suppressed |
| P10 | Rebuild figures, source tables, manuscript claims, and reproducibility bundle | `make reproduce` | `results/paper/`, `reports/generated/reproducibility/` | hours | every plotted value maps to a row, config hash, code commit, and source manifest |

## Dataset-to-phase map

| Family | Acquisition state | P04 adapter | P06 primary feature path | Architectural edge |
|---|---|---|---|---|
| Multisite working memory | public OSF | trial CSV / raw archive parser | behavioral latent measurement | E—K_memory |
| Masked-content fMRI | public OpenNeuro `ds003927` v1.0.3 | BIDS events | fMRI run-wise patterns, crossnobis | E—K_content |
| BMVP | public NITRC archives | report/no-report multimodal parser | eye-calibrated E; EEG/fMRI/depth EEG | E—R |
| COGITATE | owner account + terms required | BIDS modality adapters | fMRI/M-EEG/iEEG temporal and representational geometry | K_task—R—S |
| Propofol volition fMRI | public OpenNeuro `ds006623` v1.0.0 | BIDS events + force/dose | imagery templates, dose trajectories | A—K_volition—R |
| DREAM | mixed registry | per-package DREAM schema | within-stage pre-awakening EEG/MEG | E—A—R |
| Propofol awakening EEG | public OpenNeuro `ds005620` v1.0.0 | BIDS awakenings | spontaneous EEG primary, TMS-EEG secondary | E—A |

## Queue topology on this server

The host has no Slurm. For the currently authorized scope,
`scripts/server/queue_acquisition.sh` launches named `tmux` sessions for P01 and P02.
`run_acquisition.sh` verifies host/user/root identity, obtains an exclusive lock, writes logs under
the canonical NAS root, records `RUNNING.json`, and atomically replaces it with `SUCCESS.json` or
`FAILED.json`. The default batch is sequential by family and uses at most eight file transfers for
the 119,120-object propofol release, four elsewhere, and two for BMVP, avoiding uncontrolled
high-I/O concurrency.

No compute phase is currently deployed. If that authorization changes later, P04/P05 may overlap
P02 for completed families, and P07-P10 will consume every technically valid family available at
run time while recording unavailable families rather than replacing them post hoc.
