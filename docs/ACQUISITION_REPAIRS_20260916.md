# Acquisition repair release — 2026-09-16

This is acquisition engineering for a non-preregistered secondary analysis. No
scientific model, outcome label, exclusion rule or stopping criterion changes.

## Source corrections

- OpenNeuro: inspect all snapshot-provided URLs. Accept an official dataset-scoped
  SHA256E content key only when its embedded size matches the API and verify the
  embedded SHA-256 after download. Continue accepting immutable S3 version IDs.
  Snapshot Git SHA, reported size, full inventory count and byte totals remain strict.
- DREAM v6: 22 registry rows describe 20 sets, including two historical amendments.
  Select the highest approved amendment by Set ID and preserve superseded rows.
  Resolve public Figshare/Monash DOIs to explicit article versions with file IDs,
  byte counts, MD5 and license metadata. FreiData set 19 uses its exact v1 record,
  published byte count and MD5. Private/revoked/unknown access stays held.
- COGITATE: the owner signed in interactively. Five distinct full Experiment 1
  bundle links returned HTTP 200 from Rorqual. The raw MEEG catalog link duplicates
  raw iEEG and must not be mislabeled or treated as acquired MEEG. MEEG BIDS has a
  separate available link. Experiment 2 is not published in the catalog.
  Private catalog URLs remain outside Git. Pin modality, format, byte size and
  strong ETag; use If-Match for resumed downloads and require the response ETag.
  These bundles have no verified publisher cryptographic checksum; local SHA-256
  records provenance but does not replace a publisher checksum.

## Operation

Command (from a verified same-run source release):

```bash
python scripts/alliance/repair_acquisition.py \
  --root /scratch/pwa209/cognition-and-consciousness/fresh-20260916 \
  --family dream --dry-run
```

Other families: `cogitate` (requires `--catalog` pointing to the private authorized
catalog inside the fresh root) and `propofol_volition_fmri`.
Use `--resolve-only` to freeze and inspect a manifest without downloading payloads;
omit it to acquire. All cache, temporary, download and output paths use personal
scratch. Quota checks retain 500 GB and 50,000 files. One worker per invocation.

The new runner uses `operations/acquisition-repair-v1/FAMILY` for locks, status,
attempt provenance, frozen manifests and download ledgers. It never overwrites
the original campaign's global summary or active acquisition source. Restart
reuses the frozen manifest, byte-bound ledger and partial downloads. A changed
manifest fails closed. A source failure affects its family, not other jobs.
No archives are extracted and no downloaded code is executed by this runner.

Deployment and actual progress must be verified separately; source tests alone do
not establish completion. DREAM set 8 remains private pending owner access.

## Verified deployment and start

Source commit `b2e9e59e8613b7bd4e8f0ba120f49c8678c4564e` was installed as
a new immutable release on Rorqual: 164 source files verified, source archive SHA-256
`bd59cd5aae427d3c0324a57ca5ab62e9f505d01a0aa23c254eba925d816fe26f`.
Local full suite: **140 passed**. Rorqual targeted acquisition/storage/repair suite:
**30 passed**. All three command/config dry runs passed. Synthetic tests cover
failure and success status/provenance and reuse of the frozen manifest on restart.

All three live resolvers completed, with the configured Volition totals unchanged:

| Family | Resolved objects | Bytes | Remaining hold |
|---|---:|---:|---|
| Volition fMRI | 119,120 | 1,578,461,354,264 | None at resolution |
| DREAM | 58 across 19 public sets | 150,734,502,767 | Private set 8 |
| COGITATE Experiment 1 | 5 full bundles | 1,796,597,638,162 | Mislabeled raw-MEEG link |

At **2026-09-16 17:34:46 UTC**, all three repair processes reported DOWNLOADING
on `rorqual3`: DREAM PID 2716231, COGITATE PID 2716232, Volition PID 2716233.
Observed partial bytes were respectively 469,762,048; 310,378,496; and 17,131.
These are transfer observations, **not completed or checksum-verified datasets**.
Each repair uses one low-priority HTTP worker (three total); the original BMVP
worker and the existing analysis jobs were neither stopped nor changed.

The private COGITATE catalog is under the fresh run's
`operations/private-catalogs` directory with owner-only permissions; no credentials
were copied. XNAT is a separate official account service. Its login page has been
opened for the owner to investigate raw MEEG through the supported alternative.
The public landing page lists Experiment 2 sizes/DOIs while the accessed download
catalog says coming soon; no Experiment 2 retrieval URLs were inferred.
