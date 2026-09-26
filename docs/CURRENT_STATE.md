# Current study state (26 September 2026)

This is the maintained GitHub handoff for the transparent, non-preregistered
secondary analysis. It is a timestamped snapshot, **not** a live scheduler or
participant-data mirror. No scientific result is a stopping gate.

## Where to resume

- Rorqual account/host: `pwa209` on `rorqual.alliancecan.ca`. Authenticate
  interactively with password and Duo/OTP; never place either in Git, a command,
  or a log. Verify `id -un` and `hostname -f` before remote actions.
- Personal study root: `/scratch/pwa209/cognition-and-consciousness/fresh-20260916`.
  All data, caches, temporary files and derivatives stay under personal
  `/scratch`, never shared `/project`. Check fresh personal quota before new jobs.
- Local code can be freshly cloned from the GitHub repository; the latest
  work need not be recovered from `D:`. Keep the same Git branch/commit identity
  when matching an immutable Rorqual release. `scripts/alliance/prepare_release.py`
  is the versioned source-deployment mechanism; never overwrite a release.
- Consult [the phase roadmap](ROADMAP.md), [P08 compatibility audit](P08_BMVP_COMPATIBILITY_AUDIT_20260925.md),
  [empirical evidence checkpoint](EMPIRICAL_RESULTS_CHECKPOINT_20260925.md),
  [deviations](DEVIATIONS.md), and [today's P09 recovery record](REMOTE_STATE_AND_RECOVERY_20260926.md).

## Verified checkpoint

- Masked P06 `21744874` and P07 `21744875` completed. P07 scored all 30
  participant-by-model rows; five evaluation participants are too few for a
  model-winner claim. Existing P08 `21744876` is a hash-verified *single-family
  not-applicable* receipt, not transfer evidence.
- The original P09 packed array is `21744877` (50 tasks × 20 fixed replicate
  IDs). Six tasks—4, 6, 7, 8, 23, 24—failed solely because the personal-quota
  reporting service timed out. Twenty-five successful replicate receipts in
  those six batches are preserved; exactly 95 original replicate IDs need
  new attempts. New-start throttle was reduced from 25 to 8 on 26 September
  to protect the quota service; this changes no scientific setting or seed.
  Original P10 `21744878` was dependency-pending at the last check.
- A dry-run-verified, exact 95-ID P09 retry was submitted as Slurm array
  `21842371` (at most four concurrent four-core tasks) using the unchanged
  analysis release. The latest hash-checked retry receipt census found one
  successful original replicate ID, four running and 90 not started, with no
  retry failure yet; these are time-stamped counts. The
  first attempt to submit a new P10 was rejected by Slurm because its
  dependency named already-completed, aged-out jobs. Its `UNCERTAIN` receipt
  is preserved; scheduler queue/accounting showed **no** first P10 job. A
  separate, hash-guarded P10 submission `21842472` was then accepted and is
  dependency-pending on the original and retry P09 arrays. Its input SHA-256
  is `f3aedcb1c63f79cead4a83ae55c67f9baffded24db441646ce3f82ac41c456ef`.
- All nine BMVP report-MRI conversion jobs `21821871`–`21821879` were Slurm
  COMPLETED with exit code 0. Their per-series status JSONs were also checked:
  all nine say SUCCESS, each lists two hashed output artifacts and one
  `110 × 110 × 64 × 720` image. The underlying NIfTI/JSON bytes have not yet
  been independently rehashed in this session; do not call neural preprocessing
  or BMVP P06 complete.
- There is still no valid multi-family P08 score. The exploratory E–R runner
  now fails closed on missing cross-family anchors; the full E–K_content–R
  transfer is not estimable with BMVP's construct map.

## Immediate operational sequence

1. Monitor P09 retry `21842371` and original array `21744877` by Slurm and
   per-replicate receipts. Preserve all original and retry attempts.
2. When both P09 arrays are terminal, inspect the hash-bound results of
   reconciled P10 `21842472` and its 1,000-ID coverage. The old P10 may
   produce a provisional incomplete report; never erase it. If a technical
   retry task fails, preserve it and reconcile exact missing IDs again.
3. Rehash each of the nine BMVP conversion outputs on a scheduled compute
   node, then continue the separate event-alignment, no-report imaging,
   preprocessing and independent E/R/feature calibration work. Conversion
   alone does not qualify a multi-family P08 fit.

Status claims above are from live `sacct` plus inspected P09 status JSONs on
26 September 2026. A later run must query the scheduler and immutable
receipts again; static GitHub documentation is not a substitute for either.
