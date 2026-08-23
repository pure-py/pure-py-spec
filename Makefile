TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex fig/*.tex)
ARXIV_ZIP := PurePy-spec-arXiv.zip
ARXIV_FILES := \
	PurePy-spec.tex \
	$(wildcard tex/*.tex) \
	$(wildcard fig/*.tex) \
	$(wildcard *.bbl *.bst tex/*.bib) \
	$(wildcard fig/*.pdf fig/*.png fig/*.jpg fig/*.jpeg fig/*.eps)

default: PurePy-spec.pdf

%.pdf: %.tex $(TEXFILES)
	pdflatex $<
	bibtex "$*"
	pdflatex $<
	pdflatex $<

anon: PurePy-spec-anon.pdf

PurePy-spec-anon.pdf: $(TEXFILES)
	pdflatex -jobname=PurePy-spec-anon "\def\anonmode{}\input{PurePy-spec.tex}"
	bibtex PurePy-spec-anon
	pdflatex -jobname=PurePy-spec-anon "\def\anonmode{}\input{PurePy-spec.tex}"
	pdflatex -jobname=PurePy-spec-anon "\def\anonmode{}\input{PurePy-spec.tex}"

clean:
	rm -f *.pdf *.aux *.log *.out *.bbl *.blg $(ARXIV_ZIP)

arXiv: $(ARXIV_ZIP)

$(ARXIV_ZIP): $(ARXIV_FILES)
	rm -f $@
	zip -9 $@ $^

.PHONY: default anon clean arXiv
