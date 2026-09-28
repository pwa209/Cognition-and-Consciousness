# P10 structural bootstrap repair (28 September 2026)

The completed masked-fMRI bootstrap has 1,000 hash-bound P09 attempts. Of these,
887 returned paired model contrasts and 113 returned the same structural failure:
fewer than three independent groups in a resampled family. The original P10
report and all failed draws remain immutable provenance.

The repair will retain every originally estimable draw and deterministically
redraw only the 113 structurally invalid group-multiplicity vectors until each
family has at least three distinct groups. This changes the reported bootstrap
target to the distribution of the nested estimator conditional on structural
estimability. It does not create unconditional uncertainty or validate population
coverage from five evaluation participants. New attempts and the new P10 report
must be separately versioned and labeled; no model result determines redraws.

The original seed is 260830 and the five-participant draw is indexed by
`SeedSequence([seed, replicate])`. Recomputing only its group counts locally
produces exactly 113 structurally invalid IDs among 1,000, matching the
hash-bound P10 reason census; this check uses no neural observations or scores.
Each failed ID retains its original multiplicity vector. Its new stream starts
at `SeedSequence([seed, replicate, 1])`, increments the final counter only
while the group-count condition is unmet, and stops at the first structurally
valid draw. Numerical/model failures are recorded, not redrawn. The unchanged
887 initial valid vectors plus these 113 accepted redraws are samples from the
bootstrap distribution conditional on that structural event. The initial
failure fraction, source hashes, original P10 job and exact result-path mapping
are included in the new report provenance.

The first cluster preflight stopped because the older source release uses LF
line endings and the Windows-packaged repair release uses CRLF. All 21 compared
Python/YAML scientific and scoring files matched after newline normalization.
The repair now accepts only that text-format difference for compatibility;
each release still independently verifies its original byte-level file hashes,
and any substantive content change still aborts the mixed-release analysis.
Slurm also requires LF-only batch files: dispatch derives one immutable LF copy
from the verified release into its operations directory and refuses to reuse
that copy if its contents change. Python source files remain in the original
hash-verified release.

The new interval is an unadjusted percentile summary at fixed families,
conditions and external calibration. It is not a validated small-sample
coverage statement, an unconditional interval, or a multi-family P08 result.

## Rorqual submission receipt (28 September 2026)

The verified source-only release is
`42b52abb743b09d1e168843d098bae6a6cbe260c` on personal scratch under
`/scratch/pwa209/cognition-and-consciousness/fresh-20260916`. Its transfer
SHA-256 was `297BD007E0E6C3F62C34C0C3FD9FB5EC518C9717F942A0990B34E3DFBF2A9546`;
the installer verified 306 source files. The cluster-side dry run reported
exactly 113 structural IDs and a concurrency limit of eight retry tasks.

Slurm accepted P09 structural redraw array `21943233` and dependent P10
conditional report `21943235` at 2026-09-28 07:23:36 UTC. The durable receipts
are in `operations/p10-structural-repair/42b52abb743b09d1e168843d098bae6a6cbe260c/`
under that personal scratch root. At submission, both jobs were pending; P10
was pending on the P09 dependency. This is a submission record, not a claim
that redraws or the new report have completed. The original P10 job `21842472`
and all original failure records are preserved.

## Operational acceleration (28 September 2026)

At 08:59:53 UTC, the live receipt census showed nine successful redraws,
eight running, 96 without status, and no recorded failures. The array owner,
source release, job name, four CPUs per task and existing `%8` throttle were
verified before changing only Slurm `ArrayTaskThrottle` for job `21943233`
from 8 to 20. `scontrol` returned success and then reported `%20`. This
allows at most 80 allocated CPUs, subject to scheduler availability; it does
not change replicate IDs, seeds, models, result paths or the P10 dependency.
The cluster-side receipt is
`operations/p10-structural-repair/42b52abb743b09d1e168843d098bae6a6cbe260c/p09-throttle-20-20260928.json`.
The earlier 25-task setting in the original campaign led to quota-service
timeouts, so this is a bounded increase, not an unqualified 100-core claim.
