PYTHON ?= python3
VENV ?= .venv
CONFIG ?= conf/base.yaml

.PHONY: bootstrap validate test simulate manifest acquire status analysis figures reproduce clean

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -e '.[workflow,analysis,neuro,test]'

validate:
	$(PYTHON) -m factorcon config validate --config $(CONFIG)
	$(PYTHON) -m pytest -q

test:
	$(PYTHON) -m pytest -q

simulate:
	$(PYTHON) -m factorcon simulate --architecture all --out results/synthetic

manifest:
	$(PYTHON) -m factorcon manifest resolve --config $(CONFIG)

acquire:
	$(PYTHON) -m factorcon acquire --config $(CONFIG) --eligible-only

status:
	$(PYTHON) -m factorcon status --config $(CONFIG)

analysis:
	$(PYTHON) -m snakemake --snakefile workflow/Snakefile --configfile $(CONFIG) --cores all all_analysis

figures:
	$(PYTHON) -m snakemake --snakefile workflow/Snakefile --configfile $(CONFIG) --cores 1 figures

reproduce:
	$(PYTHON) -m snakemake --snakefile workflow/Snakefile --configfile $(CONFIG) --cores all reproduce

clean:
	@echo "Generated research data are never deleted by Makefile. Remove specific scratch targets manually."

