# Rorqual P09 quota-service recovery (26 September 2026)

The original masked-fMRI P09 analysis source is immutable release
`27ce5d1d4c565b5e5506fb4dce5e0843cd3b8dbe`, qualified by job
`21744804`; its P06, P07, P08, P09 and P10 jobs are `21744874`–`21744878`.
The packed batch runner source is `9acd74a5a23c2b280d855f6904272d1e413e67e1`.
The P09 input SHA-256 is
`711a3a6bf72b417b88c54d3d779f1857d18295f591201f8f1e3f17c7e708f530`.
These identify the original campaign; no new construct, seed, or model is
introduced by recovery.

Live Rorqual `sacct` and personal-scratch batch/replicate receipts showed
terminal FAILED array indices 4, 6, 7, 8, 23 and 24. Their successful
prefixes are respectively 80–82, 120–125, 140–143, 160–163, 460–463 and
480–483 (25 preserved successes). The first failures were 83, 126, 144,
164, 464 and 484, each with `CapacityError: personal quota service unavailable
after 3 attempts`; later replicate IDs in those batches were not attempted.
Thus 95 original IDs, not 120, need retry. This is an infrastructure failure,
not model convergence, scientific result direction, or observed capacity
exhaustion. A fresh report showed personal scratch at 12/20 TB and
834K/1,000K files; it is not a storage reservation.

The existing array's new-start throttle was changed from 25 to 8 and verified
in `scontrol`. Its remote receipt is
`operations/noise-recovery/27ce5d1d4c565b5e5506fb4dce5e0843cd3b8dbe/p09-throttle-recovery-20260926.json`.
Already-running tasks may exceed the new-start limit until they finish.

The recovery plan is in `conf/masked_p09_quota_recovery_20260926.yaml` and the
dispatcher in `scripts/alliance/submit_masked_p09_quota_recovery.py`. It checks
old scheduler-terminal states, hash-bound successful receipts, exact failed
causes, original input bytes, release identity and personal quota; then it
submits only the 95 original replicate IDs as a new four-at-a-time Slurm
array using the unchanged analysis code. It builds a lossless P10 input graph
that redirects only those 95 paths to the retry job and keeps all other
original P09 paths. New attempts and the new report never overwrite old ones.
Actual retry/P10 job IDs and receipts must be appended here after verified
submission. This is operational repair, not a post-hoc scientific exclusion.
