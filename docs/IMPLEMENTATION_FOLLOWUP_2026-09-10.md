# Follow-up implementation and remaining evidence requirements

Status: transparent **non-preregistered** secondary analysis; no scientific gates.
Scope: local analysis source, tests and documentation. **No P03–P10 deployment or
analysis jobs on the university server.** No participant recordings were copied locally.

## What changed

| Review gap | Implementation now provided | Remaining boundary |
|---|---|---|
| Fixed architectural proxies | Separate fitted generative M0–M5 engine, including signed M0 loadings, fitted strict/partial M1 gate, constrained M2 access/A span, penalized M3 report effects, correlated M4 covariance and free within-family M5 | These are explicit operational models, not exhaustive formalizations of every consciousness theory. M3 is not a region-specific hierarchical report model. |
| Marginal RDM score mislabeled as full prediction | Joint Gaussian density of repeated-partition condition contrasts, with known partition-condition noise covariance | Requires valid independently calibrated channel whitening and noise design. Gaussian residuals/channel independence remain assumptions. |
| Measurement uncertainty absent | Hierarchical ordinal-probit posterior with subject/context effects, sampled thresholds/variances, posterior prediction, log-mean-exp integration in neural scores | E is an operational report-liability probability, not ground-truth consciousness. This is modular external calibration, not a joint behavioral-neural latent model or within-neural-subject cross-fitting. |
| LOFO was only sensitivity of an average | Actual source-only fitting/tuning followed by untouched target-family scoring | Requires common independently justified anchors/units and source support. M5 is retained as non-transferable, not assigned an invented cross-family ceiling. |
| Training-refit uncertainty missing | Full nested evaluator refit in a within-family subject bootstrap; repeated subjects use weights with original IDs | Fixed conditions/families. External calibration is integrated but not bootstrap-refitted. No new-condition/general-population or simultaneous coverage claim. |
| Invariance/missingness assumptions implicit | Common versus context-specific threshold prediction on disjoint report subjects; fixed log-odds pattern-mixture sensitivity | These procedures examine assumptions; they do not establish invariance or identify MNAR from observed data alone. |
| Multiplicity/equivalence missing | Holm adjustment, shared-sign max-|t| and TOST functions, with unit/exchangeability assumptions documented | Do not apply independent-unit sign tests to dependent CV folds. A calibrated simultaneous pattern-inference workflow is still unconnected. |
| Matched-generator recovery only | Independent neural-pattern and report generators; signed-unitary, correlated, aliased, heavy-tail, MAR, MNAR and context-noninvariance scenarios | Local smoke checks are not a completed power, coverage or false-positive validation campaign. |
| Dataset schema mapping gaps | ds003927 verified-column adapter, categorical visibility preserved, missing reports unknown, traversal/count/parser tests | Other raw-to-feature adapters/report linkages still need source-specific validation. |
| Spectral scaling defect | Correct one-sided Hann PSD normalization, checked against SciPy for odd/even windows | Does not validate the complete EEG preprocessing/feature pipeline. |

The historical `model score` RDM command remains a separate prototype. Never merge
its scores with new `patterns` joint-density outputs. Every candidate, including
unavailable and numerical-failure rows, remains in the new outputs. A null or poor
score does not stop subsequent phases.

## Model and estimand details

Patterns have axes independent-group × partition × condition × feature. Each group
has independent random neural loadings, shared across its partitions. Per-partition
Helmert contrasts remove feature baselines; they do not select windows or ROIs.
The likelihood integrates these random loadings. Architecture parameters are fitted
by multistart penalized maximum likelihood, not integrated as a Bayesian posterior.
External design draws are integrated per-group using log-mean-exp. The fitting
objective averages normalized group predictive losses within family, then averages
families; this is not labeled an unweighted joint posterior across all subjects.

