# Fresh Rorqual deployment — 2026-09-16

Non-preregistered secondary analysis; no scientific gates. The owner authorized fresh
acquisition, isolated environments/tests, and ready analysis phases on Compute Canada.
The university server remains acquisition-only and is unchanged. Reference projects
AI Collective Intelligence and Artificial Anaesthesia were read only for operational
procedures; their data, environments and scientific specifications are not reused.

## Identity and storage

Verified at 09:53 UTC: `pwa209@rorqual.alliancecan.ca`, host `rorqual1`, owned personal
`/scratch/pwa209`. Live quota: **871 GB / 20 TB**, **142K / 1000K files**. This is an
observation, not a reservation. The separate shared `/project` quota is not used.

Fresh root: `/scratch/pwa209/cognition-and-consciousness/fresh-20260916`.
All source transfers, publisher data, packages, caches, temporary files, extracted
data, derivatives and results go beneath it. Expected pinned raw size is about
3.44 TB plus open DREAM constituents; extraction/derivatives require additional space.
Acquisition periodically checks personal quota, conservatively retaining 500 GB and
50,000 files. Other projects can consume the same personal quota concurrently.

Scratch is not backed up and is purgeable. GitHub retains source, configuration and
reviewed compact operational records, not participant data or large derivatives.
Do not evade purge policy by artificially refreshing files. Archive elsewhere only
with separately agreed storage. [Alliance storage documentation](https://docs.alliancecan.ca/mediawiki/images/9/99/File_Systems.pdf).

## Authentication and execution

`interactive_bridge.py` uses native SSH with the existing verified host-key file.
Password and Duo/OTP go directly to the user's visible console. Only remote stdout
is logged. A sent script is not proof of execution: reconcile remote completion
markers and side effects after disconnection before retrying. No credential is saved.

1. Verify live host, ownership, personal quota, tools and scheduler association.
   Discovered: `StdEnv/2023`, `python/3.12.4`, CPU account `def-ptewarie_cpu`.
2. `prepare_release.py --commit COMMIT --root FRESH_ROOT --queue-file QUEUE.sh`
   builds a Git-only source transfer with archive and per-file SHA-256 checks.
   The receiver refuses an existing run root. Never delete a partial installation
   automatically: inspect/reconcile it or explicitly document a different fresh root.
   For a source-only repair in this same fresh run, `--existing-run` adds a new
   immutable commit directory and per-release `RELEASE.json`. It never overwrites
   the original `FRESH_RUN.json`, raw data, acquisition process or earlier source.
3. Set `FACTORCON_ALLIANCE_ROOT` and `FACTORCON_RELEASE` from `FRESH_RUN.json`.
   Submit `qualify.sbatch` with the CPU account, scratch stdout/stderr paths, and
   `FACTORCON_PYTHON_MODULE=python/3.12.4`. It installs a private environment from
   cluster wheels and runs config validation, dry runs and the complete test suite.
4. `bash scripts/alliance/launch_acquisition.sh` starts a detached, low-priority,
   single-worker publisher download. This uses standard-library acquisition code,
   not another project's environment. Access/terms restrictions remain explicit.
5. After technical qualification, `stress.sbatch` runs independent P05 simulations.
   One array task executes one original replicate across every scenario. Original
   plans contain 200 replicates: indices 0–199, concurrency one per suite, at most
   eight CPUs across two suites. Check scheduler limits and first-task runtime
   before expanding submissions. Poor recovery/coverage never suppresses later work.

Downloads use the network-enabled login/transfer surface as in the reference projects;
CPU-heavy processing goes through Slurm. Compute-node internet is restricted.
[DRAC/Rorqual operational reference](https://docs.mila.quebec/technical_reference/clusters/drac/).

## Evidence and recovery

Acquisition: `operations/acquisition/status.json`, attempt provenance, source manifests
and durable per-file SHA-256 ledgers. Verified files and `.part` objects resume only
within this fresh run; source/configuration hashes must match. A downloaded DREAM
registry or a launched PID is not completion. Restricted sources yield explicit holds.

Qualification: `qualification/JOB/` status/provenance, modules, package versions,
install/test logs, dry runs and JUnit. P05: `analysis/P05/SUITE/replicate-NNN/JOB/`
with original replicate/seed, hashes, status and all numerical outcomes. Retry failed
replicates under a new job ID with identical seeds; never choose the best retry.
P05 retries recompute; they do not resume partial optimizers/chains. SIGKILL can leave
RUNNING and requires `sacct` reconciliation, not a success claim.

First qualification job `21169188` installed its isolated packages successfully but
failed the acquisition dry run: the initial guard accepted login names, not Slurm
compute node `rc32623`. The repair additionally accepts `rc` + digits only with
`SLURM_CLUSTER_NAME=rorqual` and a numeric Slurm job ID; user and personal-root
ownership checks remain mandatory. This is a technical deployment repair, not a
scientific result-dependent change. The failed attempt/environment are preserved.

## Phase map

| Phase | Execution path | Remaining technical/evidence requirement |
|---|---|---|
| P00 | Identity/quota checks, immutable source, CPU qualification | Actual job evidence in dated deployment record |
| P01–P02 | Fresh resolution and resumable publisher acquisition | COGITATE account/terms and restricted DREAM constituents |
| P03 | Per-family integrity/schema validation | Acquired bytes and verified raw layout; archives alone are insufficient |
| P04 | WM/masked harmonizers and report measurement | Verified report links and independent calibration cohorts |
| P05 | Report and pattern simulation shards | Qualified environment; independent of participant acquisition |
| P06 | Modality-specific raw-to-pattern production | Certified producers for every modality are not yet implemented |
| P07 | All M0–M5, `patterns --mode within` | Valid grouped patterns and external calibration |
| P08 | `patterns --mode lofo` | Justified common anchors/units and source support |
| P09 | Missingness/invariance/bootstrap utilities | Exchangeability and calibrated simultaneous inference |
| P10 | Figures, source tables, claims/reproducibility audit | Actual results including nulls, failures and limitations |

Authorization does not establish empirical readiness. The historical RDM workflow is
not substituted for the newer pattern engine. See `IMPLEMENTATION_FOLLOWUP_2026-09-10.md`.

### First acquired family: working memory

All 146 publisher files (542,530,371 bytes) completed at 10:11:32 UTC. The study-specific
`wm_phase.sbatch` / `wm_phase.py` path now runs P03 deep checksum/archive validation,
then P04 schema normalization only after P03 technical success. It enforces recorded
ZIP CRC failures, preserves all raw files and writes private per-job artifacts with
status/provenance. P04 checks the existing 531-participant/19-laboratory schema contract.
These jobs do not fit behavioral effects or turn PAS values into E probabilities.
Unfavorable scientific results do not enter their scheduling decisions.
