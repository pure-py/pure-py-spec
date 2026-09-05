TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex spec/*.tex spec/*/*.tex paper/*.tex paper/*/*.tex)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
# Removed after each build; the .bbl is kept, since paper-arXiv.zip includes it.
BUILD_AUX := *.aux *.blg *.cb *.cb2 *.cut *.fdb_latexmk *.fls *.loc *.log *.out *.soc *.toc
AUX := $(BUILD_AUX) *.bbl
ARXIV_FILES := \
	paper.tex \
	$(wildcard tex/*.tex spec/*.tex spec/*/*.tex paper/*.tex paper/*/*.tex) \
	$(wildcard *.bbl *.bst tex/*.bib)

default: paper.pdf

%.pdf: %.tex $(TEXFILES)
	$(PDFLATEX) $<
	bibtex "$*"
	$(PDFLATEX) $<
	$(PDFLATEX) $<
	rm -f $(BUILD_AUX)

# Anonymised build of source $(2) under job name $(1).
define anon
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
bibtex $(1)
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
rm -f $(BUILD_AUX)
endef

paper-anon.pdf: $(TEXFILES)
	$(call anon,paper-anon,paper.tex)

spec-anon.pdf: $(TEXFILES)
	$(call anon,spec-anon,PurePy-spec.tex)

# The specification with change markup shown, for review.
spec-markup.pdf: $(TEXFILES)
	$(PDFLATEX) -jobname=spec-markup "\def\markupmode{}\input{PurePy-spec.tex}"
	bibtex spec-markup
	$(PDFLATEX) -jobname=spec-markup "\def\markupmode{}\input{PurePy-spec.tex}"
	$(PDFLATEX) -jobname=spec-markup "\def\markupmode{}\input{PurePy-spec.tex}"
	rm -f $(BUILD_AUX)

# The Isabelle mechanisation, as a submodule so that it has a known location.
MECHANISATION := isabelle-purepy

# A submission ships the mechanisation as it stands on main, so refuse to build
# one from a working copy that has changes, unpushed commits, or a branch that
# origin/main does not already contain.
check-mechanisation:
	@test -e $(MECHANISATION)/ROOT || \
		{ echo "$(MECHANISATION) not checked out: git submodule update --init"; exit 1; }
	@test -z "$$(git -C $(MECHANISATION) status --porcelain)" || \
		{ echo "$(MECHANISATION) has uncommitted changes"; exit 1; }
	@git -C $(MECHANISATION) merge-base --is-ancestor HEAD origin/main || \
		{ echo "$(MECHANISATION) HEAD is not in origin/main: push and merge first"; exit 1; }
	@command -v isabelle >/dev/null || \
		{ echo "isabelle not on PATH: needed to check $(MECHANISATION)"; exit 1; }
	$(MAKE) -C $(MECHANISATION) build

supplementary.zip: spec-anon.pdf check-mechanisation
	rm -f $@ && rm -rf .submission
	cp spec-anon.pdf spec.pdf && zip -q -9 $@ spec.pdf && rm spec.pdf
	./anonymise-mechanisation.sh .submission
	cd .submission && zip -q -9 -r ../$@ ourlang-mechanisation
	rm -rf .submission

# Tests are included in the paper as examples, so a submission requires a passing suite.
check-tests:
	uv run --locked ./test/run-all.sh

submit: check-tests paper-anon.pdf supplementary.zip

paper-arXiv.zip: $(ARXIV_FILES)
	rm -f $@
	zip -q -9 $@ $^

clean:
	rm -f $(AUX) *.pdf *.zip

.PHONY: default submit clean check-mechanisation check-tests
