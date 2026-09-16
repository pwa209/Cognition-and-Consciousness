# Cognition and Consciousness Factorization Study

This repository implements a transparent, non-preregistered secondary analysis of public and access-controlled human datasets. It tests whether experience (`E`), cognitive operations (`K`), arousal/global state (`A`), report/action (`R`), and sensory structure (`S`) require distinguishable neural components.

The scientific premise is described in [Consciousness_Cognition_Factorization_Proposal_Neuron_NHB.docx](Consciousness_Cognition_Factorization_Proposal_Neuron_NHB.docx). That document is source material, not an instruction file. The implementation deliberately departs from its registration and lockbox language:

- the study is **not registered or preregistered**;
- there are **no scientific success gates** and no result-dependent stopping rules;
- every candidate architecture and every completed dataset-family result is retained;
- integrity, access, leakage, provenance, and computational checks remain mandatory;
- changes to analysis choices are timestamped in `docs/DEVIATIONS.md`.

The journal ambition is Nature or Science, with Nature Human Behaviour as a realistic alternative if the mechanistic evidence is less broad. Journal positioning never controls execution or reporting.

## Current state

**Compute Canada, 2026-09-16:** a fresh deployment is running on personal Rorqual
scratch, with owner authorization for acquisition and ready analysis phases. WM
download/validation/harmonization completed; further acquisition and independent
simulations are running. See the [deployment record](docs/ALLIANCE_DEPLOYMENT_STATUS.md)
and [fresh-run roadmap](docs/ALLIANCE_FRESH_RUN.md). No data or environments were
imported from earlier studies; the university server remains unchanged.

**Scientific follow-up, 2026-09-10:** a separate local generative-pattern engine now
fits M0–M5, integrates external report-measurement draws, and implements nested
within-family and source-only LOFO prediction. Report measurement, independent stress
generators and training-refit subject bootstrap are included. This is not yet the
complete raw-data-to-manuscript implementation. See the
[implemented fixes and remaining boundaries](docs/IMPLEMENTATION_FOLLOWUP_2026-09-10.md)
and [local command contracts](docs/PATTERN_AND_MEASUREMENT_COMMANDS.md).
The historical [canonical RDM v2 scorer](docs/CANONICAL_RDM_V2.md) remains a distinct
prototype; its scores must not be mixed with pattern likelihoods. University analysis
activation remains unauthorized; Rorqual has the separate authorization above.

- Proposal: audited, extracted, and translated into implementation contracts.
- University server: H100 host verified; no Slurm; persistent jobs use `tmux` plus logs and status markers.
- Public source audit: OpenNeuro, OSF, and BMVP are directly retrievable. COGITATE requires a user-created account and acceptance of terms. DREAM is a registry with dataset-specific access states.
- Data policy: university-run data stay on its NAS/work volumes; fresh Rorqual data,
  caches and derivatives stay on personal scratch, not shared `/project`. All are excluded from Git.
- Analysis status: architecture, leakage, feature, model, simulation, and reporting cores are tested;
  dataset-specific P06 producers that depend on downloaded schemas are deliberately explicit
  contracts rather than unvalidated guesses.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the phase map and [docs/SERVER_RUNBOOK.md](docs/SERVER_RUNBOOK.md) for operations.

## Quick start

Python 3.12 is the reference runtime. Acquisition and provenance commands use only the standard library; scientific extras are installed separately.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
factorcon config validate --config conf/base.yaml
factorcon simulate --architecture all --out results/synthetic
pytest -q
```

University-server authorization is acquisition-only. Use the sparse acquisition release described in
[`docs/SERVER_RUNBOOK.md`](docs/SERVER_RUNBOOK.md), resolve manifests, and then queue raw-data
downloads. Do not deploy or queue P03-P10 unless the owner explicitly expands the scope. Do not
place passwords, API keys, cookies, or account credentials in this repository or in command
history.

## Reproducible command surface

```text
make bootstrap       create an isolated Python environment
make validate        validate configuration and run tests
make simulate        run architecture-recovery simulations
make manifest        resolve source metadata without downloading raw data
make acquire         download eligible public data to the NAS
make status          summarize server markers and manifests
make analysis        run the configured scientific workflow
make figures         rebuild figures from tidy result tables
make reproduce       rebuild all tracked manuscript outputs
```

Large jobs must be launched through the phase runner. Direct foreground downloads are reserved for tiny smoke tests.

## Repository/data boundary

Tracked: source code, configuration, human-reviewed construct maps, source manifests, checksums/inventories, environment definitions, run summaries, deviations, roadmap, manuscript code, and small figure-source tables.

Not tracked: participant-level raw data, large derivatives, caches, temporary work, credentials, cookies, or protected metadata. Dataset licenses and terms remain authoritative.
