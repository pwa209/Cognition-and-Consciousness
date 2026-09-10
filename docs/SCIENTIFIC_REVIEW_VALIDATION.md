# Scientific review validation — 2026-09-10

Scope: local component-RDM scoring, grouped calibration, synthesis, robustness and
audit documentation. No participant data were downloaded locally or analyzed.

## Executed checks

- Targeted regression/configuration/canonical tests passed during development.
- Full suite: see the final execution count below.
- Ruff checks on `src` and `tests`: passed.
- Python byte compilation of `src` and `tests`: passed.
- `factorcon config validate --config conf/base.yaml`: passed; registration null,
  scientific gates false, all six candidates retained, deployment acquisition-only.
- `git diff --check`: passed.

Full-suite final result: **78 tests passed**.

Environment: Python 3.12.14, NumPy 2.3.5, pytest 8.4.2, Ruff 0.16.7. Test/lint tools
were installed in the ignored local `.tmp/review-deps` directory, not on the server.

## Defects covered by regression tests

- Train/test identity overlap, missing identity fields, duplicate condition/construct
  names and unsupported inference units are rejected.
- Outer-training empirical design tables cannot masquerade as inner-fold-local inputs.
- Perturbing test values does not change fitted weights, alpha or predictive variance.
- Identical duplicated rows under the same ID cannot inflate group evidence.
- Both train and test targets are group-mean RDMs, not differently aggregated targets.
- M5 variance matches held-out-training prediction errors, not in-sample residuals.
- Constant components at alpha zero are finite; intercept fit matches a known solution.
- Fixed comparisons, equal weights, unknown SEs, duplicated families, unavailable
  candidates and all-model table retention are checked.
- Robustness uses whole-group influence and a shared condition permutation.
- Invalid score/configuration claims fail validation.
- Dry run performs no writes; a failed scoring attempt records FAILED/provenance,
  can retry after correcting inputs, and then records SUCCESS. Both run-specific
  provenance files remain. Existing completed outputs are protected from overwrite.

## Not established by these checks

No real-data adapter was validated here. No empirical measurement model, full
architecture/PCM pipeline, actual LOFO transfer, inferential coverage under realistic
neural noise, power, or journal-ready result was established. The synthetic recovery
suite remains a matched-generator code-consistency check. Full phase completion,
multi-process collision handling, remote restart-from-checkpoint and server integration
are not certified. The review does not authorize or perform analysis deployment.

## Follow-up implementation checks — later on 2026-09-10

The preceding 78-test record describes the first review, not the later implementation.
The follow-up's final full suite passed **118 tests in 55.31 seconds**. Ruff checks,
byte compilation, configuration validation and `git diff --check` also passed.
SciPy 1.16.3 was added to the ignored local test runtime; it was not installed on
the university server. No scientific analysis or participant-recording download was
performed on the local machine or deployed to the server by this follow-up.

Additional executed checks include:

- Repeated-partition Gaussian density matches an independent SciPy multivariate-normal
  reference; per-partition baseline shifts leave contrast density unchanged.
- All six candidate covariance matrices are PSD in synthetic tests; each architecture
  completes an actual numerical fit. M0 signed loadings and strict versus partial
  M1 gating are checked. Failed multistart fitting retains diagnostics.
- External design uncertainty uses log-mean-exp, demonstrably not mean log density.
- LOFO orchestration's held-out mutation test uses a deterministic fit stub to isolate
  split/tuning leakage; source parameters and tuning are unchanged. This is not a
  real-data LOFO validation. Common-anchor and cross-family calibration-ID rejection
  are tested.
- A real end-to-end **synthetic** within-family pattern stage performs nested fitting
  and produces all 18 scored model/fold rows (six candidates × three outer groups).
- Subject-bootstrap orchestration is tested with a deterministic evaluator: every
  replicate invokes a fresh evaluation, uses original subject IDs with multiplicity
  weights, and does not silently change the family population. A full empirical
  bootstrap coverage campaign has not been executed.
- Ordinal posterior probability normalization, ordered thresholds, anchored first
  threshold, missing-row likelihood exclusion, context-model comparison, separated-
  chain diagnostics and fixed missingness shifts are tested. Short chains test code,
  not convergence or identifiability in the intended datasets.
- Measurement command executes an actual synthetic fit and writes posterior/provenance
  artifacts. Small independent report stress fixtures execute all requested scenarios
  and checkpoint results. Neural generators are tested not to call fitted model
  covariance functions.
- Holm values, shared-sign endpoint handling and practical-equivalence precision are
  tested as mathematical utilities, not as validated inference on dependent CV scores.
- Verified-schema **synthetic** ds003927 fixtures cover labels, missingness, unknown RT
  units, expected participant counts and path escapes. No participant rows are committed.
- BIDS timing accepts negative onset/unknown duration and rejects nonfinite timings.
  Corrected odd/even one-sided PSD values match SciPy periodograms.
- Pattern dry run does not write; failure → corrected retry → success preserves both
  attempt records; existing completed outputs remain protected.

See `IMPLEMENTATION_FOLLOWUP_2026-09-10.md` for unresolved scientific and engineering
requirements. Passing these tests does not certify all phases, all dataset adapters,
full simulation power/coverage, simultaneous type-I error, causal claims, a universal
E scale, multi-process safety, remote checkpoint resume or journal readiness.
