# Empirical implementation and deployment — 19 September 2026

This is a non-preregistered secondary analysis. Technical validity, not favorable
scientific outcomes, controls whether an affected command is executable.

## Implemented in this revision

- `pipeline/empirical.py`: bind complete acquisition manifests to same-manifest
  per-file SHA-256 receipts; check file counts, byte counts, identity, traversal and
  stable size/mtime; recompute SHA-256 in allocated compute jobs.
- Inventory all manifest files and ZIP members without extracting recordings or
  executing archive code. Reject unsafe paths/types, duplicate destinations and
  encrypted entries. Bounded table/JSON schema inspection preserves schema errors.
- `scripts/alliance/empirical_phase.py`: immutable P03/P04 attempts, atomic failure/
  success markers, provenance/configuration/input/output hashes, dry-run and
  same-manifest/same-source predecessor checks.
- P04 uses the existing source-verified masked-fMRI adapter. Categorical visibility
  remains ordinal report evidence; missing reports remain unknown; raw response-time
  units are not guessed.
- A new COGITATE Exp1 fMRI adapter reads event tables directly from the preserved
  BIDS ZIP (944 files, 118 participants, source-inspected 19 September). It validates
  the exact seven-column schema, task/stimulus levels and timing; keeps all event
  roles and original fields; and never equates a correct rejection with a button
  event or assigns E=1. MEEG and iEEG use different trigger schemas and remain separate.
- `empirical_phase.sbatch` uses only the study's qualified environment, source release,
  personal scratch/cache/temp and a CPU allocation. It cannot submit P06–P10.
- `submit_empirical.py` creates a new isolated qualification job, six P03 jobs in
  two bounded I/O lanes, and masked/COGITATE-fMRI P04 successors. P04 depends only
  on its own P03 technical completion. An unrelated family's failure does not stop
  the other lane or later P03 jobs. Durable intent/receipt files prevent blind
  duplicate submissions after a lost SSH response.

P03 success means byte fixity and a completed source-schema census. It does **not**
mean every neural file has been parsed, all archive payload CRCs checked, preprocessing
validated, or report linkages certified. Scientific endpoints remain downstream.

## Phase mapping

| Phase | Implemented command / next dependency | Evidence required before submission |
|---|---|---|
| P03 | `empirical_phase.py --phase P03 --family FAMILY` | Complete exact acquisition manifest, personal quota, source/environment checks |
| P04 masked | Same runner with `--phase P04 --predecessor PATH` | Same-release/same-manifest P03 success; verified event schema/counts |
| P04 COGITATE fMRI | Same runner, `--family cogitate` | Same-release P03 success; 944 event files / 118 participants and source-specific schema |
| P04 other families | Source-specific adapters after census | Explicit event/report/recording keys and units, participant/site/run or patient grouping |
| P05 | Existing 200-replicate report and pattern suites | Already executing; null/poor recovery retained |
| P06 | Raw-to-pattern producers still incomplete | Declared preprocessing, physical timing, disjoint calibration, independent partitions, noise design |
| P07 | Existing `patterns --mode within` engine | Validated empirical NPZ input contract; all M0–M5 retained, including unavailable/failure rows |
| P08 | Existing `patterns --mode lofo` engine | Independent common anchors and source support, not merely two available datasets |
| P09 | Existing sensitivity/bootstrap/testing components; workflow incomplete | Independent-unit exchangeability, justified margins and calibrated uncertainty |
| P10 | Empirical reporting integration incomplete | Real-data scores with source hashes; never use simulation outcomes as empirical findings |

## Restart and interpretation

New Slurm job IDs create new attempts; existing attempts cannot be overwritten.
P03 retains a flushed file-by-file verification ledger. Initial retry rehashes from
the beginning rather than trusting a partially successful attempt. SIGTERM writes
FAILED; SIGKILL cannot run cleanup, so scheduler accounting must reconcile a stale
RUNNING marker. Inspect `progress.json` and Slurm logs/accounting, not marker alone.

Private DREAM set 8 and the separate mislinked raw-MEEG archive stay explicit holds.
The acquired MEEG BIDS bundle is not removed. Do not interpret unavailable sources
or invalid calibration as null scientific effects.

