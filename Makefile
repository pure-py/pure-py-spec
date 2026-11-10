INPUTS := $(wildcard tex/*.tex spec/*.tex spec/*/*.tex spec/*/*/*.tex)
BIBFILES := $(wildcard tex/*.bib)
PYTHON_VERSION_TEX := tex/python-version.tex
MYPY_VERSION_TEX := tex/mypy-version.tex
ANON_NAME_TEX := tex/anon-name.tex
MECHANISATION_NAMES_TEX := tex/mechanisation-names.tex
SPEC_LABELS := xref/PurePy-spec.aux
FIGURE_NUMBERS := src/purepy_conformance/figure-numbers.json
TEXFILES := $(wildcard *.tex) $(INPUTS) $(BIBFILES) $(PYTHON_VERSION_TEX) $(MYPY_VERSION_TEX) $(MECHANISATION_NAMES_TEX)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
ISABELLE ?= isabelle
BUILD_AUX := *.aux *.blg *.cb *.cb2 *.cut *.fdb_latexmk *.fls *.loc *.log *.out *.soc *.toc
AUX := $(BUILD_AUX) *.bbl

default: PurePy-spec.pdf

all: PurePy-spec.pdf spec-anon.pdf graduality.pdf check-consistency

# Unresolved references are only warnings to pdflatex.
define check-log
@! grep -E "Reference .* undefined|Citation .* undefined|multiply defined" $(1).log || \
	{ echo "$(1).log: unresolved references"; exit 1; }
endef

$(PYTHON_VERSION_TEX): .python-version
	printf '\\newcommand*{\\pythonVersion}{%s}\n' "$$(cat $<)" > $@

$(ANON_NAME_TEX): .anon-name
	printf '\\newcommand*{\\anonName}{%s}\n' "$$(cat $<)" > $@

$(MYPY_VERSION_TEX): uv.lock
	printf '\\newcommand*{\\mypyVersion}{%s}\n' \
		"$$(sed -n '/^name = "mypy"$$/{n;s/^version = "\(.*\)"$$/\1/p;}' $<)" > $@

# pin: release tag
MECHANISATION_REPO := https://github.com/pure-py/isabelle-purepy
MECHANISATION_RELEASE := v$(shell cat .mechanisation-version)
# Clone of the release, made once per release
MECHANISATION := .mechanisation/$(MECHANISATION_RELEASE)

$(MECHANISATION)/ROOT:
	@git ls-remote --exit-code --tags $(MECHANISATION_REPO).git $(MECHANISATION_RELEASE) >/dev/null || \
		{ echo "report: no mechanisation release $(MECHANISATION_RELEASE)"; exit 1; }
	rm -rf $(MECHANISATION) $(MECHANISATION).tmp
	git -c advice.detachedHead=false clone -q --depth 1 --branch $(MECHANISATION_RELEASE) $(MECHANISATION_REPO).git \
		$(MECHANISATION).tmp
	mv $(MECHANISATION).tmp $(MECHANISATION)

$(MECHANISATION_NAMES_TEX): script/mechanisation-names.py $(MECHANISATION)/ROOT
	uv run --locked python $< $(MECHANISATION) > $@.tmp && mv $@.tmp $@

# FINAL=1 renders the clean version, with change markup accepted; switching modes needs a forced
# rebuild (make -B).
ifdef FINAL
latex-source = -jobname=$* "\\def\\finalmode{}\\input{$<}"
else
latex-source = $<
endif

%.pdf: %.tex $(TEXFILES)
	$(PDFLATEX) $(latex-source)
	bibtex "$*"
	$(PDFLATEX) $(latex-source)
	$(PDFLATEX) $(latex-source)
	$(call check-log,$*)
	$(if $(filter PurePy-spec,$*),mkdir -p $(dir $(SPEC_LABELS)) && cp $*.aux $(SPEC_LABELS))
	rm -f $(BUILD_AUX)

# Labels of the specification, kept for the paper's references into it (xr-hyper), outside the directory
# cleared of auxiliary files after each build.
$(SPEC_LABELS): PurePy-spec.pdf
	@test -f $@ || $(MAKE) -B PurePy-spec.pdf

$(FIGURE_NUMBERS): script/figure-numbers.py $(SPEC_LABELS)
	uv run --locked python script/figure-numbers.py > $@.tmp && mv $@.tmp $@

GRADUALITY_INPUTS := $(wildcard graduality/*.tex graduality/*/*.tex)
## Draft notes on gradual typing, outside the 1.0 spec and paper
graduality.pdf: $(GRADUALITY_INPUTS)

# Anonymised build of source $(2) under job name $(1).
define anon
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
bibtex $(1)
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
$(call check-log,$(1))
endef

## Anonymised spec builds, with no undefined references or citations
spec-anon.pdf: $(TEXFILES) $(ANON_NAME_TEX)
	$(call anon,spec-anon,PurePy-spec.tex)
	rm -f $(BUILD_AUX)

## Spec consistent with conformance suite
check-consistency:
	uv run --locked python test/check-consistency.py

## Python passes conformance suite, with mypy as type checker
check-suite-python:
	uv run --locked purepy-conformance --python-mode \
		--type-checker "mypy --python-version $$(cat .python-version) --config-file $(CURDIR)/test/mypy.ini --no-error-summary"

# tracks: latest release
PUREPY_LATEST_WHEEL = $(shell gh release view --repo https://github.com/pure-py/isabelle-purepy --json assets \
	--jq '.assets[] | select(.name | endswith(".whl")) | .url')

## Latest mechanisation release passes the suite, except for listed expected failures
check-suite-purepy:
	@test -n "$(PUREPY_LATEST_WHEEL)" || { echo "no release of the mechanisation found"; exit 1; }
	uv run --locked python test/expected-failures.py --type-checker "uvx --from $(PUREPY_LATEST_WHEEL) purepy --check"

## Suite against the isabelle-purepy branch of the same issue, or else the latest release
check-suite-mechanisation:
	@tree=$$(uv run --locked python test/mechanisation-worktree.py) || exit 1; \
	if [ -z "$$tree" ]; then $(MAKE) check-suite-purepy; else \
		test -z "$$(git -C "$$tree" status --porcelain)" || { echo "uncommitted changes in $$tree"; exit 1; }; \
		$(MAKE) -C "$$tree" build && \
		uv run --locked python test/expected-failures.py --type-checker "uv run --project $$tree purepy --check"; \
	fi

## Wheel of the conformance suite and runner
wheel: check-targets check-consistency check-suite-python check-suite-purepy $(FIGURE_NUMBERS)
	rm -rf dist && uv build --wheel

## Remove build products
clean:
	rm -f $(AUX) *.pdf $(PYTHON_VERSION_TEX) $(MYPY_VERSION_TEX) $(ANON_NAME_TEX) $(MECHANISATION_NAMES_TEX)
	rm -rf $(dir $(SPEC_LABELS)) $(FIGURE_NUMBERS) .mechanisation

## Make targets documented, and workflows named after their targets
check-targets:
	script/submission-report.py --check

## List targets with descriptions
help:
	@awk '/^## / { d = substr($$0, 4); next } d && /^[a-zA-Z0-9_.-]+:/ { t = $$0; sub(/:.*/, "", t); printf "%-24s %s\n", t, d } { d = "" }' $(MAKEFILE_LIST)

.PHONY: default all help check-targets clean check-consistency check-suite-python check-suite-purepy check-suite-mechanisation wheel
