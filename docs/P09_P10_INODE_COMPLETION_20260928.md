# P09/P10 technical completion and study-owned inode reduction

This is an operational recovery of the non-preregistered masked-fMRI lane. It
does not change model candidates, participants, contrasts, seeds, the 1,000
replicate IDs, or the conditional bootstrap rule. The original P09/P10 failures
and outputs remain available at their existing paths. No result direction is a
continuation gate.

## Verified state, 28 September 2026

- At 19:15 UTC the personal scratch quota reported approximately 994K of 1M
  files and 11 TB of 20 TB. This total includes the owner's other projects.
- A read-only compute-node census at approximately 19:51 UTC counted 303,821
  entries under this project's personal scratch directory. Its largest groups
  were `fresh-20260916/data/raw` (123,888),
  `fresh-20260916/analysis/masked-neural` (104,930), and the three protected
  current environments (28,473). The entry census does not deduplicate hard
  links and is not a substitute for the quota service.
- A targeted compute-node census counted 86,162 entries in the historical
  `analysis/masked-neural/PREPROCESS/21450700-3/work` tree. There was no
  corresponding `archives/mri-work/21450700-3` directory.
- At 19:59 UTC, `sacct` showed exact job 21450700 (`fc-recover-mri-3`)
  `FAILED`, exit 1:0, terminal since 20 September. Its attempt and provenance
  each reported `PREPROCESS`/`FAILED` from source `5c3cb879...`; the work
  directory's mtime was 20 September. The live scheduler census showed no
  Cognition and Consciousness study job. Raw input and retained derivatives
  are outside the proposed archive target.
- Of the 113 original structural P09 redraws, 112 have successful recorded
  attempts. Replicate 914 under job 21943233 failed with `Errno 122` while
  writing `result.json`; its status remains stale `RUNNING`. Dependent P10
  21943235 failed before making a report. The original P10 21842472 and all
  original 1,000 P09 attempts remain unchanged.

## Bounded execution graph

1. On a scheduled compute node, verify the exact old MRI job is terminal
   `FAILED`, the matching receipt and provenance are identical, and no other
   study job uses the root. The archive helper accepts only this numeric MRI
   attempt's `work` path. It inventories 86,162 entries, copies them into an
   uncompressed tar, verifies every payload SHA-256 and the whole tar, then
   retires only duplicate `work` members. The raw tree, retained derivatives,
   status/provenance and logs are untouched. Interrupted or failed packing is
   preserved for explicit reconciliation; no automatic overwrite occurs.
2. Only after a successful archive job, run a short dispatcher in a compute
   allocation. It checks the live personal quota reserve, all 112 surviving
   structural redraws, the exact quota-failure log, the original 1,000-ID
   graph and model-code compatibility. It submits a fresh P09 attempt for
   replicate 914 using the unchanged `42b52abb...` retry source and seed.
3. The dispatcher submits a new P10 job dependent on the new P09 attempt. Its
   input graph keeps the 887 originally scored draws and 112 successful first
   redraws at their original hash-verified paths, substituting only the new
   attempt path for ID 914. P10 reports coverage for all 1,000 IDs; an interval
   is conditional on at least three distinct participant groups per resampled
   family. It is **not** an unconditional or validated five-participant
   population-coverage interval. If the technical retry fails again, P10 must
   record the missing result rather than silently treating the analysis as
   complete.

The archive and dispatcher submission receipts follow. Post-archive quota,
the resulting P09/P10 job IDs, and final coverage/results require later
scheduler and output checks; submission is not completion.

## Submission receipt, 28 September 2026

GitHub commit `5d9655d7817bbf43ba4641fd447ab61879fac047` was installed as a
hash-verified source-only release under the personal study root; the installer
verified 313 source files. The cluster-side P09/P10 dry run verified 112
successful first redraws, identified only replicate 914 for a technical retry,
and observed 4,000 free personal-scratch files before consolidation. The new
archive and dispatcher batch files were LF-normalized into their operations
directories, checked with `bash -n`, and accepted by Slurm's test mode; the
source release itself was not edited.

Slurm accepted archive job **21980380** and dispatcher job **21980382** with
`afterok:21980380`. Both were pending at submission. The archive attempt is
bounded to `21450700-3/work`; the dispatcher will submit the new P09 and P10
jobs only after successful archive retirement and a fresh personal-quota check.
Their eventual IDs and outcomes are not yet known. The historical failure,
original derivatives, and original P09/P10 records remain untouched.

### First archive job stopped at its quiescence guard

Job 21980380 ran ten scoped Linux tests successfully, then refused to begin
packing because its conservative live-job census saw the dependent, still-pending
dispatcher 21980382. It failed at 20:10:04 UTC **before creating an archive or
removing any work files**. Slurm canceled 21980382 because its `afterok`
dependency failed. Both job logs and receipts are preserved. The follow-up
release permits only the exact recorded dispatcher while Slurm independently
confirms it is `PENDING` with `afterok` on the current archive job; every other
study consumer still blocks retirement. Tests cover a wrong dependency and a
running dispatcher. New scheduler IDs require separate submission receipts.
