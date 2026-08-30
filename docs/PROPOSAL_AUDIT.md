# Proposal-to-implementation audit

## Accepted scientific core

The proposal's strongest contribution is a connected construct-bridge design across seven families. It distinguishes experiential status (`E`), cognitive-operation components (`K_content`, `K_memory`, `K_task`, `K_volition`), arousal/global state (`A`), report/action (`R`), and physical/sensory structure (`S`). It compares six architectures from a unitary rank-one account through a saturated predictive ceiling, emphasizing held-out prediction, representational geometry, unique variance, temporal generalization, and leave-one-family-out transfer.

The implementation retains:

- dataset-specific measurement links for `E` rather than hard unconscious labels;
- equal-family evidence synthesis rather than pooled-trial dominance;
- identical grouped outer folds and fold-local preprocessing for all models;
- M0-M5 evaluation, effective-complexity reporting, and a saturated ceiling;
- deterministic provenance, checksum inventories, synthetic recovery, and leakage tests;
- within-stage sleep comparisons, continuous propofol state, no-report calibration, and patient-level iEEG grouping;
- complete reporting of favorable, null, unfavorable, heterogeneous, and low-ceiling findings.

## Explicit user-directed departures

The project is not registered or preregistered. The proposal's terms “confirmatory,” “freeze,” and “lockbox” are not carried forward as registration claims or data-access barriers. Instead:

- `conf/analysis_spec.yaml` is a transparent, versioned specification;
- data remain accessible to the owner; no environment variable hides a partition;
- code/configuration changes are permitted and logged in `docs/DEVIATIONS.md`;
- all completed versions and result paths remain auditable;
- no positive control, model rank, p-value, ELPD direction, detectable effect, or journal criterion determines whether the next scientific phase runs.

Integrity failures still stop affected jobs. Continuing after a checksum mismatch, path traversal, leakage, corrupt event timing, or terms violation would not be “gate-free science”; it would be invalid computation.

## Feasibility correction

The proposal anticipated a Slurm cluster and 5 TB fast scratch. The verified host has 256 logical CPUs, about 1 TiB RAM, one H100 80 GB GPU, about 2.3 TB free on `/data1`, 3.2 TB on `/data2`, and 9.6 TB free on the NAS, but no Slurm and no permitted Docker socket. The operational design therefore:

- stores raw data directly on NAS;
- stages only active subjects/runs to `/data1`;
- stores restartable intermediates in `/data2`;
- uses `tmux`, file locks, logs, and markers instead of Slurm;
- uses Python virtual environments and pinned package manifests rather than relying on Docker;
- limits concurrent high-I/O jobs and cleans no data automatically.

## Claims discipline

The target is the minimum predictive architecture supported at the available measurement resolution. Factorization does not imply ontological independence. Decoding does not establish use by a participant. Unresponsiveness is not unconsciousness. Sleep stage and anesthesia dose are not definitions of experience. Temporal precedence constrains but does not establish causality.

