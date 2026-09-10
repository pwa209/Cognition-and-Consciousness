# Canonical RDM v2 contract

This is the local, fixed-condition component-RDM prototype interface, not a full
latent consciousness model or a preregistration. Do not migrate old inputs by
inventing participant identifiers.

| Array | Shape / values |
|---|---|
| `train_rdms`, `test_rdms` | finite replicate-by-pair floats; strict upper triangle, condition order below; retain negative crossnobis distances |
| `design_names` | unique strings from E, A, R, K_content, K_memory, K_task, K_volition, S |
| `design_values` | construct-by-condition floats; no outcome-derived test-set values |
| `condition_labels` | at least 3 unique strings in common train/test order |
| `train_group_ids`, `test_group_ids` | one nonempty string per RDM row, with disjoint sets; repeats within a group are allowed |
| `independent_unit` | scalar string: participant, patient, laboratory, contributing_dataset, or synthetic_participant |
| `design_origin` | scalar string: fixed_by_design |

At least three training groups are needed for inner tuning and predictive-error
calibration. One test group can be scored descriptively but cannot supply a group
SE. Group IDs must identify the independent unit, not an electrode, trial, run,
posterior draw or repeated-CV fold. Subject-within-run analyses require a separate
nested contract and must not be passed off as participant-held-out evaluation.

Within each training and test group, RDM rows are averaged before fitting/scoring.
The target is an independent group's mean geometry, with equal group weight, not
individual trials or windows. Replicate scores are diagnostic only; inference uses
group scores. Upstream adapters must document their replicate definition.
Conditions are fixed. No unseen-condition or unseen-paradigm claim follows.

Empirically estimated E tables are not yet supported by this generic interface.
Fitting a measurement model once to the outer-training partition is insufficient:
its inner-validation groups would influence tuning through the learned table.
The future latent-measurement runner must refit inside each inner fold and propagate
draws without accessing test outcomes. Do not relabel fitted tables as fixed designs.

Example local commands (not deployment authorization):

```text
factorcon model score --family FAMILY --input rdms-v2.npz --output scores-v2.json --analysis-spec conf/analysis_spec.yaml
factorcon model synthesize --input family-a-v2.json --input family-b-v2.json --output synthesis-v2.json --analysis-spec conf/analysis_spec.yaml
factorcon model robustness --family FAMILY --input rdms-v2.npz --output robustness-v2.json --analysis-spec conf/analysis_spec.yaml
```

Add `--dry-run` to `model score` or `model robustness` to validate the input and
configuration without fitting or writing. Each scoring/synthesis/robustness attempt
writes an atomic `<output>.status.json` and a run-specific provenance JSON under
`<output>.runs/`, including input, specification, source-code and output hashes.
Failed attempts without an output can be retried; a completed output is never
overwritten. Supply a new versioned output path for a rerun. These commands are
not a resume-from-mid-fit scheduler, nor full phase operational certification.

Use new output paths when changing the specification. Score/spec hashes must match
for synthesis. Every model ID remains present; `not_estimable` records missing
construct requirements, not zero evidence. Diagnostics report aliased/constant
components without selecting or removing them by neural results. Score type and
prototype implementation appear in JSON and paper-source tables.

`M4_minus_M0` through `M4_minus_M3` are fixed comparisons; `M4_minus_M5` is a
separate benchmark, not a theoretical test. Family sets and missing uncertainties
are explicit. The synthesis is an equal-weight finite-family summary, not LOFO.

The contract checks declared identities/provenance, not the truth of upstream
labels. Adapters still need independent source-count, timing, leakage and
measurement-model tests. Files contain derived participant information and must
remain outside Git; the synthetic fixtures are the only test-data exception.
