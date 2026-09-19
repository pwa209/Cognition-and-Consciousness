# P06-P10 execution layer — 19 September 2026

This is a **non-preregistered** secondary analysis, with no scientific gates.
These scripts are a real generative-model execution layer, **not a completed raw
neuroimaging pipeline**. The live server audit at approximately 09:03 UTC found no
model-ready NPZ files under the study analysis root. The masked-fMRI and COGITATE
P03 inventories contained no `preproc_bold`/`denoised_bold` files. Do not substitute
synthetic patterns, unprocessed BOLD, report category codes or presumed E=1 labels.

## What this release adds

| Phase | Implemented command layer | Technical input required |
|---|---|---|
| P06 | hash-bound bundle validation, global calibration isolation, independent residual whitening, atomic model NPZ assembly | precomputed runwise neural summaries; disjoint feature/noise and construct calibration; documented conditions and partitions |
| P07 | nested within-family M0-M5 prediction using the existing generative engine | successful same-release P06 |
| P08 | source-only leave-family-out prediction, unavailable candidates retained | same P06; at least two families for applicability; compatible verified anchors for estimability |
| P09 | 1,000 independent-subject full nested-refit bootstrap shards, concurrency 2 | same P06; original participant/patient IDs maintained through multiplicity weights |
| P10 | per-group TSV, all candidate audits, paired normalized scores, bootstrap coverage and intervals | any completed P07/P08/P09 artifacts; failed/missing artifacts recorded explicitly |

All downstream paths are under the personal run
`/scratch/pwa209/cognition-and-consciousness/fresh-20260916`.
University-server analysis is still unauthorized; no university jobs are created.

The full intended P09 programme (calibration resampling, dataset-specific robustness,
simultaneous inference and justified equivalence margins) is **not completed** by
these subject-bootstrap scripts. P10 writes evidence tables, not a publication-ready
manuscript or a claim that the study's primary question is identified.

## Private input contract

Create a private campaign JSON **on personal scratch, never in Git**:

```json
{
  "schema_version": 1,
  "scientific_gates": false,
  "bundles": [{"path": "analysis/inputs/FAMILY/bundle.json", "sha256": "64-lowercase-hex-digest"}]
}
```

Each bundle JSON has schema_version=1 and source_kind=derived_neural_patterns;
family, anchor_id, source_units, feature_definition, noise_definition,
condition_definition, partition_definition, modality, and independent_unit
(participant or patient; iEEG must use patient). Required declarations:

- design_source: fixed_by_design or external_calibration; an E column requires the latter.
- noise_source: fixed_design or independent_calibration; never target outcome noise fitting.
- selection_basis: design_and_technical_integrity_only.
- arrays: root-relative path and SHA-256 for a non-pickled NPZ.
- provenance: root-relative path/SHA-256/role records, with roles preprocessing,
  noise_calibration and condition_mapping; external designs also require
  report_or_construct_calibration. The referenced JSON records must indicate
  technical SUCCESS and no scientific gate. Their scientific validity still needs
  source-specific review: passing declarations is not evidence of valid preprocessing.

NPZ exact keys and units:

| Key | Shape / meaning |
|---|---|
| patterns | G x R x C x F precomputed neural beta/epoch summaries, source feature units |
| group_ids | G globally namespaced independent participant/patient IDs |
| names | Q distinct named constructs; S belongs in sensory, not here |
| design_draws | D x C x Q, fixed design or independent construct posterior draws |
| sensory | C x J, fixed physical stimulus covariates |
| noise | RC x RC, common positive-definite design/calibration covariance |
| calibration_residuals | N x F, independent residuals in the same feature units/order |
| calibration_ids | unique disjoint subjects providing residual/noise calibration |
| design_calibration_ids | unique disjoint construct calibration subjects; empty Unicode vector only for fixed designs |
| feature_ids / calibration_feature_ids | F unique ordered strings; vectors must match exactly |
| condition_ids | C unique condition strings |
| partition_ids | R unique partition strings |

The existing engine assumes a common condition design and noise matrix across
participants within a bundle. Heterogeneous run designs cannot be silently averaged
into this contract. If this assumption cannot be justified, the likelihood must be
extended before empirical assembly. At least three independent evaluation groups,
two partitions and three conditions are required. The calibration subject set must
be disjoint from **every** evaluation family, not just its own family.

## Submission and execution

From the qualified immutable release with `PYTHONPATH=src`, first run without a
campaign to submit only qualification and an honest artifact-readiness census:

```sh
python scripts/alliance/submit_downstream.py --root /scratch/pwa209/cognition-and-consciousness/fresh-20260916
```

Once an independently reviewed empirical campaign exists:

```sh
python scripts/alliance/submit_downstream.py \
  --root /scratch/pwa209/cognition-and-consciousness/fresh-20260916 \
  --campaign /scratch/pwa209/cognition-and-consciousness/fresh-20260916/analysis/inputs/campaign.json
```

The dispatcher verifies inputs before submitting; saves a private campaign snapshot;
qualifies its own source release; uses `afterok` for technical predecessors; and uses
`afterany` for reporting. P07/P08/P09 are siblings after P06, so a model-fitting failure
does not prevent other scientifically independent branches. One-family P08 records
not-applicable, not a fictitious transfer score. No score threshold affects dispatch.

