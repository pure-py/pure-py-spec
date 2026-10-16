INPUTS := $(wildcard tex/*.tex spec/*.tex spec/*/*.tex spec/*/*/*.tex paper/*.tex paper/*/*.tex)
BIBFILES := $(wildcard tex/*.bib)
PYTHON_VERSION_TEX := tex/python-version.tex
MYPY_VERSION_TEX := tex/mypy-version.tex
ANON_NAME_TEX := tex/anon-name.tex
SPEC_LABELS := xref/PurePy-spec.aux
TEXFILES := $(wildcard *.tex) $(INPUTS) $(BIBFILES) $(PYTHON_VERSION_TEX) $(MYPY_VERSION_TEX) $(ANON_NAME_TEX)
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

$(ANON_NAME_TEX): .anon-name
	printf '\\newcommand*{\\anonName}{%s}\n' "$$(cat $<)" > $@

$(MYPY_VERSION_TEX): uv.lock
	printf '\\newcommand*{\\mypyVersion}{%s}\n' \
		"$$(sed -n '/^name = "mypy"$$/{n;s/^version = "\(.*\)"$$/\1/p;}' $<)" > $@
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

paper.pdf paper-anon.pdf: $(SPEC_LABELS)

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
	zip -q -9 $@ paper.tex paper.bbl $(sort $(INPUTS) $(PYTHON_VERSION_TEX) $(MYPY_VERSION_TEX))

clean:
	rm -f $(AUX) *.pdf *.zip $(PYTHON_VERSION_TEX) $(MYPY_VERSION_TEX) $(ANON_NAME_TEX)
	rm -rf $(dir $(SPEC_LABELS))

.PHONY: default all paper-submission clean check-mechanisation check-tests
