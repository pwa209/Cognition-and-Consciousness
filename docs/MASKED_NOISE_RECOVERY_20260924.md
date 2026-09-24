# Masked-fMRI calibration recovery (24 September 2026)

This is a non-preregistered secondary analysis. No result direction, null score,
or low ceiling blocks a later phase. The present repair concerns estimability only.

| Phase | Input boundary | Scheduled command | Completion evidence |
|---|---|---|---|
| Qualification | New immutable source; existing personal-scratch environment | `masked_lane.sbatch` with `FACTORCON_STAGE=QUALIFY` |  Full tests, imaging smoke, SUCCESS/provenance |
| NOISE | Two reserved subjects; verified prior extraction ZIPs | `masked_lane.sbatch` with `FACTORCON_STAGE=NOISE` | Design-exclusion ledger, independent AR/noise, hashed SUCCESS |
| BUNDLE | Five evaluation subjects, NOISE, fixed report posterior | `masked_lane.sbatch` with `FACTORCON_STAGE=BUNDLE` after NOISE | Five-group bundle, held-out integrity, hashed SUCCESS |
| P06 | BUNDLE | `masked_lane.sbatch` with `FACTORCON_STAGE=P06` | Grouped feature/prepared-pattern receipt |
| P07/P08 | P06/BUNDLE | Two Slurm jobs, 48 h each | All candidate scores; P08 records single-family non-applicability |
| P09 | P06/BUNDLE | 50 Slurm array tasks × 20 unchanged replicates, concurrency 2 | 1,000 seed/replicate receipts, including failures |
| P10 | BUNDLE and all P07/P08/P09 terminal states | `masked_lane.sbatch` with `FACTORCON_STAGE=P10` | Lossless candidate/coverage tables and reproducibility receipts |

The prior extraction and failed NOISE attempts remain immutable. The recovery
dispatch uses durable `submit_one` receipts so an uncertain `sbatch` call is not
blindly repeated. All outputs, caches, and scheduler logs stay beneath
`/scratch/pwa209/cognition-and-consciousness/fresh-20260916` on the personal 20 TB
allocation; nothing is staged to shared `/project`. Existing packed extraction
ZIPs and the packed P09 layout limit additional file count.

Interpretation remains the narrow masked-fMRI cortical association lane. This
retry does not restore timing-excluded runs or make P08 cross-family synthesis
applicable. Report-liability E is not ground-truth consciousness.
