# Acquisition recovery — 2026-09-17

Scope: technical acquisition recovery only; no scientific exclusions, model changes
or stopping gates. Personal fresh-run scratch remains the only download/cache target.

## Evidence and correction

DREAM completed 56/58 public files and COGITATE completed 3/5 bundles before two
files in each family failed with `diskusage_report` exceeding its 45-second timeout.
The retained partials include MEEG BIDS and DREAM set 14. This was not an observed
quota exhaustion, checksum failure or authentication failure.

`read_personal_quota` now makes at most three fresh-report attempts, waiting 5 and
10 seconds between transient timeout/OS/nonzero-exit failures. No download writes
occur while the guard retries. Invalid successful reports fail immediately. Exhausted
retries raise `CapacityError`, which stops new file submissions and preserves partials.
The 500 GB / 50,000-file reserves remain unchanged. No stale quota or shared `df`
fallback is permitted.

BMVP's checkpoint stopped at 114/168 archives (642,914,869,760 bytes). Its old PID
was absent on rorqual1 and its original campaign lock was available. The exact
reason that process exited is not established by the available log. Restart uses
the same frozen inventory and validates its fingerprint against the existing ledger.
The repair worker holds BOTH its family lock and the original campaign lock,
preventing concurrent original/repair writers. Existing verified-file events and
partial bytes are reused, not deleted or silently imported from another run.

## Commands

From the new verified immutable source release, run the existing repair command
with `--family dream`, `--family cogitate --catalog PRIVATE_CATALOG_PATH`, or
`--family bmvp`. First use `--dry-run`; normal execution uses one HTTP worker per
family. DREAM/COGITATE retain their repair manifests and ledgers. BMVP uses its
original P02 download ledger but separate repair status and attempt provenance.
Original campaign status is historical and is not silently rewritten as current.

Volition's active process and P05 simulation jobs are intentionally unchanged.
Previously recorded access holds (private DREAM set 8 and the mislabeled native
MEEG bundle link) remain; resuming BIDS MEEG does not require that broken link.

## Verified deployment

Release `c2043759ff6aa7b633e1dd90a84c1dce4b491c81` was installed with 165
verified source files; archive SHA-256
`3fc3cb01a271e4913185dc0661da3f153a211698541e6089e9855512d4ed3d46`.
Local full suite: **143 passed**. Rorqual targeted suite: **33 passed**.
All three dry runs passed before launch.

At **2026-09-17 05:55:39 UTC**, all three workers reported DOWNLOADING, with
zero failures in their new attempts and growing partial files:

| Family | PID on rorqual3 | Previously completed objects reused | Resumed partial bytes |
|---|---:|---:|---:|
| DREAM | 3720696 | 56/58 | 20,929,576,960 |
| COGITATE | 3720703 | 3/5 | 73,895,247,872 (MEEG BIDS) |
| BMVP | 3720755 | 114/168 | 1,711,276,032 |

Partial growth was checked against the pre-restart sizes; this verifies resumed
transfer, not complete datasets. Historical failed attempts remain preserved.
P05 pattern task 21169423_36 remained running; its queued successors were unchanged.

## Evening restart — 2026-09-17

At 18:51 UTC the COGITATE, BMVP and Volition workers were absent on rorqual3
and their campaign locks were free, despite stale DOWNLOADING markers. Logs did
not establish the exit cause. DREAM had completed all 58 public files.

At the owner's explicit request, the three incomplete workers were restarted on
rorqual4 at 18:53 UTC using the same tested `c204375` release, frozen manifests,
ledgers and personal scratch paths. New PIDs: COGITATE 2291491, BMVP 2291497,
Volition 2291537. Dry runs and fresh personal quota checks passed. COGITATE reused
three complete bundles; BMVP reused 121 complete archives. Their partial files
grew to 170,873,692,160 and 9,768,587,264 bytes respectively at the first check.
Volition was initially reconciling its saved inventory; process launch alone was
not counted as resumed byte transfer. DREAM and simulation jobs were untouched.
