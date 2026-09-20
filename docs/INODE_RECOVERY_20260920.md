# Personal-scratch file-count recovery — 20 September 2026

This is an operational repair in the non-preregistered secondary analysis. It does
not change hypotheses, model candidates, mappings, cohorts, seeds, analysis plans,
or scientific continuation rules. Null/unfavorable findings are not excluded.

## Observed failure and bounded intervention

Personal scratch reported 7,683 GB of 20 TB and approximately 998K of 1,000K files.
The quota warning inserts `->` into its human-readable row. The previous parser
rejected that format, accounting for all 45 failed pattern replicates (155–199).
MRI workers independently exhausted file-count allocation and raised Errno 122;
missing Nipype result pickles were consequences, not missing acquisition inputs.

Array 21417200 was canceled at 06:36:26 UTC after capturing scheduler state. Its
two running tasks and four pending tasks are terminal; historical markers and logs
remain unchanged. Completed MRI pilot 21417199 and report calibration 21421582
were not canceled or rerun.

The initial bootstrap consolidated 423 cache/test entries into a verified 8,130,560
byte tar; 72 zero-byte files from canceled work trees were recorded for exact-path
reconstruction. Because a new inode was denied, an existing regenerable pip-cache
inode carried the tar. Its prior bytes were saved in the tar and private local
receipt before reuse. Symlink-containing test trees were excluded. No participant
data, derivatives, scientific results, environments, licences or logs were removed.

Bootstrap archive (private personal scratch):
`operations/inode-bootstrap-20260920.tar`.
SHA-256: `872660310b1e2e3e2678be5350afbad8a253b849e32aefc9eec24a9eb055e017`.
These are recoverable consolidation operations, not deletion of unique research data.

## Recovery sequence

1. Verify exact source hashes, Rorqual ownership and terminal scheduler records.
   Run archive/quota lifecycle tests on the server using the existing study environment.
2. Consolidate only these quiescent `PREPROCESS/<attempt>/work` trees:
   `21417199-0` (318.97 GB), `21417200-1` (209.58 GB), and `21417200-2` (225.69 GB).
   Together their original census contained about 209K files/directories.
   Raw acquisitions, derivatives, attempt logs and status/provenance remain in place.
3. Each tree becomes one uncompressed tar plus manifest/status/provenance under
   `archives/mri-work/<attempt>`. This reduces file count, not payload bytes.
   Verify every member SHA-256, exact inventory, metadata, and whole-tar SHA before
   removing only the duplicate original work members. Preserve failed archives.
4. Run the complete test suite in the existing study PyMC environment, with all
   temporary files under personal scratch. No new environment is installed.
5. Retry exactly the 45 technical-failure pattern replicates with their original
   source `2d4e03e`, qualification environment 21169236, seeds and configurations.
   A runtime shim changes only the quota parser; the old release is not modified.
6. Retry six remaining MRI participants, sequentially, using original source
   `5c3cb879`, environment 21417196 and prepared inputs 21417197. Do not repeat the
   completed pilot or calibration. Require 180K free files at each start and retain
   50K files / 500 GB during processing, checking live quota every 60 seconds.
   On technical failure stop the child process group and preserve that attempt.
   After successful preprocessing, archive its work before the next participant.

Scheduler dependencies are technical input/storage dependencies, not scientific
gates. A failed archive, test or preprocessing job cannot silently unblock its
dependent job. New Slurm IDs preserve all original failures and completed results.

## Restart and restore rules

- Submission receipts are write-once and protected by a lock. Reconcile uncertain
  submission receipts against Slurm before any retry.
- Failed/incomplete packing is not overwritten; inspect it and select a new
  destination for another packing attempt. Original work remains intact.
- VERIFIED/RETIRING archive retirement can resume after rechecking tar/member hashes
  and remaining original identities. A completed retirement is idempotent.
- Never extract directly over a live work tree or into the data/derivative roots.
  To restore, choose an empty owner-approved scratch directory, validate the
  recorded inventory and link targets, extract there, and verify member checksums.
- Scratch is not a durable backup service. Combining files does not change its
  retention policy; long-term storage arrangements remain a separate owner decision.

## Scope still unfinished

This recovery does not produce neural feature/event-alignment validation,
independent neural-noise calibration, empirical P06 bundles, or primary M0–M5
findings. Those remain distinct from successful raw MRI preprocessing and report
calibration. Actual submission IDs and observed states are recorded below only
after receiving scheduler evidence.

Local validation before deployment: **238 passed, 4 skipped** (one Windows symlink
privilege test, three tests needing unavailable local ArviZ/PyMC), plus clean Ruff,
shell syntax and whitespace checks. Server qualification will exercise the full
suite with the existing PyMC/ArviZ environment; local skips are not counted as passes.
