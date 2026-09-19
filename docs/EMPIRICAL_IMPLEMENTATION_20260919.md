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
