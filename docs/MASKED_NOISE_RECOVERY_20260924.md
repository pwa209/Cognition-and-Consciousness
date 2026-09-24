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

## Deployed checkpoint, 24 September 2026

Immutable analysis source `27ce5d1d4c565b5e5506fb4dce5e0843cd3b8dbe` was
installed in the existing personal-scratch fresh run; the source archive and
266 files passed SHA-256 verification. Slurm qualification `21744804` passed
270 tests plus the synthetic imaging-runtime smoke. The recovery dispatcher
recorded job IDs: NOISE `21744872`, BUNDLE `21744873`, P06 `21744874`, P07
`21744875`, P08 `21744876`, packed P09 array `21744877` (50 tasks × 20
replicates), and P10 `21744878`. At this checkpoint, NOISE, BUNDLE, P06, and
P08 have SUCCESS receipts; P07 and P09 are running, and P10 waits on their
terminal states. The NOISE ledger excludes only
`sub-07_ses-05_task-recog_run-1.npz` at design residual df 0. Scheduler
receipts and all detailed provenance are retained on personal scratch; no
participant-level data are committed here. This is an operational checkpoint,
not a scientific finding or a claim that the full multi-family study is done.
