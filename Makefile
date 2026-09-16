INPUTS := $(wildcard tex/*.tex spec/*.tex spec/*/*.tex spec/*/*/*.tex paper/*.tex paper/*/*.tex)
TEXFILES := $(wildcard *.tex) $(INPUTS)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
# Removed after each build; the .bbl is kept, since paper-arXiv.zip includes it.
BUILD_AUX := *.aux *.blg *.cb *.cb2 *.cut *.fdb_latexmk *.fls *.loc *.log *.out *.soc *.toc
AUX := $(BUILD_AUX) *.bbl

default: paper.pdf

all: PurePy-spec.pdf paper.pdf graduality.pdf paper-arXiv.zip paper-submission

# pdflatex only warns about these, so check the log of job $(1) before removing it.
define check-log
@! grep -E "Reference .* undefined|Citation .* undefined|multiply defined" $(1).log || \
	{ echo "$(1).log: unresolved references"; exit 1; }
endef

%.pdf: %.tex $(TEXFILES)
	$(PDFLATEX) $<
	bibtex "$*"
	$(PDFLATEX) $<
	$(PDFLATEX) $<
	$(call check-log,$*)
	rm -f $(BUILD_AUX)

# Draft notes on gradual typing, a separate document that is not part of the 1.0 specification or
# paper. Its sources are not in $(INPUTS), so they do not ship with the arXiv source; the pattern rule
# above supplies the recipe.
GRADUALITY_INPUTS := $(wildcard graduality/*.tex graduality/*/*.tex)
graduality.pdf: $(GRADUALITY_INPUTS)

# Anonymised build of source $(2) under job name $(1).
define anon
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
bibtex $(1)
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
$(call check-log,$(1))
rm -f $(BUILD_AUX)
endef

paper-anon.pdf: $(TEXFILES)
	$(call anon,paper-anon,paper.tex)

spec-anon.pdf: $(TEXFILES)
	$(call anon,spec-anon,PurePy-spec.tex)

# The Isabelle mechanisation, as a submodule so that it has a known location.
ISABELLE := isabelle-purepy

# A submission ships the mechanisation as it stands on main, so refuse to build
# one from a working copy with uncommitted changes or with a checked-out commit
# that is not on origin/main.
check-mechanisation:
	@test -e $(ISABELLE)/ROOT || \
		{ echo "$(ISABELLE) not checked out: git submodule update --init"; exit 1; }
	@test -z "$$(git -C $(ISABELLE) status --porcelain)" || \
		{ echo "$(ISABELLE) has uncommitted changes"; exit 1; }
	@git -C $(ISABELLE) merge-base --is-ancestor HEAD origin/main || \
		{ echo "$(ISABELLE) HEAD is not in origin/main: push and merge first"; exit 1; }
	@command -v isabelle >/dev/null || \
		{ echo "isabelle not on PATH: needed to check $(ISABELLE)"; exit 1; }
	$(MAKE) -C $(ISABELLE) build

supplementary.zip: spec-anon.pdf check-mechanisation
	rm -f $@ && rm -rf .submission
	cp spec-anon.pdf spec.pdf && zip -q -9 $@ spec.pdf && rm spec.pdf
	./anonymise-mechanisation.sh .submission
	cd .submission && zip -q -9 -r ../$@ mechanisation
	rm -rf .submission

# Tests are included in the paper as examples, so a submission requires a passing suite.
check-tests:
	uv run --locked ./test/run-all.sh

paper-submission: check-tests paper-anon.pdf supplementary.zip

# arXiv runs pdflatex but not bibtex, so the source ships with the .bbl of the current build.
paper-arXiv.zip: paper.pdf
	rm -f $@
	zip -q -9 $@ paper.tex paper.bbl $(INPUTS)

clean:
	rm -f $(AUX) *.pdf *.zip

.PHONY: default all paper-submission clean check-mechanisation check-tests
