# Rorqual deployment status

**Downstream execution layer — 2026-09-19 09:23 UTC:** release `5b8e91f` is installed;
qualification **21410644 passed 192 tests** and artifact audit **21410645 succeeded**.
The audit found zero model-ready NPZ candidates. P06 prepared-pattern assembly,
P07/P08 generative fitting, P09 subject-bootstrap arrays and P10 evidence tables have
tested Slurm wrappers, but **no empirical P06-P10 jobs are submitted**. Raw preprocessing
and independent calibration remain missing. See [contracts and exact scope](DOWNSTREAM_EXECUTION_20260919.md).
Masked P03 **21409959 succeeded**; its P04 successor **21409960 failed** on the source
token `missing data`. A repair retains all 8,235 such rows as unknown reports and
preserves the original token; the expanded local suite passed 194 tests. The failed
attempt remains intact and needs a separately qualified retry.

**Empirical preparation — 2026-09-19:** replacement release `0f43141` installed and
nine jobs accepted: qualification 21409958, six P03 integrity/schema jobs, and two
dependent P04 harmonizers (masked fMRI and COGITATE fMRI). Initial qualification
21409777 failed a filesystem-sensitive fixture; its downstream jobs are CANCELLED
and the complete attempt history is retained. See the [implementation, phase map
and job receipts](EMPIRICAL_IMPLEMENTATION_20260919.md). P06–P10 are not submitted.
Available COGITATE bundles and Volition downloads completed before this deployment;
historical acquisition counters below are not current status.
Qualification 21409958 passed 178 tests; the EEG raw-cohort correction release
`abcc10c` passed 179 tests remotely in qualification 21410131. EEG-only retry
21410132 is queued; masked P03 21409959 and COGITATE P03 21409963 were RUNNING
at 08:55 UTC. Other preparation jobs retain their existing qualified source.

**Hashing recovery — 2026-09-18 06:35 UTC:** COGITATE and Volition restarted with
large-file hashing separated into Slurm job 21324125. The full MEEG partial is
being hashed rather than re-downloaded. See [deployment evidence and limitations](ACQUISITION_HASH_RECOVERY_20260918.md).

**Recovery update — 2026-09-17 05:55 UTC:** DREAM, COGITATE and BMVP were
resumed with verified partial-byte growth. Quota-service retries retain all storage
safety checks. See [recovery evidence](ACQUISITION_RECOVERY_20260917.md).

**Later acquisition update — 2026-09-16 17:34 UTC:** the isolated repair release
resolved Volition's complete expected inventory, 19 public DREAM sets and five
authorized COGITATE bundles. All three transfers started on personal scratch.
Private DREAM set 8 and the mislabeled raw-MEEG bundle remain held. See the
[repair evidence and commands](ACQUISITION_REPAIRS_20260916.md).
The timestamped records below are historical snapshots, not current counters.

Observed **2026-09-16 10:21:55 UTC**. This is a dated operational record, not a live
dashboard, preregistration or scientific result. No raw participant data are in Git.

## Storage and authorization

Owner authorized fresh Compute Canada acquisition, environment/tests and ready
analysis phases. University-server acquisition-only authorization remains unchanged.
No university-server or reference-project data/environments were copied or changed.

Fresh root: `/scratch/pwa209/cognition-and-consciousness/fresh-20260916`.
All downloads, environments, caches, temporary files, derivatives and outputs use
this **personal** scratch run, not shared `/project`. Personal quota was verified as
20 TB / 1 million files; latest report: 904 GB / 158K files used across the user's
projects. Scratch has no backup guarantee and is purgeable; this is not archival storage.

Authentication followed the two reference projects' native SSH console method:
password and Duo/OTP entered by the owner directly, with no secret saved or logged.
The first connection failed before returning server output; the second connected to
`rorqual1` as `pwa209`. Host-key verification was not disabled or replaced.

## Immutable source releases

Every release was transferred from reviewed committed Git source, checked against
its archive SHA-256 and per-file SHA-256 inventory, and installed without overwriting
an earlier release or the initial fresh-run marker.

| Use | Commit | Archive SHA-256 | Verified files |
|---|---|---|---:|
| Active acquisition | `2269253f4519dd6adb42c5b828063e780f8b2358` | `18456700eb0af2b9ced72af003615beafb1e015e03aa19e9474bf93c1225f7e2` | 154 |
| Qualified environment / P05 | `2d4e03e6b2c9ae582730dfb6778484c754017ef7` | `510f6bf8e92a4cfd38ef8291645681cbb5e1af2f4f280bd83ab69b09cd4e7163` | 154 |
| WM P03/P04 wrappers | `f20a824c9048cb414b6b0f61b2436308ac4769a7` | `e5f21337daba7ccaff5f311c0d040ed6b73e563f1e8983b6978b1af83352c17c` | 156 |

