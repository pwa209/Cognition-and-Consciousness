# Local pattern and report command contracts

Python 3.12 and `pip install -e '.[test]'` provide the NumPy/SciPy/test runtime for
these commands. For the broader analysis environment use the `analysis` extra.
Paths below are placeholders for private local/NAS artifacts, never files to commit.
**Do not deploy or run these analysis commands on the university server under the
current acquisition-only authorization.**

## P04 report measurement

```sh
factorcon measurement --input PRIVATE/report_calibration.json --output PRIVATE/posterior.json --dry-run
factorcon measurement --input PRIVATE/report_calibration.json --output PRIVATE/posterior.json
```

Input JSON keys:

- `schema_version: 1`, `predictor_source: "non_neural_fixed_units"`, nonempty `anchor_id`;
- `design`: trial × fixed predictors, finite, first column ones;
- `reports`: integer ordinal categories 0 through K−1, or −1 for missing;
- `subjects`, `contexts`: one globally namespaced string ID per trial;
- `categories`: K, at least 2.

Predictors must have justified observed meanings; do not use neural outcomes or call
sleep stage/dose an experience label. A report-category zero is not latent E=0.
Posterior output includes calibration IDs, parameter/threshold draws, diagnostics and
flags. `predict_reports` returns operational E and ordinal category probabilities;
aggregate predicted rows into conditions **within each draw**, not by thresholding
or averaging posterior parameters. `report_invariance_check` uses disjoint report
subjects; `missingness_sensitivity` exposes a declared pattern-mixture shift.

These APIs do not automatically produce a validated condition map from arbitrary
behavioral files. Report timing, condition assignment and independent calibration
selection must be supplied and audited for each dataset.

## P06–P08 pattern prediction

```sh
factorcon patterns --input PRIVATE/family_a.npz --mode within --output PRIVATE/within.json --dry-run
factorcon patterns --input PRIVATE/family_a.npz --mode within --output PRIVATE/within.json
factorcon patterns --input PRIVATE/family_a.npz --input PRIVATE/family_b.npz --mode lofo --output PRIVATE/transport.json
factorcon patterns --input PRIVATE/family_a.npz --mode within --bootstrap-replicates 1000 --output PRIVATE/refit_bootstrap.json
```

NPZ v1 must be non-pickled and contain exactly:

| Key | Shape / meaning |
|---|---|
| `patterns` | G × R × C × F, finite calibrated neural beta/epoch-pattern summaries |
| `group_ids` | G unique globally namespaced independent-subject IDs; iEEG uses patient IDs |
| `names` | Q distinct constructs E/A/R/K_content/K_memory/K_task/K_volition; no scalar S |
| `design_draws` | D × C × Q, calibrated construct draws; E in [0,1] |
| `sensory` | C × J fixed sensory covariates, J may be zero |
| `noise` | (R C) × (R C), known symmetric positive-definite design/independent-calibration covariance |
| `metadata` | scalar Unicode JSON with the declarations below |

G≥3, R≥2, C≥3. All features in a paired comparison use identical definitions/order.
Metadata: `schema_version:1`, `source_kind` (`synthetic_fixture` or
`derived_neural_patterns`), `family`, `anchor_id`, `units`, `feature_definition`,
`noise_definition`, `design_source` (`fixed_by_design` or `external_calibration`),
`calibration_ids`. Empirical files additionally require `feature_scaling:
"independent_calibration"` and `source_sha256` records. An empirical E column requires
external calibration. All calibration IDs must be disjoint from **every** neural
group across the collection, including target families. Within-subject empirical
calibration is not supported by this contract.

`whiten_patterns` consumes already prepared pattern arrays and **independent**
residuals. It does not preprocess raw MRI, EEG or iEEG. An identical `anchor_id`
string cannot establish scientific comparability; the underlying measurement and
feature calibration records must justify it. LOFO never estimates target scale/noise
or selects target-favorable penalties. M5 has no invented condition correspondence.

Outputs retain M0–M5 and all fold audits. Joint nats/group depend on dimensionality;
paired normalized summaries use nats/scored dimension and equal family weights.
Missing comparison families do not silently disappear from bootstrap summaries.

## P05 independent stress tests

```sh
factorcon stress --plan conf/report_stress.yaml --output PRIVATE/report_stress.json --dry-run
factorcon stress --plan conf/report_stress.yaml --output PRIVATE/report_stress.json
factorcon stress --plan conf/pattern_stress.yaml --output PRIVATE/pattern_stress.json
```

The versioned plans request 200 replicates per scenario and can be expensive. They
have **not** been run as a production validation campaign. Tests use explicitly small
synthetic variants. Recovery wins are not p-values. Report interval coverage and its
Monte Carlo uncertainty concern only the simulated slope/scenarios, not universal
coverage. Inspect numerical diagnostics and failures rather than dropping them.

## Artifact lifecycle

Commands write atomic RUNNING/SUCCESS/FAILED markers and per-attempt provenance
under `<output>.runs/`, including source/config/input/output hashes. Completed outputs
are not overwritten. A failed attempt without final output can be retried. Stress
runs checkpoint completed replicates for diagnosis; a retry currently recomputes the
deterministic run rather than resuming a partial chain or optimizer. Abrupt process
death can leave RUNNING; multi-process locking and remote checkpoint resume are not
certified. These limitations prevent claiming full production phase completion.
