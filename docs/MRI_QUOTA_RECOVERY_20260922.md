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
Server qualification, archive counts, release hash, job IDs and post-archive quota
must be appended here after the immutable release is installed and dispatched.