Source path: `FRESH_ROOT/releases/COMMIT/source`. Initial identity/manifest:
`FRESH_RUN.json`; later releases have adjacent `RELEASE.json`. Acquisition continues
on its original source and PID **1002588**; the repairs did not restart it.

## Executed and queued phases

| Phase | Job/process | Observed state and evidence |
|---|---|---|
| First qualification | `21169188` | FAILED: compute-node hostname was not accepted by initial login-only guard; preserved |
| Repaired qualification | `21169236` | COMPLETED, exit 0; **130 tests passed** in 55.66 s; dry runs passed |
| P01–P02 WM | acquisition PID above | **146/146 files**, 542,530,371 bytes, zero failures; completed 10:11:32 UTC |
| P01–P02 awakening EEG | acquisition PID above | **300/1442 files**, 14,263,351,309 verified bytes, zero failures; RUNNING |
| Remaining acquisition families | same sequential campaign | Not complete; masked fMRI, DREAM, COGITATE, volition, BMVP follow with explicit access/source holds |
| WM P03 integrity | `21169386` | COMPLETED, 5 s; 146 files valid, no reported errors/warnings |
| WM P04 harmonization | `21169387` | COMPLETED, 20 s; **451,662 rows, 531 participants, 19 laboratories** |
| P05 reports, replicate 0 | `21169271_0` | SUCCESS, 36 s; all original scenarios retained |
| P05 reports, replicates 1–199 | `21169422` | Submitted, concurrency 1; task 2 running at snapshot |
| P05 patterns, replicate 0 | `21169272_0` | RUNNING, 10 min observed; no completion claim |
| P05 patterns, replicates 1–199 | `21169423` | PENDING on initial pattern task's technical completion, concurrency 1 |

The scheduler rejected an attempt to depend on the already-completed report pilot
after its controller record aged out. No remaining-array receipt existed and queue
inspection showed only the initial pattern job. The retry verified durable report
SUCCESS, omitted that obsolete dependency, and recorded the two new array IDs above.
This was a dependency repair, not a change based on recovery, coverage or model wins.

P05 has **200 replicates per suite**, four scenarios each, including the initial
replicates. Each task requests four CPUs, 16 GiB and a 12-hour wall-time bound; only
one task per suite runs concurrently. A technical task failure is retained; poor or
null scientific outcomes are not discarded. A completed task is not a completed
campaign. Aggregate by original replicate IDs in the wrapper provenance, not the
local zero index inside each one-replicate result; do not double-count retries.

## Verification and recovery

- Latest local full suite: **132 passed**, 57.83 s. Targeted Ruff and shell syntax
  checks passed. Additional WM wrapper/adapter fixtures ran in both WM Slurm jobs.
- Qualified environment: `environments/qualification-21169236`, Python 3.12.4,
  NumPy 2.5.3+computecanada, SciPy 1.18.1+computecanada, pytest 8.4.2+computecanada.
  Exact dependencies/modules are retained under `qualification/21169236/`.
- Acquisition source manifests and per-file SHA-256 event ledgers are under
  `manifests/generated/` and `run_state/P02/`; status and attempt provenance are
  under `operations/acquisition/`. Completed raw files are not copied into Git.
- WM private artifacts are under `analysis/P03/multisite_working_memory/21169386/`
  and `analysis/P04/multisite_working_memory/21169387/`. PAS remains raw ordinal
  report evidence; harmonization is not a fitted E measurement or a scientific finding.
- P05 status/provenance/checkpoints are under `analysis/P05/SUITE/replicate-NNN/JOB/`.
  Slurm logs and submission receipts are under `operations/`. Reconcile interrupted
  states with `sacct`; do not treat a sent queue script or stale RUNNING as success.
- Download resume stays inside this same fresh run. Simulation retries preserve
  original seeds and use new job-ID directories; failed attempts are never overwritten.

## Remaining scope

All-data acquisition is **not complete**. COGITATE still requires owner-managed access
and terms; DREAM constituent access remains explicit. Full empirical P06–P10 requires
the remaining validated adapters, source report links, neural pattern producers and
calibration/inference evidence described in the [phase roadmap](ALLIANCE_FRESH_RUN.md).
These are not supplied by successful deployment, nor by a favorable simulation result.
No journal acceptance or complete raw-to-manuscript readiness is claimed.
