# Phase-mapped implementation roadmap

This roadmap is operational, not a scientific stop/go tree. Every phase proceeds when its inputs are technically available; unfavorable or null results never block later work. Access-controlled families can remain `WAITING_ACCESS` while public families continue.

| Phase | Purpose | Main command | Canonical output | Compute / storage | Completion evidence |
|---|---|---|---|---|---|
| P00 | Verify host identity, roots, storage, tools, licenses, and repository commit | `scripts/server/run_phase.sh P00` | `run_state/P00/` | minutes; negligible | `SUCCESS.json` plus preflight report |
| P01 | Resolve immutable source metadata and per-file inventories | `factorcon manifest resolve` | `manifests/generated/` | minutes-hours; MB | source IDs, versions, URLs, sizes, licenses, access states, hashes where supplied |
| P02 | Acquire all eligible public raw data directly to NAS | `factorcon acquire --eligible-only` | `data/raw/<family>/<snapshot>/` | ~1.75 TB plus open DREAM subsets; network/I/O bound | per-file size/checksum ledger and atomic family marker |
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

The host has no Slurm. `scripts/server/queue_phase.sh` launches one named `tmux` session per phase. `run_phase.sh` obtains an exclusive lock, writes logs under the canonical NAS root, records `RUNNING.json`, and atomically replaces it with `SUCCESS.json` or `FAILED.json`. P02 uses a maximum of two high-I/O family jobs and four file transfers per family. Compute phases use explicit thread budgets so 256 CPUs and 1 TiB RAM are not oversubscribed.

P02 may overlap P04/P05 for a completed family; the global roadmap does not wait for access-controlled COGITATE. P07-P10 consume every technically valid family available at run time and record unavailable families rather than replacing them post hoc.

