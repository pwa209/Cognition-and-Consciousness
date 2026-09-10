# Inactive server source snapshot — c1a6e64

- Owner authorization: stage the updated analysis scripts only; do not activate them
  or launch any analysis jobs.
- Completed: 2026-09-10 19:38:17 UTC.
- Verified host/account: `kemove-Rack-Server` / `wangpeng`.
- Source commit: `c1a6e6479c7ace967bfcf070cf2e27ef382b1c18`.
- Local Git tree: `a49011b6452358aac1012db6a1187cbaea1d6807`.
- Status: **STAGED_NOT_ACTIVATED**.

## Locations

Inactive repository snapshot:

```text
/data1/wangpeng/cognition-and-consciousness-work/source/staged-releases/c1a6e6479c7ace967bfcf070cf2e27ef382b1c18/repository
```

Its parent directory contains `STAGING_STATUS.json`, `SOURCE_INVENTORY.json`, and
`STAGED_ONLY.txt`. This is an extracted source snapshot, not a Git working clone.

Existing active acquisition source, left unchanged:

```text
/data1/wangpeng/cognition-and-consciousness-work/source/current
```

No `current` link or directory was changed. No source was written to the raw-data
root, and no restart root was created. The original configuration still records the
proposed-root status; this staging approval does not silently confirm all three roots.

## Verification performed

- A local `git archive` was generated from the exact commit, not from uncommitted files.
- The 1,177,600-byte archive was transferred over authenticated SSH.
- Remote archive SHA-256 matched the locally generated archive:
  `a4ed41ef7b48f12e31bfa26ce1a7dc9a192b99d0ab0f269316c60ee4db412d78`.
- The archive's Git commit annotation matched the requested commit.
- All 141 tracked files were extracted with path-traversal, link, special-file and
  duplicate-file rejection; each written file was reread and checked against the
  hash-verified archive. Per-file SHA-256 and Git-blob SHA-1 values are in the inventory.
- All 90 Python files passed `ast.parse` syntax checks without importing/executing
  project code or creating a scientific environment.
- SHA-256 values for all 94 checked active source/configuration/script files remained
  unchanged from the pre-transfer inventory. The tmux session-name list was unchanged.
- The completed directory was published by a same-filesystem atomic rename.
- Local full regression suite before the tracking commit: **118 passed in 53.64 s**.
  The test suite was not executed on the server.

## Transfer recovery record

The initial server-side GitHub fetch timed out after 90 seconds. The final release
did not exist, and a process check found no matching remaining Git fetch helper
before the alternate transfer. No destructive cleanup was performed.

The failed attempt remains under:

```text
/data1/wangpeng/cognition-and-consciousness-work/source/staged-releases/.staging-c1a6e6479c7ace967bfcf070cf2e27ef382b1c18
```

It contains a `STAGING_FAILED` record. The successful SSH-transferred archive is
retained alongside the final release as `<commit>.tar`. This evidence is distinct
from the completed inactive snapshot and is not an active release.

## Explicitly not performed

No analysis activation, environment installation, P03–P10 run, GPU/CPU analysis job,
download restart, acquisition-release replacement, system update or credential
storage was performed. There is no new job/session identifier because no job was
launched. Numerical tests from the previous implementation review remain local
evidence, not a claim of empirical or production server readiness.

This tracking document is a later documentation change; the staged scientific source
remains pinned to `c1a6e64`, not automatically advanced to the documentation commit.
