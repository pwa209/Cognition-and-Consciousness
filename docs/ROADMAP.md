# Phase-mapped implementation roadmap

> **Report-sampler repair, 2026-09-19:** longer Gibbs run 21417467 finished but remains
> unconverged. Independent ArviZ diagnostics confirm the upper-threshold bottleneck.
> A same-probability-model marginal NUTS backend and synthetic qualification workflow
> are implemented; execution receipts will be recorded after submission. This repairs
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
