# Scientific design and implementation review — 10 September 2026

## Assessment

The study has a worthwhile question: do separate operational measures of experience,
cognitive operations, arousal and report improve prediction beyond simpler accounts,
and where does that separation generalize? Its strongest feature is the complementary
experimental contrasts, not the volume of downloaded data. However, the current code
is a component-RDM prototype, not an implementation of the proposal's full latent,
multimodal architecture. It is not yet ready to support a Nature/Science-level
architectural conclusion. Nature Human Behaviour is not a fallback justified merely
by less favorable results; scope, inference and contribution still have to stand.

This assessment uses the supplied proposal (especially Methods 4–6 and 14–23), local
configuration, analysis and synthesis source, and targeted primary-methods literature.
No participant outcomes were analyzed. No claim is made of independent human review,
exhaustive literature review, or journal acceptance probability. The scientific-nature
skill's evidence contract motivated the claim-to-method distinctions below.

The project remains a **non-preregistered secondary analysis**. Versioned decisions
are reproducibility records. Null, low-ceiling, heterogeneous and unfavorable results
do not prevent later phases. Data access and computational integrity are separate.

## Claim-to-evidence assessment

| ID | Claim or promised analysis | Evidence and defect | Action/status |
|---|---|---|---|
| C01 | A connected construct graph is overidentified | Proposal editorial proposition and §5.8. Connectivity alone does not identify latent scales, transport measurement links or establish invariance across disjoint people and tasks. | Narrow to complementary constraints. Explicit measurement anchors, rank/parameter checks and held-out transport are still required. |
| C02 | M0–M4 test the full candidate architectures | `models/architectures.py`: M0 averages standardized columns with fixed equal loadings, M1 fixes its logistic gate, M2 fixes the access average, M3 lacks the proposed regional/temporal shrinkage, M4 sums rank-one components rather than fitting arbitrary correlated loadings. | Each approximation is now named in configuration and outputs. Full fitted alternatives remain indispensable before interpreting a win as rejection of a general unitary/nested account. |
| C03 | Held-out ELPD / PCM is the implemented primary score | `models/fit.py` scores Gaussian marginals with one variance; `models/pcm.py` is not called by the canonical scorer. RDM pair dependence is not modeled. | Label the implemented score mean Gaussian marginal log score in nats/pair, not joint ELPD. Primary PCM and predictive calibration remain unimplemented end-to-end. |
| C04 | Fair model comparison | Synthesis selected the strongest M0–M3 using their test scores, then treated the selected contrast as fixed. This is test-dependent selection, not a nested comparator; its direction of bias is not automatically pro-M4. | Replaced by all configured M4–M0/M1/M2/M3 comparisons and a separate M4–M5 benchmark. No inferential winner is selected on the test set. |
| C05 | Independent participant evidence | Canonical archives lacked train/test identities. Inner tuning and uncertainty treated arbitrary RDM rows as independent replicates. | v2 requires real independent-group IDs, disjoint splits and declared units. Both training and test RDMs aggregate within group before fitting/scoring. Duplicate identical rows do not add weight. Run-only dense analyses need a separate nested participant-aware contract. |
| C06 | Equal-family synthesis | `random_effects_normal` actually uses inverse-variance random-effects weighting; one row per family is not equal weighting. Single-row SE was invented as 1.0 and zero SEs were floored. | Arithmetic 1/F weighting for the finite available-family estimand. Missing uncertainty remains null. Old precision-weighted helper is accurately labeled and no longer the primary path. |
| C07 | Calibrated held-out scoring | Variance came from training-fit residuals, particularly optimistic for M5. | Estimate prediction-error variance from leave-one-training-group-out predictions, retuning within each calibration fold; never use test outcomes for fitting. This remains an approximate plug-in marginal score, not a fully Bayesian predictive distribution. |
| C08 | All models and families retained | M1/M2 require K, so E/A/R-only designs could abort the whole family. | Keep explicit `not_estimable` candidates and unavailable comparison rows; do not invent missing K or replace missing E with zero. Report aliases/zero components without outcome-dependent removal. |
| C09 | Valid robustness/influence | Each construct was independently shuffled, destroying inter-construct correlation; influence removed one row instead of a whole participant. | Use one shared condition permutation and whole-group influence. Label the single shuffle descriptive, not a permutation P value. Design-specific exchangeability and repeated null draws remain necessary. |
| C10 | Stable constrained fitting | Zero columns with alpha=0 could divide by zero; intercept optimization and degrees-of-freedom calculations were not consistently centered. | Center the objective, handle null columns, report nonconvergence, and compute active-design degrees of freedom after centering. |
| C11 | Generalization to an unseen family | The synthesis merely pools within-family scores; it never predicts an omitted family. | Explicit `not_implemented` status. Pooling and leave-one-family-out prediction must not be conflated. |
| C12 | Measurement uncertainty is propagated | Ordered-logit primitives exist, but no full participant/site latent model, cross-fitted E draws or integrated scoring is wired into P07. A table fitted once on all outer-training data is not inner-fold-local. | Remains an implementation priority. Generic v2 only accepts fixed designs; empirical measurement tables require a future fold-specific interface. A provenance declaration is not proof that upstream labels satisfy it. |

All six model IDs are retained for traceability. M5 is a training-group mean-RDM
benchmark, not a guaranteed upper bound, theoretical winner, or proof of explainable
variance. Do not form an unvalidated ratio of log scores and call it fraction explained.

## Dataset-specific interpretive risks