All candidates share the sensory covariance and noise-scale terms. The default
M4 covariance uses a lower-triangular factor permitting correlated construct and
declared interaction directions. It can be rank deficient. M5 is a free PSD
covariance in condition-contrast space, not a guaranteed ceiling. The pattern model
follows the random-pattern Gaussian framework, with its independence/whitening
assumptions made explicit. [PCM statistical model](https://pcm-toolbox-python.readthedocs.io/en/latest/model_statistical.html),
[PCM model classes](https://pcm-toolbox-python.readthedocs.io/en/latest/model_type.html).

The report sampler uses truncated-normal latent augmentation, Gaussian regression
updates, variance updates, and ordered-threshold updates. The first threshold is
fixed at zero and residual SD at one. Predictor units are fixed externally. Priors
are versioned in `analysis_spec.yaml`. These anchors identify the operational
liability scale; they do not validate a consciousness scale. [Albert & Chib, 1993](https://www.stat.cmu.edu/~brian/905-2009/all-papers/albert-chib-1993.pdf).

Rank/folded split R-hat and bulk ESS estimates are included. They do not replace
tail diagnostics, posterior predictive checks, independent sampler benchmarking or
simulation-based calibration. Short test chains deliberately exercise serialization
and sampling only. [Vehtari et al.](https://arxiv.org/abs/1903.08008).

Subject-bootstrap copies never get new fake subject IDs. A sampled subject is
represented once with an integer weight, so all copies leave an inner/outer fold
together. Every bootstrap replicate refits tuning and model parameters. If any
replicate cannot produce a complete comparison, its failure is retained and that
interval is unavailable; it is not silently conditioned on successful fits. Conditions
are fixed: this is not the corrected two-factor subject/condition bootstrap.
[Generalization over subjects and conditions](https://elifesciences.org/articles/82566).

## Read-only source-schema findings

On 2026-09-10 the university server was inspected read-only, then disconnected.
No downloads, analysis deployments or jobs were changed during this follow-up.

- **Masked fMRI ds003927 1.0.3:** verified `visibility`, `targets`, `labels`, `paths`,
  `response`, `correct`, `RT_response`, `options` and timing columns. Source visibility
  labels `unconscious`, `glimpse`, `conscious` are ordinal report categories, never
  E=0/0.5/1. `RT_response` units were not established by the inspected header; raw
  values remain metadata and are not silently treated as seconds.
- **Propofol awakening EEG ds005620 1.0.0:** BrainVision layout and `sed2` minute-before-
  awakening convention found in README. Event columns contain markers, not a verified
  experience-report linkage. Missing report tables cannot be reconstructed by guessing.
  README lists CC-BY-4.0, dataset description lists CC0: license conflict remains open.
- **Propofol volition ds006623 1.0.0:** README describes imagery, force and dose data,
  but no actual events TSV was found in the inspected downloaded subset. No behavior/
  dose/force schema is certified from that description alone.
- DREAM constituent access and COGITATE account/terms requirements remain separate
  from software work. No access controls have been bypassed.

## Phase roadmap and readiness

| Phase | Local implementation / next action | Ready for full empirical execution? |
|---|---|---|
| P01–P02 acquisition | Existing acquisition-only release; this change does not refresh acquisition completion | Separate acquisition status, not changed here |
| P03 validation | BIDS timing correction; masked parser/count/path fixtures | Not all family schemas verified |
| P04 harmonization/measurement | Masked/WM harmonizers; `measurement`; invariance and missingness APIs | Report links, external calibration cohorts and predictor definitions still required |
| P05 identifiability | `stress` with two versioned plans; independent generators | Full simulation campaign and simultaneous inference calibration not completed |
| P06 features | Independently calibrated pattern whitening/assembly API; PSD correction | No certified raw-to-pattern producer for all modalities/families |
| P07 models | `patterns --mode within`; optional full-refit subject bootstrap | Executable on validated pattern files, tested on synthetic fixtures |
| P08 transport | `patterns --mode lofo` | Executable only for justified common anchors/support; cross-modality comparability not established |
| P09 robustness | Invariance/MNAR, bootstrap, Holm/max-t/TOST APIs | Dataset-specific exchangeability, margins, corrected condition resampling and calibrated joint testing outstanding |
| P10 reporting | Keep operational definitions and limitations visible | No real-data findings or journal-readiness claim |

Unavailable scientific effects are not a gate. Missing data identity, invalid
calibration separation, corrupt inputs or unsupported inference may make an affected
analysis non-estimable without stopping unrelated valid analyses.

## What cannot honestly be marked solved

Full raw-data-to-manuscript execution, within-neural-subject fold-local measurement,
all seven validated feature adapters, universal E measurement invariance, causal
direction E↔K, corrected subject/condition uncertainty, simultaneous inferential
calibration, full simulation coverage/power and production restart/concurrency
certification remain open. Some require more implementation; others require source
data, calibration design or evidence that no amount of scripting can manufacture.

This is a substantial local implementation advance, **not a declaration that every
problem is closed**. Nothing here authorizes analysis deployment.
