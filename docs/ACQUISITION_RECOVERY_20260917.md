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
