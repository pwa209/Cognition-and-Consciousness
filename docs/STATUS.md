# Project status

Last updated: 2026-09-10

## Current scientific implementation

Scientific review and local revisions are documented in
`SCIENTIFIC_REVIEW_2026-09-10.md`, with executed checks in
`SCIENTIFIC_REVIEW_VALIDATION.md`. The canonical component-RDM prototype now uses
independent-group identities, fixed pairwise comparisons and genuinely equal-family
summaries. Full latent measurement/architectures, P06 producers and P08 LOFO transfer
remain unfinished. No analysis was deployed or queued by this revision.

The read-only server check earlier on September 10 found working memory and propofol
awakening EEG download records complete; masked fMRI, BMVP and propofol-volition
acquisition remained partial, DREAM had only its registry, and COGITATE was waiting
for access. The historical "not started" entries below are not the current acquisition
status. Local root-confirmation configuration was not changed by this review.

## Historical record — 2026-08-30

| Area | State | Evidence / next action |
|---|---|---|
| Proposal review | complete | 43 pages rendered and visually reviewed; methods extracted into config contracts |
| Study designation | complete | transparent non-preregistered secondary analysis; no scientific gates |
| Local repository | implemented core | acquisition is operational; P03-P10 contracts/core methods are drafted; 51 tests and Ruff checks pass |
| Dataset-specific analysis adapters | pending raw-schema validation | exact P06 producers remain explicit rather than guessing before downloads; not deployed |
| GitHub | current | acquisition-hardened release `e49bb2b` pushed to `main` |
| Server connection | verified | expected hostname/user, H100, CPU, RAM, storage, outbound sources |
| Server roots | awaiting owner confirmation | proposed paths are in `conf/server_h100.yaml`; no remote project writes yet |
| Server deployment scope | acquisition only | owner instructed that P03-P10 must not be deployed or queued |
| Public data manifest | ready to queue | pinned source IDs/versions and per-file P01 resolvers implemented |
| Bulk acquisition | not started | sparse acquisition deployment and P01/P02 queue await root confirmation |
| COGITATE | waiting access | owner-created account and terms acceptance required |
| DREAM | source blocked | upstream final object host currently fails verified TLS; no insecure bypass |
