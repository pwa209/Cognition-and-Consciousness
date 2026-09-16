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
