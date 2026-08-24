TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex fig/*.tex)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
ARXIV_ZIP := paper-arXiv.zip
ARXIV_FILES := \
	paper.tex \
	$(wildcard tex/*.tex) \
	$(wildcard fig/*.tex) \
	$(wildcard *.bbl *.bst tex/*.bib) \
	$(wildcard fig/*.pdf fig/*.png fig/*.jpg fig/*.jpeg fig/*.eps)

default: paper.pdf

%.pdf: %.tex $(TEXFILES)
	$(PDFLATEX) $<
	bibtex "$*"
	$(PDFLATEX) $<
	$(PDFLATEX) $<

spec: PurePy-spec.pdf

anon: paper-anon.pdf

paper-anon.pdf: $(TEXFILES)
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"
	bibtex paper-anon
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"

clean:
	rm -f *.pdf *.aux *.log *.out *.bbl *.blg $(ARXIV_ZIP)

arXiv: $(ARXIV_ZIP)

$(ARXIV_ZIP): $(ARXIV_FILES)
	rm -f $@
	zip -9 $@ $^

.PHONY: default spec anon clean arXiv
