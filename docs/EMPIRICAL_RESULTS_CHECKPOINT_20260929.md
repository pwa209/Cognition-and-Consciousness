# Empirical results checkpoint — 29 September 2026

This is a non-preregistered secondary-analysis checkpoint, not a claim that the
full study or cross-family test is complete. It records aggregate findings and
provenance only; participant-level data and raw downloads are not committed.

## Completed masked-content fMRI lane

The within-family P07 evaluation used five evaluation participants and two
independent calibration participants. All 30 participant-by-model rows (M0–M5)
were scored. Mean held-out Gaussian log predictive scores in nats per scored
neural dimension (higher is better) were:

| Candidate | Mean score |
| --- | ---: |
| M0 unitary | -1.3166231 |
| M1 experience-gating | -1.3010708 |
| M2 cognitive-access | -1.3264497 |
| M3 report-bottleneck | -1.3290749 |
| M4 factorized-interactive | -1.3101646 |
| M5 saturated within-family reference | -1.1664690 |

The P09 technical repair retained the 887 originally scored participant
bootstrap draws. Its 113 original structural failures were redrawn under a
fixed rule requiring at least three distinct participant groups per family;
112 first redraws succeeded and quota-failed replicate 914 was recomputed
without changing its seed or scientific configuration. P09 job `21991093_914`
completed; P10 job `21991095` reported 1,000/1,000 completed conditional draws
for each comparison. P10 status was `SUCCESS`, and the SHA-256 of its `result.json`
matched the status receipt:
`d2be63b7de147a7bc611c66fccb6c9d7c2e43a8c3e5128c92abd76ac155430d9`.

| Paired contrast (M4 minus comparator) | Point estimate | Conditional percentile 95% interval |
| --- | ---: | ---: |
| M4–M0 | 0.0064585 | [-0.0932194, 0.0163211] |
| M4–M1 | -0.0090938 | [-0.1035079, 0.1182119] |
| M4–M2 | 0.0162851 | [-0.0715283, 0.0394981] |
| M4–M3 | 0.0189103 | [-0.2050455, 0.0607378] |
| M4–M5 | -0.1436956 | [-0.2665013, -0.0733715] |

These are paired nats per scored dimension at fixed conditions, fixed family,
and fixed external calibration. Intervals are unadjusted and conditional on
the three-distinct-group redraw rule, not unconditional intervals or validated
five-participant population-coverage intervals. No equivalence test was run.
M1 has the highest descriptive score among M0–M4, and M5 has the highest
score overall. The M4 comparisons with M0–M3 do not establish a superior
structured architecture. M5 is a flexible within-family benchmark, not a
noise ceiling or a biologically identified mechanism.

## Cross-family status and reproducibility boundary

The existing P08 receipt is `NOT_APPLICABLE: LOFO requires >=2 families`.
BMVP preparation does not yet provide a second verified neural/measurement
bundle or independent shared E/feature scale, so there is no cross-family
result. BMVP also lacks the K_content assay required for the original full
E–K_content–R transfer; a narrower exploratory E–R transfer remains a
separate, unfinished analysis. This is a technical estimability limitation,
not a result-dependent scientific gate.

The detailed P10 output was under personal Rorqual scratch at
`/scratch/pwa209/cognition-and-consciousness/fresh-20260916/analysis/downstream/P10/21991095`.
This repository records aggregate statistics and code, not raw recordings,
participant-level model scores, the 1,000 per-draw outputs, or private files.
Those would be lost if the entire Rorqual study root were deleted without a
separate backup; rerunning would require reacquisition and recomputation.