Targeted empirical-input, lifecycle, submission and COGITATE parser tests: 32 passed locally.
Deployment IDs and final full-suite evidence will be appended after live verification.

## Deployment receipt

Source release `34fce0750e2771e7e679d3d77cc2f129b3d92b0d` was installed under the
existing personal fresh run, with 182 source files verified. Archive SHA-256:
`a7e45d639b3e534e46f2cc81a5985ebd662c74cb3613197dacdf194586fd65c9`.
No acquisition release or original source snapshot was overwritten.

Local full suite: **178 passed** (56.49 s); targeted Ruff and Bash syntax passed.
The warning is from the deliberately duplicated ZIP-path test fixture.

| Submitted job | Purpose | Dependency |
|---|---|---|
| 21409777 | Isolated environment and full tests | None |
| 21409778 | P03 masked fMRI | Qualification success |
| 21409779 | P04 masked fMRI | 21409778 success |
| 21409781 | P03 awakening EEG | Qualification success |
| 21409782 | P03 Volition fMRI | Qualification success; 21409778 terminal |
| 21409783 | P03 COGITATE | Qualification success; 21409781 terminal |
| 21409784 | P04 COGITATE fMRI only | 21409783 success |
| 21409785 | P03 public DREAM | Qualification success; 21409782 terminal |
| 21409786 | P03 BMVP | Qualification success; 21409783 terminal |

At 08:40 UTC, qualification was RUNNING and all eight preparation jobs were pending
on their declared dependencies. These are submission receipts, not completion claims.
Personal quota before deployment: 6,398 GB / 20 TB and 624K / 1M files. Shared-project
quota warnings are unrelated; these jobs use no shared-project data/output paths.

Private scheduler receipts/logs:
`operations/empirical-deployment/34fce0750e2771e7e679d3d77cc2f129b3d92b0d/`.
Stage artifacts: `analysis/PHASE/FAMILY/JOB_ID/`. None are committed to Git.

**Qualification correction:** 21409777 finished FAILED with 177 passed and one
filesystem-sensitive test failure. Its concurrent-mutation fixture happened to
replace a file with an equal-length string and relied on an mtime change that was
not observable in that run. Add ctime/inode to change checks and give this fixture
a guaranteed different length. Same-size corruption with restored mtime remains a
separate SHA-256 test. Initial dependent jobs must be cancelled/replaced explicitly;
they did not start empirical work. Records of the failed attempt remain intact.

### Replacement campaign

Release `0f4314128bf66a58e98aa8e21f703cb5665edd26` installed with 182 files verified;
archive SHA-256 `d13ce80009a2f357b27ee335ee9c4c3b50338e98bc99884ab0987da6c5ea6990`.
After the repair, the local full suite again passed: **178 tests**, 70.60 s.
Scheduler accounting confirmed all eight old preparation jobs CANCELLED before any
empirical work; qualification 21409777 remains FAILED in the retained history.

| Replacement job | Purpose |
|---|---|
| 21409958 | Qualification |
| 21409959 | P03 masked fMRI |
| 21409960 | P04 masked fMRI |
| 21409961 | P03 awakening EEG |
| 21409962 | P03 Volition fMRI |
| 21409963 | P03 COGITATE |
| 21409964 | P04 COGITATE fMRI |
| 21409965 | P03 DREAM |
| 21409966 | P03 BMVP |

Same two-lane technical dependency design; receipts are under the replacement
release's `operations/empirical-deployment/COMMIT/` directory. No P06–P10 jobs exist
in this campaign. Follow-up work remains source-specific neural preprocessing and
measurement/calibration integration, not just waiting for downloads.

Qualification **21409958 completed successfully: 178 remote tests passed** in
57.52 s. Masked-fMRI and COGITATE P03 started on compute nodes. Awakening P03
21409961 stopped at the raw participant-count assertion before hashing: the release
contains 21 subject roots and its participant table contains 21 rows, comprising
20 upstream included and one upstream excluded flag. The earlier configured 20
was not the raw inventory count. Add `expected_raw_participants=21`, retain 20 as
the separately recorded analysis-cohort expectation, and keep all raw subjects.
No scientific subject exclusion is introduced by this repair.
