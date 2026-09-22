# MRI transient-quota recovery and inode control

This is an operational repair for the transparent non-preregistered secondary
analysis. It does not change the seven-participant cohort, report model, neural
features, M0-M5 architectures, folds, seeds, bootstrap replicates or scientific
interpretation. Null or unfavorable outcomes remain eligible for every later phase.

## Failure evidence

Rorqual job `21500396` was actively processing sub-05 when three consecutive
`diskusage_report` attempts timed out. The conservative monitor terminated fMRIPrep
and recorded a `CapacityError`; the scheduler then cancelled the serial MRI and
`afterok` analysis descendants. The storage service subsequently reported 11 TB of
20 TB and 843K of 1M files, so this was service unavailability rather than a proved
quota exceedance. P10's `afterany` dependency started it without a bundle and it
failed immediately on the absent bundle marker. No incomplete derivative was
promoted and no scientific result caused the stop.

## Repair

- Require a fresh personal-quota reading and 180K free-file start margin before
  every MRI retry. Shared `/project` capacity is never substituted.
- During an already-running MRI only, tolerate at most 30 minutes of transient
  quota-service unavailability. Each failed refresh pessimistically charges 50 GB
  and 10K files against the last fresh counters and enforces stricter 1 TB/100K
  stale reserves. Malformed reports, missing initial evidence, expiry or a bound
  crossing still terminate safely. Acquisition and ordinary writers remain
  fail-closed with no stale fallback.
- Before retrying sub-05, checksum and verify a tar of failed attempt
  `21500396-4/work`, then retire only the duplicate loose work members. Status,
  provenance, logs, partial derivatives, raw data and the recoverable archive stay.
- Run sub-05, sub-06 and sub-07 serially. Each successful MRI attempt must archive
  and retire its work tree before the next begins. Feature extraction outputs remain
  one ZIP per participant.
- Reuse successful report and sub-01 through sub-04 extraction artifacts by exact
  release/hash proof. Queue new sub-05 through sub-07 extraction, independent noise,
  bundle and P06-P10 attempts. P09 remains 1,000 fixed replicates packed into 50
  scheduler tasks. P10 additionally requires the new bundle to succeed, so an
  upstream cancellation cannot launch it against a missing bundle.

Every retry has a new Slurm/job identity and preserves the failed/cancelled records.
The archive step may run with only the 50-file metadata reserve; the MRI itself will
not start unless archiving has restored the stricter 180K free-file margin.

## Validation and deployment record

Local targeted recovery tests passed 27/27. The complete local suite passed 262
tests with five documented Windows/local-dependency skips and one intentional
duplicate-archive warning. Changed Python passed Ruff and `git diff --check`.
Immutable repair release `f4de98eb17d337f2c09bf478819b9bbf3b0234f6`
was installed with 263 files and source-archive SHA-256
`36665ec21510bef3845bf4f023cad6b26fbabca7cdf9cfada4198e8134f00667`.
Qualification **21571206** completed successfully: 267 server tests passed and both
baseline/patched real-container warning smokes passed. Preflight measured the failed
work tree as 149 GB and 61,755 loose entries; its archive target was absent and all
predecessor states matched the retained failure records.

The accepted recovery graph is:

| Stage | Job |
| --- | ---: |
| Verify/archive failed sub-05 work | 21571207 |
| MRI sub-05 / sub-06 / sub-07 | 21571208 / 21571209 / 21571210 |
| Extract sub-05 / sub-06 / sub-07 | 21571211 / 21571212 / 21571213 |
| Independent noise / bundle | 21571214 / 21571215 |
| P06 / P07 / P08 | 21571216 / 21571217 / 21571218 |
| P09 packed / P10 | 21571219 / 21571220 |

At 07:41 UTC archive job 21571207 was running after qualification. P09 is 50 tasks
at concurrency two, covering all 1,000 original replicate IDs. P10 depends on both
bundle success and terminal P07/P08/P09. Post-archive quota and net inode reduction
remain to be measured after verification and retirement; no completion is claimed yet.
