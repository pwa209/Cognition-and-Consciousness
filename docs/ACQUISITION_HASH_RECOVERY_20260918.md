# Transfer / digest separation — 2026-09-18

COGITATE and Volition processes disappeared again without exception logs. Their
locks were free. The exact termination cause is **not established**. No resource
limit is raised and no automatic restart loop evades login-node enforcement.

Network probe Slurm job 21322894 could read personal quota but timed out connecting
to both OpenNeuro and the COGITATE publisher. Therefore HTTP transfers cannot simply
be moved into a compute job. The probe's overall shell exit 0 is not evidence of
network success: both curl calls explicitly failed.

Large-file digests (at least 256 MiB) now use a study-owned filesystem request/result
queue under `operations/hash-service`. One Slurm CPU with 2 GiB memory computes
SHA-256/MD5, validates path confinement and checks byte-size/mtime before and after.
Requests are data, never executable commands. Network workers wait for matching
results and retain partials on failure. A six-hour request timeout bounds waiting.
The service has a 48-hour Slurm bound and exits when both families finish. Inspect
sacct after node loss or timeout; stale status is never proof that a worker is alive.

The complete 752,061,695,148-byte MEEG partial receives a HEAD check against the
pinned ETag and size, then scheduled SHA-256 hashing and atomic promotion. It is
not downloaded again or accepted merely because its size matches. ETag is not a
publisher cryptographic checksum; local SHA-256 is provenance, not independent
publisher certification. Hashing status has a separate JSON sidecar.

`transfer_worker.sh` keeps HTTP on the approved login surface, with a dated exit
record when its child exits. `hash_service.sbatch` owns large-digest CPU execution.
The systemd user probe worked, but `Linger=no`; no account-wide linger setting was
changed and no logout-survival guarantee is claimed. Volition and COGITATE retain
the same frozen manifests and download ledgers. Other completed datasets and P05
jobs are untouched. This change affects engineering only, not scientific scope.
