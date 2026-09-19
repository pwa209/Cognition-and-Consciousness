# Same-model report sampler repair (2026-09-19)

This is a computational revision in a transparent non-preregistered secondary
analysis, not a scientific gate. The initial posterior and fixed longer Gibbs run
remain immutable and must not be interpreted as converged inference.

## Diagnosis

The extended run 21417467 has worst rank/folded split R-hat 1.2876434610 and
custom minimum bulk ESS 11.44986. An independent ArviZ 0.22.0 audit reproduced
R-hat exactly and gave bulk ESS 11.45541. The upper ordinal threshold has those
worst diagnostics (tail ESS 34.42945). Its slow mixing is not an artifact of the
custom diagnostic calculator. The frame-duration coefficient also has R-hat
1.00996 and bulk ESS 562.37; diagnostics do not establish substantive validity.

## Revision and equivalence

Use PyMC 5.24.0 NUTS on the analytically marginalized ordered-probit likelihood.
The old sampler conditions the threshold on thousands of latent trial liabilities;
marginalization removes that narrow conditional sampling step. Subject and context
effects retain their original hierarchy without a sum-to-zero constraint. Exact repeated likelihood
terms are count-weighted (no averaging or binning).

Unchanged: two reserved calibration participants, five evaluation participants,
fixed-unit non-neural predictors, missing-report treatment, common thresholds,
fixed zero first threshold, residual SD one, beta N(0,2.5^2), independent
subject/context effects with InvGamma(2,1) variance priors, and upper threshold
N(1,2^2) restricted above zero. No neural evaluation values enter calibration.
The empirical budget is four chains, 4,000 warmup and 4,000 retained draws each,
seed 260830, full mass-matrix adaptation. The first implementation used noncentered
effects and target acceptance 0.95. Its hierarchical synthetic test exposed 26
divergences, bulk ESS 391.69 and tail ESS 273.55 despite R-hat 1.00918. Its threshold
95% interval missed the generating value; that observation is retained, not used
to choose the parameterization or treated as a coverage estimate. The scalar
quadrature benchmark passed and all 218 server tests passed. Qualification SUCCESS
in that initial release meant implementation checks completed, not clean sampling.

The revised plan uses **centered effects, target acceptance 0.99**, and 2,000
warmup/retained draws per chain for synthetic qualification. This is a coordinate
change with identical priors, supported by separate density/Jacobian/gradient tests
for both forms. Synthetic numerical warnings now stop that sampler's qualification
after saving all diagnostics; generating-value coverage never determines acceptance.
The initial empirical NUTS attempt remains preserved. No empirical effect size,
sign, or favored architecture is used to select the revision.

That initial empirical job 21420707 finished in 3m40s. R-hat improved to 1.00307,
minimum bulk ESS to 2135.85, and minimum tail ESS to 950.39, but **216 divergences**
remained. It is not certified for interpretation. The revised centered plan had
already been chosen from the synthetic warnings before these empirical diagnostics
were read. All 3,447 reserved trial rows remain: 3,295 observed reports and 152
missing reports; exact likelihood compression gives 501 distinct observed terms.

## Technical qualification and lifecycle

`tests/unit/test_report_nuts.py` compares compressed/uncompressed likelihoods,
prior change-of-variable identity, PyMC density against an independent SciPy
joint evaluator, gradients against finite differences, and diagnostic behavior.
PyMC/ArviZ tests are optional locally but dependencies are mandatory in the
isolated server qualification environment. That job runs the full test suite,
a scalar NUTS-versus-quadrature benchmark, and a synthetic hierarchical recovery
exercise. Recovery intervals and diagnostics are retained even if unfavorable;
one realization is not a coverage study. Empirical results never select the
sampler budget or determine whether unrelated preprocessing continues.

`repair_masked_report.py` verifies source and input hashes, original preparation,
and identical scientific configuration before reading only reserved report inputs.
Attempts have atomic status/provenance, output hashes, and distinct retry paths.
The two old posteriors get private parameter-wise ArviZ audits. New diagnostics
include R-hat, bulk/tail ESS, mean MCSE, chain drift summaries, divergences, BFMI
and maximum-tree-depth events. Unexpected constant parameters are flagged, not
silently removed. Only the fixed threshold anchor is excluded from diagnostics.

`submit_report_nuts.py` uses durable no-duplicate scheduler receipts:
QUALIFY_NUTS -> CALIBRATE_NUTS. All mutable storage is under the study's personal
20 TB scratch root. MRI jobs are neither canceled nor resubmitted.

## Scope and remaining limits

Passing sampler diagnostics does not establish a universal consciousness scale,
separate E from stimulus strength, validate report truth, or solve the two-subject
calibration limitation. Neural-noise calibration, event alignment, raw-to-pattern
integration and empirical P06–P10 remain separate unfinished work. No current
successful sampling result is claimed until execution receipts exist.

## Deployment receipt

At 17:35 UTC, source release `09cf7b2cdef8e96d65a233a017745b803198143a`
was installed with all 216 source-file hashes verified. Local validation: 216 tests
passed, two optional PyMC/ArviZ tests skipped because those packages are absent
locally; Bash syntax and lint checks passed. Slurm accepted QUALIFY_NUTS **21420706**
and dependent CALIBRATE_NUTS **21420707**. At 17:35:53 UTC qualification was running
on rc32026 and calibration was pending its technical predecessor. MRI pilot 21417199
remained running; array 21417200 remained pending the MRI pilot. Neither was changed.
All posterior draws remain private on personal scratch; Git contains code and
aggregate operational receipts only.

Implementation references: [PyMC OrderedProbit](https://www.pymc.io/projects/docs/en/v5.24.0/api/distributions/generated/pymc.OrderedProbit.html)
and [ArviZ diagnostics](https://python.arviz.org/en/v0.22.0/api/generated/arviz.summary.html).
