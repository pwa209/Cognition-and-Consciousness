# P10 structural bootstrap repair (28 September 2026)

The completed masked-fMRI bootstrap has 1,000 hash-bound P09 attempts. Of these,
887 returned paired model contrasts and 113 returned the same structural failure:
fewer than three independent groups in a resampled family. The original P10
report and all failed draws remain immutable provenance.

The repair will retain every originally estimable draw and deterministically
redraw only the 113 structurally invalid group-multiplicity vectors until each
family has at least three distinct groups. This changes the reported bootstrap
target to the distribution of the nested estimator conditional on structural
estimability. It does not create unconditional uncertainty or validate population
coverage from five evaluation participants. New attempts and the new P10 report
must be separately versioned and labeled; no model result determines redraws.

The original seed is 260830 and the five-participant draw is indexed by
`SeedSequence([seed, replicate])`. Recomputing only its group counts locally
produces exactly 113 structurally invalid IDs among 1,000, matching the
hash-bound P10 reason census; this check uses no neural observations or scores.
Each failed ID retains its original multiplicity vector. Its new stream starts
at `SeedSequence([seed, replicate, 1])`, increments the final counter only
while the group-count condition is unmet, and stops at the first structurally
valid draw. Numerical/model failures are recorded, not redrawn. The unchanged
887 initial valid vectors plus these 113 accepted redraws are samples from the
bootstrap distribution conditional on that structural event. The initial
failure fraction, source hashes, original P10 job and exact result-path mapping
are included in the new report provenance.

The new interval is an unadjusted percentile summary at fixed families,
conditions and external calibration. It is not a validated small-sample
coverage statement, an unconditional interval, or a multi-family P08 result.
