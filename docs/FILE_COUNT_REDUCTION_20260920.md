# Significant file-count reduction without changing research inputs

## Scope

Owner requested additional consolidation on 20 September 2026. This is an
operational change, not a scientific specification change. Raw acquisitions,
completed derivatives, posterior draws, failure histories and source releases stay
at their existing paths. No participant information is committed to Git.

The personal allocation is shared with the owner's other projects; its total is
not this project's file count. Other projects' files and jobs are not modified.

## Measured targets

- Existing MRI-work consolidation: approximately **208,728 entries** remaining in
  three quiescent work trees, after the 72 zero-byte bootstrap removals. Job
  **21450695** was already processing these trees; it is not duplicated or canceled.
- Additional environment consolidation: **43,953 entries** in seven obsolete
  qualification environments (**6,279 each**), to seven verified archives.
- Combined target: approximately **252,681 loose entries**, replaced by a few dozen
  archive/manifest/status/provenance files. This is roughly a quarter of the
  personal one-million-entry limit, excluding the already-completed small bootstraps.

Actual net reduction must be checked after archives pass verification and original
duplicates are retired. Copies under construction do not count as completed cleanup.
Personal-quota counters can also change because other projects remain active.

## Protected runtimes and reproducibility

Keep `qualification-21169236` for original P05 simulation retries,
`qualification-21417196` for MRI, and `report-pymc-5.24.0-arviz-0.22.0-v1` for
calibration/qualification/recovery. The archive helper rejects these paths.
All active/queued study consumers are checked before and after each archive copy;
unknown consumers or references to a proposed target stop that cleanup.

The exact seven target names are in `conf/environment_archive_plan.yaml`. Their
qualification jobs must be terminal. Both successful and failed historical
environments are preserved; selection does not depend on scientific results.
Qualification status, logs and package inventories remain outside archived trees.

Environment archives preserve complete payloads, modes and interpreter/library
symlinks without following them. Each file and the whole tar are checksummed;
live source identities are rechecked before any loose copy is removed. Research
inputs/outputs cannot be archive targets. These are reversible consolidation
operations, not purges of unique information.

For an old result rerun, first restore the matching archived environment to its
**original absolute path**, after inspecting its manifest and verifying every
checksum. Do not activate it directly from a different extraction path: venv
scripts can contain absolute paths. Only restore into an absent, approved study
path; never overwrite an active environment. CVMFS links remain read-only software
references, not bundled interpreters. Scratch archives are not durable backups.

## Preventing recurrence

The queued MRI recovery runs one participant at a time, watches personal quota,
and consolidates each successful work tree before the next participant starts.
It reuses protected existing environments. Leave canonical BIDS/raw inputs and
completed derivatives directly readable by the current pipeline; converting those
to a new container format would require additional reader/integrity validation.

Commands: `scripts/alliance/archive_environments.sbatch` runs the versioned
`archive_environments.py`. Archives are under `archives/environments`, with
separate operational status/provenance under `operations/environment-consolidation`.
Packing and retirement have tested dry-run, checksum rejection, success, failure
and interrupted-retirement restart behavior; failed packing is never overwritten.
