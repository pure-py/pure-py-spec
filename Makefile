TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex fig/*.tex)
ARXIV_ZIP := PurePy-spec-arXiv.zip
ARXIV_FILES := \
	PurePy-spec.tex \
	$(wildcard tex/*.tex) \
	$(wildcard fig/*.tex) \
	$(wildcard *.bbl *.bib *.bst) \
	$(wildcard fig/*.pdf fig/*.png fig/*.jpg fig/*.jpeg fig/*.eps)

default: PurePy-spec.pdf

%.pdf: %.tex $(TEXFILES)
	pdflatex $<
	pdflatex $<

clean:
	rm -f *.pdf *.aux *.log *.out $(ARXIV_ZIP)

arXiv: $(ARXIV_ZIP)

$(ARXIV_ZIP): $(ARXIV_FILES)
	rm -f $@
	zip -9 $@ $^

.PHONY: default clean arXiv
