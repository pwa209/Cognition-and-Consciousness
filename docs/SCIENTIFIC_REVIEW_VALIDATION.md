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