| Family | Required distinction / feasible remedy |
|---|---|
| Working memory | PAS is a report, not calibrated proof of E=0. Fit joint awareness/performance measurement with cue-absent controls, response bias and site/participant effects. Do not define K_memory from correctness and then predict that same correctness. Keep behavior separate from neural RDM synthesis. |
| Masked-content fMRI | Seven participants cannot be replaced by thousands of trial-level independent samples. Content category is confounded with stimulus structure; use cross-run/cross-stimulus checks where possible. Neural K_content predictors must not be extracted from the very neural outcome being evaluated. |
| BMVP | Cross-fitting ocular calibration removes training overlap but does not establish report-to-no-report measurement invariance. Preserve calibration uncertainty and test context shift. Adjusting for the very eye features defining E can also remove or distort the estimand; make that causal/measurement choice explicit. |
| COGITATE | The suprathreshold task principally constrains task, sensory and response effects; it does not identify experience variation. Three modality cohorts remain one experimental family, with patient—not contact—replication for iEEG. |
| Propofol volition | Dose, time/order, motor response and imagery expression are different variables. Independently trained localizers and matched-dose loss/recovery contrasts constrain alternatives. Do not treat failed localizer detection as proof of absent volition or use it as a scientific exclusion gate. |
| DREAM | A registry download is not acquisition of its constituent signals. Keep within-stage comparisons, missing-report patterns and recall ambiguity explicit. Spectral arousal covariates extracted from the same EEG features being predicted require an explicit, noncircular estimand. |
| Propofol awakening EEG | Sparse no-experience observations and failed reports require participant-level uncertainty and missingness sensitivity. Report timing must match the neural window; TMS/spontaneous recordings are not automatically interchangeable. |

Symmetric RDM geometry cannot establish whether E causes K or K causes E. Temporal
precedence does not resolve that on its own. Also, K_task and K_volition are different
operations: transferring between them is a test of a proposed shared cognitive
component, not automatically "within-construct replication". Keep those components
distinct and report operation-specific results.

## What the revised summary estimates

For each fixed comparison, subtract scores within the same independent test group,
average those paired differences within family, and average the resulting family
effects with exactly 1/F weight. The SE is the sample SE of group differences; a
single group has no estimated SE. For the finite-family average, conditional variance
is the sum of family SE-squared values divided by F-squared, assuming independent
families. Any missing family SE makes the aggregate interval unavailable.

The normal intervals are descriptive and conditional on the fitted training models,
fixed conditions and given measurement links. They omit training-refit, condition-
sampling and latent-measurement uncertainty. They are neither credible intervals nor
new-paradigm prediction intervals. All comparisons are shown; there is no multiplicity-
adjusted joint significance claim. Different comparisons may involve different
available-family sets, which are listed explicitly and must not be compared as if
their coverage were identical. Shared participants or source cohorts across families
require deduplication/dependency modeling before an independent-family interval is used.

## Implementation roadmap mapped to existing phases

1. **P03–P04: data identity and estimands.** Finish source-schema fixtures and adapters,
   record nested participant/site/run IDs, verify report timing and construct support,
   and specify allowed contrasts without inspecting neural effect direction. Retain
   unavailable families in the coverage ledger.
2. **P04–P07: measurement and model fidelity.** Implement train-only hierarchical
   ordinal/binary measurement links and uncertainty integration. Score mixtures with
   appropriate predictive integration (not a naive average of log densities or
   mechanical Rubin rules for every score). Fit learned-loadings M0 and flexible
   M1/M2 alternatives and a correlated-component model with matched sensory terms.
3. **P05: independent stress tests.** Add null, partial, correlated and misspecified
   generative processes, variable rank-one loadings, realistic participant noise,
   imbalance and missing reports. The existing generator uses the same component
   functions as the fitter: successful recovery is a code-consistency test, not
   broad identifiability or type-I-error validation. Retain every recovery outcome.
4. **P06–P07: real predictive model.** Wire validated modality features, covariance-aware
   PCM/encoding likelihoods and identical nested splits; benchmark against trusted
   implementations. Crossnobis remains a complementary summary. Add full refit
   resampling for training and subject/condition uncertainty.
5. **P08: actual transport.** Specify common anchors and units; train shared parameters
   excluding the target family; declare whether any target calibration is allowed;
   then score untouched target outcomes. This is distinct from leave-one-family-out
   sensitivity of an average. Report failures of transport as results.
6. **P09–P10: calibrated claims.** Implement constrained exchangeability, multiplicity,
   measurement/missingness sensitivity and practical-equivalence margins with
   substantive meaning. Produce claim-linked estimates and uncertainty, not a
   significance-based journal decision tree.

No step requires a favorable scientific result. None of these analysis phases is
authorized for server deployment under the current instruction.

## Primary literature checked

- Diedrichsen & Kriegeskorte (2017), abstract and framework: PCM/encoding/RSA are
  related but distinct; dependencies among distances matter. Supports C03, not the
  validity of this project's particular models. [PLOS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005508).
- Schütt et al. (2023), discussion/generalization methods: subject and condition
  sampling define different generalization claims; flexible models require appropriate
  crossvalidation. Supports C05 and the uncertainty roadmap. [eLife](https://elifesciences.org/articles/82566).
- COGITATE Consortium et al. (2025), abstract: suprathreshold perception, multimodal
  observations and specified divergent theory predictions. Context for the source
  experiment, not a registration or theory-validation claim for this secondary study.
  [Nature](https://www.nature.com/articles/s41586-025-08888-1).
- Wong et al. (2025), database description/discussion: standardized dream data and
  metadata facilitate reuse; a registry is not equivalent to all underlying data.
  [Nature Communications](https://www.nature.com/articles/s41467-025-61945-1).

## Verification and handoff

See `docs/SCIENTIFIC_REVIEW_VALIDATION.md` for executed checks. No real-data effect
estimate, participant-level conclusion or full P03–P10 operational completion is
claimed. Original proposal and prior results are preserved. Server acquisitions
were not changed, restarted or redeployed by this review.
