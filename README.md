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

- Proposal: audited, extracted, and translated into implementation contracts.
- University server: H100 host verified; no Slurm; persistent jobs use `tmux` plus logs and status markers.
- Public source audit: OpenNeuro, OSF, and BMVP are directly retrievable. COGITATE requires a user-created account and acceptance of terms. DREAM is a registry with dataset-specific access states.
- Data policy: raw data and heavy derivatives live only on the university NAS/work volumes and are excluded from Git.

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

On the university server, use `scripts/server/bootstrap.sh`, then queue phases with `scripts/server/queue_phase.sh`. Do not place passwords, API keys, cookies, or account credentials in this repository or in command history.

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

