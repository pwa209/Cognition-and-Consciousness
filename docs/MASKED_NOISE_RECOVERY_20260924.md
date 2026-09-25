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

## Execution checkpoint, 25 September 2026

P07 job `21744875` completed cleanly in 3:39:38, using 14:26:02 aggregate CPU
on four cores. All 30 intended rows (five evaluation participants × M0–M5)
were scored with finite held-out values; all 120 recorded outer-fit optimizer
starts converged. This establishes operational completeness, not a preferred
scientific model. Conditional design-draw uncertainty and five independent
evaluation participants remain interpretive limits; no P07 rerun is indicated
by this diagnostic audit.

At 08:09 UTC, the owner-authorized packed P09 array `21744877` had its
simultaneous-task throttle raised from 2 to 25 without changing its 50 tasks,
20 replicates per task, seeds, configuration or prior outputs. Each task uses
four CPUs. By 08:25 UTC, 25 tasks were running (100 allocated CPUs), with
remaining array work held by the task limit; P10 `21744878` remained pending
on its dependency. The scheduler may change live occupancy. The remote
operational receipt is retained under this run's `operations/noise-recovery/`
directory as `p09-throttle-20260925.json`; data and logs remain on personal
scratch, not the shared `/project` allocation.
At 08:39 UTC, `diskusage_report` showed personal scratch at 12 TB/20 TB
and 823K/1,000K files; the packed P09 campaign remains inside the current
file-count limit. This is a live quota snapshot, not a reservation for later
BMVP extraction.
At 08:51 UTC, the 25 running P09 batch receipts collectively recorded 42 of
the 1,000 original replicate IDs complete, with no failed batch receipts.
P10 remained dependency-pending. These counts are a snapshot, not a prediction
of completion time.

The BMVP compatibility audit is recorded separately in
[P08_BMVP_COMPATIBILITY_AUDIT_20260925.md](P08_BMVP_COMPATIBILITY_AUDIT_20260925.md).
