# Project status

Last updated: 2026-09-16

## Fresh Compute Canada execution

Rorqual is now deployed on personal 20 TB scratch with separate owner authorization
for acquisition and ready analysis phases. WM acquisition, integrity validation and
harmonization completed; EEG acquisition and P05 simulations are underway. See the
[dated deployment record](ALLIANCE_DEPLOYMENT_STATUS.md) and
[phase roadmap](ALLIANCE_FRESH_RUN.md). University-server state remains unchanged.
The scientific implementation limits below remain applicable; its September 10
deployment statements describe the earlier university-server review, not Rorqual.

## Scientific implementation — September 10 baseline

The follow-up now provides a separate fitted generative-pattern engine, modular
ordinal report measurement, true source-only LOFO, nested subject-bootstrap refits,
independent stress generators and additional adapter/statistical checks. See
`IMPLEMENTATION_FOLLOWUP_2026-09-10.md` for the phase-by-phase implemented/open ledger,
`PATTERN_AND_MEASUREMENT_COMMANDS.md` for command contracts and
`SCIENTIFIC_REVIEW_VALIDATION.md` for executed tests. The historical component-RDM
prototype remains separate. Full raw-to-feature integration, within-neural-subject
measurement cross-fitting, simultaneous inference calibration, shared empirical
anchors and production readiness are not complete. No analysis was deployed or queued.

**Later source-staging authorization, 2026-09-10:** the owner approved an inactive
versioned copy of analysis commit `c1a6e6479c7ace967bfcf070cf2e27ef382b1c18` on the
server. It is staged, not activated; no analysis environment or jobs were created.
See `SERVER_STAGING_c1a6e64.md` for the exact path and integrity checks. The existing
acquisition source and download sessions were left unchanged.

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
