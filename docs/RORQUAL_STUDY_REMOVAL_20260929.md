# Rorqual study-copy removal — 29 September 2026

The owner requested removal of this study from Rorqual to release storage and
file-count quota, then explicitly confirmed deletion of the entire study root,
including raw downloads and detailed analysis outputs, after an aggregate
results/provenance summary was saved in GitHub. The latter is commit `6447e09`
(`docs/EMPIRICAL_RESULTS_CHECKPOINT_20260929.md`). Raw recordings,
participant-level outputs and the per-draw bootstrap artifacts were **not**
backed up to GitHub; reacquisition and recomputation would be required to
recreate them.

The read-only inventory identified exactly one owned study scratch directory:
`/scratch/pwa209/cognition-and-consciousness`, containing only child
`fresh-20260916`. It found no matching study directories under the owner's
home, project or nearline roots. Three small historical inventory logs under
home and the final audit receipt/log remain outside the removed root.

The guarded removal procedure in
`scripts/alliance/remove_study_from_rorqual_20260929.py` (commit `feae90f`)
verified the literal root path, ownership, non-symlink identity, expected child
and `FRESH_RUN.json` marker. It also inspected 172 expanded active user array
tasks and found no other active study job or job command/work directory
referencing the target. The first preflight failed closed on compressed Slurm
array syntax; no deletion occurred then. The corrected preflight passed before
submission. Destructive filesystem work ran only in scheduled compute job
`22008303`, not on a login node.

At 06:48 UTC, Slurm reported `22008303` **COMPLETED** with exit `0:0`, the
outside-root receipt reported `SUCCESS`, the log contained
`STUDY_DELETE_DONE`, and a fresh read-only check found the exact scratch root
absent. The receipt was retained at
`/home/pwa209/factorcon-study-removal-20260929.json` and the Slurm log at
`/home/pwa209/factorcon-study-removal-22008303.log`.

The account-level personal scratch report changed from approximately
**11 TB and 845K/1M files** before the operation to **3,454 GB and
638K/1M files** at the post-job check. This is a shared personal-scratch
quota, with delayed accounting and other projects present; the account-level
delta should not be represented as a precisely isolated study-only count.
The study root itself was verified absent. The GitHub code and aggregate
scientific checkpoint remain; the Rorqual raw and detailed empirical copy does
not.
