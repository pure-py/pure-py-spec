INPUTS := $(wildcard tex/*.tex spec/*.tex spec/*/*.tex spec/*/*/*.tex paper/*.tex paper/*/*.tex)
BIBFILES := $(wildcard tex/*.bib)
PYTHON_VERSION_TEX := tex/python-version.tex
TEXFILES := $(wildcard *.tex) $(INPUTS) $(BIBFILES) $(PYTHON_VERSION_TEX)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
BUILD_AUX := *.aux *.blg *.cb *.cb2 *.cut *.fdb_latexmk *.fls *.loc *.log *.out *.soc *.toc
AUX := $(BUILD_AUX) *.bbl

default: paper.pdf

all: PurePy-spec.pdf paper.pdf graduality.pdf paper-arXiv.zip paper-submission

# Unresolved references are only warnings to pdflatex.
define check-log
@! grep -E "Reference .* undefined|Citation .* undefined|multiply defined" $(1).log || \
	{ echo "$(1).log: unresolved references"; exit 1; }
endef

$(PYTHON_VERSION_TEX): .python-version
	printf '\\newcommand*{\\pythonVersion}{%s}\n' "$$(cat $<)" > $@

%.pdf: %.tex $(TEXFILES)
	$(PDFLATEX) $<
	bibtex "$*"
	$(PDFLATEX) $<
	$(PDFLATEX) $<
	$(call check-log,$*)
	rm -f $(BUILD_AUX)

# Draft notes on gradual typing, not part of the 1.0 specification or paper.
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

ISABELLE := isabelle-purepy

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

# Paper examples are tests.
check-tests:
	uv run --locked ./test/run-all.sh

paper-submission: check-tests paper-anon.pdf supplementary.zip

# arXiv runs pdflatex without bibtex, so include the .bbl.
paper-arXiv.zip: paper.pdf
	rm -f $@
	zip -q -9 $@ paper.tex paper.bbl $(sort $(INPUTS) $(PYTHON_VERSION_TEX))

clean:
	rm -f $(AUX) *.pdf *.zip $(PYTHON_VERSION_TEX)

.PHONY: default all paper-submission clean check-mechanisation check-tests