`downstream_phase.py --dry-run` takes `--root`, `--campaign`,
`--campaign-sha256`, `--phase`, and where applicable `--p06`, `--replicate` or
`--graph`/`--graph-sha256`. Dry runs validate actual predecessors and write no artifacts.

Status/provenance/result locations:
`analysis/downstream/PHASE/JOB[/files]`; P09 attempts use `ARRAY_JOB-REPLICATE`.
Input campaign bytes, source release, output hashes and upstream status identities
are bound together. Completed attempts cannot be overwritten. A retry uses a fresh
Slurm ID, leaving earlier failures intact. For a partially failed array, manually
submit only the failed indices using the same immutable release/campaign/seed and
record their new status paths in a new reporting graph; do not replace the old graph
or claim the dispatcher automatically retries failed submitted receipts. SUBMITTING
or UNCERTAIN receipts require scheduler reconciliation before resubmission.

Each P09 index uses `SeedSequence([260830, index])`, independent of scheduling order.
Its full evaluation and multiplicities remain in its own result. P10 uses all
requested replicates, not a successful subset, when deciding whether a percentile
interval is available. Intervals are unadjusted and conditional on the fixed external
calibration, conditions and families. They do not establish equivalence, simultaneous
error control or population-wide consciousness probabilities.

## Outstanding work before empirical dispatch

1. Implement and verify source-specific raw preprocessing, feature definitions,
   event/report linkage and technical exclusion accounting.
2. Specify and audit disjoint calibration cohorts and cross-family measurement
   anchors without examining architecture wins; generate real calibration artifacts.
3. Validate run/condition alignment and noise assumptions, assemble private bundles,
   then run the actual campaign preflight and submit its DAG.

No extra account login is required merely to finish the source code. Missing neural
inputs are implementation work, not something the owner should fabricate or upload.

## Deployment receipt

- Source release: `5b8e91f130ede82fa9cefe6a06f6d4c24d693be2`, pushed to
  `codex/alliance-fresh-20260916` and installed as a new immutable Rorqual release.
- Receiver verified 193 committed files; archive SHA-256:
  `73db41629f46aa1ca60de4e7c75be3a5ee477ff8cc038640d933b176913bb040`.
- Local verification: **192 tests passed**, 59.43 seconds; Ruff, Bash syntax and
  diff whitespace checks passed. The duplicate-ZIP-member test intentionally emits
  one Python warning. These tests use synthetic fixtures, not participant findings.
- At 09:21:18 UTC, qualification **21410644** and neural artifact audit **21410645**
  were accepted by Slurm; the audit depends on successful qualification.
- Dispatcher explicitly returned `empirical_jobs_submitted: false` because no
  verified neural-bundle campaign was available. **No empirical P06-P10 jobs were
  queued.** Existing P03/P04/P05 jobs were not cancelled or restarted.
- Predeployment host/owner/personal quota were checked live: Rorqual / pwa209,
  approximately 6,411 GB of personal 20 TB scratch and 645K/1M files. Shared-project
  quota warnings were not used as permission to store this study under `/project`.
- Qualification **21410644 subsequently passed 192 tests** in 61.54 seconds; audit
  **21410645 succeeded**, finding zero NPZ candidates. This confirms missing upstream
  neural inputs, not empirical scientific completion.

### Masked-event upstream repair

The same audit exposed P04 masked-fMRI job **21409960 FAILED**, following successful
P03 **21409959**. The source census across all 380 event files found visibility counts:
760 n/a, 47,453 conscious, 77,333 unconscious, 58,308 glimpse and **8,235 missing data**.
These are event-file rows, not asserted independent trials. The literal missing-data
token is now retained as an unknown report with no ordinal/E value; original fields
and every row remain available. An explicit predecessor-release option verifies old
P03 source/output hashes and unchanged acquisition configuration before reusing its
byte-integrity evidence with the repaired P04 adapter. No completed P03 marker is
rewritten. Expanded local tests: **194 passed**, 59.84 seconds, plus lint/Bash checks.

Repair release `7ab472a4a69076ca438cf35a0e1b3a605cdc586d` was installed with all 193
source files verified; archive SHA-256
`36b548257179e4082e93c7ce400cb169b1813dfc9244756ccfb42ba575d98d70`.
The real server P04 dry-run passed, binding the complete 1,314-file acquisition and
successful P03 job 21409959 to the new consumer release. New qualification
**21410793** and dependent P04 retry **21410794** were accepted by Slurm. No additional
P03 full-data rehash, P06-P10 empirical job or replacement of the old failed marker
was submitted.
Qualification **21410793 passed all 194 tests remotely** in 61.59 seconds, with
Slurm COMPLETED/exit 0. P04 **21410794** then started at 09:31:36 UTC. The downstream
scripts are technically qualified, but raw-to-neural integration and the broader
scientific P09/P10 deliverables remain unfinished.
P04 **21410794 completed successfully** (Slurm exit 0; marker 09:32:09 UTC):
**192,089 event-file records, 380 files, seven participants**. A separate post-run
scan verified all **8,235** explicit missing-report records remain present with
unknown report availability, null observed experience and null ordinal code.
