TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex spec/*.tex spec/*/*.tex paper/*.tex paper/*/*.tex)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
AUX := *.aux *.bbl *.blg *.cb *.cb2 *.cut *.fdb_latexmk *.fls *.loc *.log *.out *.soc *.toc
ARXIV_FILES := \
	paper.tex \
	$(wildcard tex/*.tex spec/*.tex spec/*/*.tex paper/*.tex paper/*/*.tex) \
	$(wildcard *.bbl *.bst tex/*.bib)

default: paper.pdf

%.pdf: %.tex $(TEXFILES) | clean-aux
	$(PDFLATEX) $<
	bibtex "$*"
	$(PDFLATEX) $<
	$(PDFLATEX) $<

# Anonymised build of source $(2) under job name $(1).
define anon
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
bibtex $(1)
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
$(PDFLATEX) -jobname=$(1) "\def\anonmode{}\input{$(2)}"
endef

paper-anon.pdf: $(TEXFILES) | clean-aux
	$(call anon,paper-anon,paper.tex)

spec-anon.pdf: $(TEXFILES) | clean-aux
	$(call anon,spec-anon,PurePy-spec.tex)

# Zip rather than a bare PDF, to make room for a mechanisation.
supplementary.zip: spec-anon.pdf
	rm -f $@
	cp $< spec.pdf && zip -q -9 $@ spec.pdf && rm spec.pdf

submit: paper-anon.pdf supplementary.zip

paper-arXiv.zip: $(ARXIV_FILES)
	rm -f $@
	zip -q -9 $@ $^

clean-aux:
	rm -f $(AUX)

clean: clean-aux
	rm -f *.pdf *.zip

.PHONY: default submit clean-aux clean
