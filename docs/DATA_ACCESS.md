# Data-source and access ledger

Checked 2026-08-30. Generated per-file inventories under `manifests/generated/` supersede this human-readable summary.

| Family | Pinned source | Access / license status | Approximate size | Acquisition behavior |
|---|---|---|---:|---|
| Multisite working memory | OSF `xzv9t`, live snapshot dated 2026-08-30 | Public; OSF node declares no license | 0.54 GB | Recursively inventory and download every file; never execute included binaries |
| Masked-content fMRI | OpenNeuro `ds003927` v1.0.3, Git SHA `1f62eb6…` | Public, CC0 | 159.3 GB recursive objects (153.3 GB snapshot display) | GraphQL resolves all 1,314 versioned objects; concurrent resumable download to NAS |
| BMVP | official `download_all.html`, inventory dated 2026-08-30 | Public, CC BY 4.0 | official site reports 1.47 TB | Parse 168 official archive URLs, resume, retain archives, checksum, extract separately |
| COGITATE | official release documentation v1.3 / DOI `10.17617/1.K278-N152` | CC BY 4.0 subject to terms; separate account required for bundles/XNAT | roughly 700 GB for M-EEG alone | Mark `WAITING_ACCESS`; owner creates account and accepts terms; credentials remain outside Git |
| Propofol volition fMRI | OpenNeuro `ds006623` v1.0.0, Git SHA `9c36d2c…` | Public, CC0 | 1.578 TB recursive objects (34.1 GB snapshot display) | Download all 119,120 versioned objects, including the official derivatives tree, as requested |
| DREAM | registry v6, DOI `10.26180/22133105.v6` | Mixed per constituent; registry links open and restricted packages | variable | Download registry; follow only direct open links; restricted records remain explicit |
| Propofol awakening EEG/TMS-EEG | OpenNeuro `ds005620` v1.0.0, Git SHA `a7ee507…` | Public, CC0 | 83.003 GB | Download all 1,442 versioned objects with exact recursive-byte validation |

## Access rules

Public visibility does not imply permission to redistribute. Raw data remain on the institutional storage and are not pushed to GitHub. Derivative release is reviewed against each source license and terms. COGITATE authentication is never automated by storing a password in the repository, and access controls are never bypassed.

The DREAM registry is dynamic and its constituent datasets have distinct restrictions. The acquisition adapter records `downloaded`, `waiting_access`, `manual_resolution`, or `invalid_source` per record; it never converts unavailable packages into silent exclusions.

As checked from the university host on 2026-08-30, the DREAM registry redirect terminates at an
object host with an invalid/expired TLS certificate. The downloader deliberately refuses to disable
certificate verification. DREAM therefore remains a source-level failure until the provider repairs
TLS or a checksum-authenticated official mirror is configured; other families continue.
