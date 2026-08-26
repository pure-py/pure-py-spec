TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex spec/*.tex spec/*/*.tex paper/*.tex paper/*/*.tex)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
AUX := *.aux *.bbl *.blg *.cb *.cb2 *.cut *.fdb_latexmk *.fls *.loc *.log *.out *.soc *.toc
ARXIV_ZIP := paper-arXiv.zip
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

spec: PurePy-spec.pdf

spec-anon: spec.pdf

spec.pdf: $(TEXFILES) | clean-aux
	$(PDFLATEX) -jobname=spec "\def\anonmode{}\input{PurePy-spec.tex}"
	bibtex spec
	$(PDFLATEX) -jobname=spec "\def\anonmode{}\input{PurePy-spec.tex}"
	$(PDFLATEX) -jobname=spec "\def\anonmode{}\input{PurePy-spec.tex}"

anon: paper-anon.pdf

paper-anon.pdf: $(TEXFILES) | clean-aux
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"
	bibtex paper-anon
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"

# Zip rather than a bare PDF, to make room for a mechanisation.
submit: paper-anon.pdf supplementary.zip

supplementary.zip: spec.pdf
	rm -f $@
	zip -q -9 $@ $<

clean-aux:
	rm -f $(AUX)

clean: clean-aux
	rm -f *.pdf *.zip

arXiv: $(ARXIV_ZIP)

$(ARXIV_ZIP): $(ARXIV_FILES)
	rm -f $@
	zip -9 $@ $^

.PHONY: default spec spec-anon anon submit clean-aux clean arXiv
