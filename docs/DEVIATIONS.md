# Analysis and implementation deviations

This ledger is part of the transparent non-preregistered record. Add entries chronologically; never rewrite an old entry to make a later choice appear prospective.

## 2026-08-30 — Initial implementation status

- **Source:** proposal dated 2026-08-30.
- **Change:** removed registration, preregistration, hidden lockbox, one-time confirmatory-run, and scientific gate language.
- **Reason:** explicit owner instruction. The study is a transparent non-preregistered secondary analysis.
- **Consequence:** configurations remain versioned and all changes/results are retained, but no claim of prospective registration is made and data are never deliberately hidden from the owner.

## 2026-08-30 — Server execution model

- **Source expectation:** Slurm, 5 TB fast scratch, containerized execution.
- **Observed:** H100 host with 256 logical CPUs and ~1 TiB RAM; no Slurm; Docker client exists but the user cannot access the daemon; `/data1` has ~2.3 TB free, NAS ~9.6 TB.
- **Change:** use NAS-first raw storage, bounded staging, Python virtual environments, `tmux`, file locks, logs, and atomic markers.
- **Consequence:** same scientific workflow, different scheduler/storage implementation.

## 2026-08-30 — Dataset access reality

- **Change:** COGITATE is represented as `WAITING_ACCESS`; DREAM is handled per constituent access state.
- **Reason:** COGITATE requires a user-created account and acceptance of terms; DREAM combines open and restricted packages.
- **Consequence:** public-family acquisition proceeds; unavailable families remain explicit and may enter later without replacing or suppressing earlier results.

## 2026-08-30 — Acquisition-only server deployment

- **Owner instruction:** after scripts are written, do not deploy anything except data acquisition.
- **Change:** use a commit-pinned sparse release containing only acquisition modules, configuration,
  and P01/P02 runners. Keep P03-P10 source in GitHub/local storage only.
- **Consequence:** the full roadmap and analysis implementation remain reproducible but are neither
  deployed nor queued until the owner explicitly expands server authorization.
