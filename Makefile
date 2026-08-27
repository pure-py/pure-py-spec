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

# Zip rather than a bare PDF, to make room for a mechanisation.
supplementary.zip: spec-anon.pdf
	rm -f $@
	cp $< spec.pdf && zip -q -9 $@ spec.pdf && rm spec.pdf

submit: paper-anon.pdf supplementary.zip

paper-arXiv.zip: $(ARXIV_FILES)
	rm -f $@
	zip -q -9 $@ $^

clean:
	rm -f $(AUX) *.pdf *.zip

.PHONY: default submit clean
