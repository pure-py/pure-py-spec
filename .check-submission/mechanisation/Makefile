# Override when isabelle isn't on PATH
ISABELLE ?= isabelle
PYTHON ?= uv run --no-project python

ISABELLE_VERSION := $(shell cat .isabelle-version)
CODEGEN := python/isabelle-python-codegen
CODE := python/python_out/mechanisation-python.Codegen/code
GENERATED := src/ourlang/generated

default: build

check-version:
	@test "$$($(ISABELLE) version)" = "$(ISABELLE_VERSION)" || \
		{ echo "$(ISABELLE) is $$($(ISABELLE) version), not $(ISABELLE_VERSION)"; exit 1; }

codegen:
	@test -e $(CODEGEN)/Python.thy -a ! -e $(CODEGEN)/.git || ./fetch-codegen.sh

build: check-version codegen
	@test "$$(cat .python-version)" = "$$(cat $(CODEGEN)/.python-version)" || \
		{ echo "code generator targets Python $$(cat $(CODEGEN)/.python-version), not $$(cat .python-version)"; exit 1; }
	$(PYTHON) theories.py --check
	rm -rf python/python_out
	$(ISABELLE) build -v -e -d $(CODEGEN) -D .
	$(PYTHON) generated.py $(CODE) $(GENERATED)
	uv run --locked python exit_codes.py $(GENERATED)/exit_codes.py

# Lint and conformance suite
check-conformance:
	@test -e $(GENERATED) || { echo "$(GENERATED) not generated: make build"; exit 1; }
	uv run --locked ./test/check-conformance.sh

wheel: check-conformance
	rm -rf dist && uv build --wheel

# Self-contained copy under DEST
dist: codegen
	@test -n "$(DEST)" || { echo "usage: make dist DEST=<dir>"; exit 1; }
	@test ! -e $(DEST) || { echo "$(DEST) exists"; exit 1; }
	mkdir -p $(DEST)/$(CODEGEN)
	git archive --format=tar HEAD | tar -x -C $(DEST)
	git -C $(CODEGEN) archive --format=tar HEAD | tar -x -C $(DEST)/$(CODEGEN)
	rm -rf $(DEST)/.github $(DEST)/.claude $(DEST)/fetch-codegen.sh

.PHONY: default check-version codegen build check-conformance wheel dist
